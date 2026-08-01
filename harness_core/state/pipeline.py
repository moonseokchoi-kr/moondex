"""Pure phase transitions and project-artifact preflight."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import re
from typing import Any, Iterable

from .storage import StateBusyError, atomic_write_json, exclusive_lock, load_json


SCHEMA_VERSION = 1
MAX_RETRIES = 3
_FEATURE_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_TASK_ID = re.compile(r"T-([1-9][0-9]*)\Z")
_TASK_DOCUMENT = re.compile(r".+-T-([1-9][0-9]*)-.+\.md\Z")


class Phase(str, Enum):
    SPEC = "SPEC"
    DESIGN = "DESIGN"
    PLAN = "PLAN"
    EXECUTE = "EXECUTE"
    RESULT = "RESULT"


class TransitionError(ValueError):
    pass


class PreflightError(ValueError):
    pass


def initial_state(feature: str, phase: Phase = Phase.SPEC) -> dict[str, Any]:
    _validate_feature_slug(feature)
    return {
        "schema_version": SCHEMA_VERSION,
        "feature": feature,
        "phase": phase.value,
        "approval": {"spec": False, "design": False, "plan": False},
        "worktree": None,
        "run_id": None,
        "task_retries": {},
        "updated_at": _now(),
    }


def transition(state: dict[str, Any], target: Phase, *, worktree: Path | None = None) -> dict[str, Any]:
    """Return the next state or fail with the required remediation."""

    _validate_state(state)
    current = Phase(state["phase"])
    if target is current:
        return deepcopy(state)
    if _phase_index(target) != _phase_index(current) + 1:
        raise TransitionError(
            f"Invalid transition {current.value} -> {target.value}. "
            "Advance one approved phase at a time."
        )

    required_approval = {Phase.DESIGN: "spec", Phase.PLAN: "design", Phase.EXECUTE: "plan"}.get(target)
    if required_approval and not state["approval"].get(required_approval):
        raise TransitionError(
            f"Cannot enter {target.value}: {required_approval} approval is missing. "
            "Record explicit user approval before retrying."
        )
    if target is Phase.EXECUTE:
        if worktree is None or not worktree.is_dir():
            raise TransitionError(
                "Cannot enter EXECUTE: an isolated worktree is required. "
                "Create or select a worktree, then rerun preflight."
            )

    updated = deepcopy(state)
    updated["phase"] = target.value
    if worktree is not None:
        updated["worktree"] = str(worktree)
    return updated


def record_retry(state: dict[str, Any], task_id: str) -> dict[str, Any]:
    """Increment a task retry count and permanently expose escalation at the limit."""

    _validate_state(state)
    if not task_id:
        raise TransitionError("Task id is required to record a retry.")
    updated = deepcopy(state)
    retries = updated["task_retries"].get(task_id, 0) + 1
    updated["task_retries"][task_id] = retries
    if retries >= MAX_RETRIES:
        updated.setdefault("escalations", []).append(task_id)
    return updated


def preflight_phase(project_root: Path, state: dict[str, Any], target: Phase) -> None:
    """Check on-disk evidence required before an explicit phase transition."""

    _validate_state(state)
    feature = state["feature"]
    missing: list[str] = []
    spec_dir = project_root / "docs/sdd/spec"
    design_dir = project_root / "docs/sdd/design/arch"
    task_dir = project_root / "docs/sdd/task" / feature
    orchestrator_state = project_root / "docs/sdd/ORCHESTRATOR_STATE.md"

    if target in (Phase.DESIGN, Phase.PLAN, Phase.EXECUTE, Phase.RESULT) and not _has_feature_document(spec_dir, feature):
        missing.append("Create docs/sdd/spec/<date>-<feature>.md.")
    if target in (Phase.PLAN, Phase.EXECUTE, Phase.RESULT) and not _has_feature_document(design_dir, feature):
        missing.append("Create docs/sdd/design/arch/<date>-<feature>.md.")
    if target in (Phase.EXECUTE, Phase.RESULT):
        if not _has_markdown(task_dir):
            missing.append(f"Create task documents under docs/sdd/task/{feature}/.")
        if not orchestrator_state.is_file():
            missing.append("Create docs/sdd/ORCHESTRATOR_STATE.md with Waves and task ownership.")
        if not state["approval"].get("plan"):
            missing.append("Record explicit plan approval before executing.")
        worktree = state.get("worktree")
        if not worktree or not Path(worktree).is_dir():
            missing.append("Set state.worktree to an existing isolated worktree.")
    if target is Phase.RESULT and state["phase"] != Phase.EXECUTE.value:
        missing.append("Reach EXECUTE before creating a result.")
    if target is Phase.RESULT:
        completion_error = _task_completion_error(orchestrator_state, task_dir, feature)
        if completion_error:
            missing.append(completion_error)
    if missing:
        raise PreflightError("Preflight failed:\n- " + "\n- ".join(missing))


def check_owned_paths(changed_paths: Iterable[Path], owned_paths: Iterable[Path]) -> list[Path]:
    """Return changed paths outside a task's declared ownership roots."""

    roots = [path.resolve() for path in owned_paths]
    violations = []
    for changed in changed_paths:
        resolved = changed.resolve()
        if not any(resolved == root or root in resolved.parents for root in roots):
            violations.append(changed)
    return violations


def _has_markdown(directory: Path) -> bool:
    return directory.is_dir() and any(candidate.is_file() for candidate in directory.glob("*.md"))


def _has_feature_document(directory: Path, feature: str) -> bool:
    """Return whether an SDD document belongs to this feature.

    SDD documents use ``<date>-<feature>.md``.  The prefix remains deliberately
    unconstrained so older date formats continue to work, but a document for a
    different feature must never satisfy this phase gate.
    """

    if not directory.is_dir():
        return False
    suffix = f"-{feature}.md"
    # Do not interpolate ``feature`` into a glob: a feature such as ``port*``
    # must never let a sibling artifact satisfy this gate.
    return any(
        candidate.is_file() and candidate.name.endswith(suffix)
        for candidate in directory.iterdir()
    )


def _task_completion_error(orchestrator_state: Path, task_dir: Path, feature: str) -> str | None:
    """Return why RESULT cannot be entered, or ``None`` for verified completion.

    ``ORCHESTRATOR_STATE.md`` is a human-maintained control record, so this
    intentionally accepts only an unambiguous feature declaration and Task
    status table.  RESULT is fail-closed: a stub state file, another feature's
    state with coincident task IDs, duplicated metadata or rows, or a task
    document without a completed row cannot certify execution.
    """

    if not orchestrator_state.is_file():
        return "orchestrator state artifact is missing"
    task_ids, duplicate_task_ids = _task_document_ids(task_dir)
    if not task_ids:
        return "feature task documents are missing"
    if duplicate_task_ids:
        return "feature task documents duplicate task ids: " + ", ".join(
            sorted(duplicate_task_ids, key=_task_number)
        )
    try:
        contents = orchestrator_state.read_text(encoding="utf-8")
        _require_state_feature(contents, feature)
        rows = _parse_task_status_table(contents)
    except (OSError, ValueError) as exc:
        return f"task completion evidence is invalid: {exc}"

    unknown = sorted(set(rows) - task_ids, key=_task_number)
    if unknown:
        return "task completion evidence names unknown feature tasks: " + ", ".join(unknown)
    missing = sorted(task_ids - set(rows), key=_task_number)
    if missing:
        return "task completion evidence is missing rows for: " + ", ".join(missing)
    incomplete = sorted(
        task_id for task_id in task_ids
        if rows[task_id]["status"].casefold() != "complete"
    )
    if incomplete:
        return "feature tasks are not complete: " + ", ".join(incomplete)
    unverified = sorted(
        task_id for task_id in task_ids
        if not rows[task_id]["notes"].strip()
    )
    if unverified:
        return "feature task completion evidence is missing notes for: " + ", ".join(unverified)
    return None


def _require_state_feature(contents: str, feature: str) -> None:
    """Fail closed unless the state file declares this exact feature once.

    Task identifiers are intentionally not globally unique (for example every
    SDD feature can have a ``T-2``).  The controller therefore cannot use a
    matching task table as proof that this feature completed.  Metadata uses
    the established Markdown form ``- Feature: `feature-slug```; bare values
    remain accepted for minimal local state files.
    """

    declarations: list[str] = []
    for line in contents.splitlines():
        match = re.fullmatch(r"[ \t]*-[ \t]+Feature:[ \t]*(.*?)[ \t]*", line)
        if match:
            value = match.group(1).strip()
            if value.startswith("`") and value.endswith("`") and len(value) >= 2:
                value = value[1:-1]
            declarations.append(value)
    if not declarations:
        raise ValueError("missing Feature metadata")
    if len(declarations) != 1:
        raise ValueError("Feature metadata must appear exactly once")
    if declarations[0] != feature:
        raise ValueError(f"Feature metadata does not match requested feature {feature}")


def _task_document_ids(task_dir: Path) -> tuple[set[str], set[str]]:
    """Return feature task IDs and IDs claimed by more than one task document.

    A task status table certifies document-level work.  Collapsing filenames
    into a set would let two distinct task documents with the same ``T-N``
    share one completed status row, so duplicate IDs are completion evidence
    ambiguity and must block RESULT.
    """
    if not task_dir.is_dir():
        return set(), set()
    task_ids: set[str] = set()
    duplicate_task_ids: set[str] = set()
    for document in task_dir.iterdir():
        if not document.is_file():
            continue
        match = _TASK_DOCUMENT.fullmatch(document.name)
        if match:
            task_id = f"T-{match.group(1)}"
            if task_id in task_ids:
                duplicate_task_ids.add(task_id)
            task_ids.add(task_id)
    return task_ids, duplicate_task_ids


def _parse_task_status_table(contents: str) -> dict[str, dict[str, str]]:
    lines = contents.splitlines()
    try:
        start = next(index for index, line in enumerate(lines) if line.strip() == "## Task status")
    except StopIteration as exc:
        raise ValueError("missing '## Task status' section") from exc
    header_index = next((index for index in range(start + 1, len(lines)) if lines[index].strip()), None)
    if header_index is None or header_index + 1 >= len(lines):
        raise ValueError("Task status table is incomplete")
    expected_header = ["ID", "Wave", "Status", "Iteration", "Role profile", "Notes"]
    if _table_cells(lines[header_index]) != expected_header or not _is_separator_row(lines[header_index + 1]):
        raise ValueError("Task status table has an invalid header")

    rows: dict[str, dict[str, str]] = {}
    for line in lines[header_index + 2:]:
        if not line.strip() or line.lstrip().startswith("#"):
            break
        cells = _table_cells(line)
        if cells is None or len(cells) != len(expected_header):
            raise ValueError("Task status table has a malformed row")
        task_id, wave, status, _iteration, _role, notes = cells
        if _TASK_ID.fullmatch(task_id) is None:
            raise ValueError("Task status table has an invalid task id")
        if task_id in rows:
            raise ValueError(f"Task status table duplicates {task_id}")
        if not wave.strip() or not status.strip():
            raise ValueError(f"Task status table has incomplete {task_id} status")
        rows[task_id] = {"wave": wave.strip(), "status": status.strip(), "notes": notes.strip()}
    if not rows:
        raise ValueError("Task status table has no task rows")
    return rows


def _table_cells(line: str) -> list[str] | None:
    stripped = line.strip()
    if not (stripped.startswith("|") and stripped.endswith("|")):
        return None
    return [cell.strip() for cell in stripped[1:-1].split("|")]


def _is_separator_row(line: str) -> bool:
    cells = _table_cells(line)
    return cells is not None and len(cells) == 6 and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def _task_number(task_id: str) -> int:
    return int(task_id[2:])


def _phase_index(phase: Phase) -> int:
    return list(Phase).index(phase)


def _validate_state(state: dict[str, Any]) -> None:
    if not isinstance(state, dict):
        raise TransitionError("Pipeline state must be a JSON object.")
    if state.get("schema_version") != SCHEMA_VERSION:
        raise TransitionError("Unsupported pipeline schema. Run the documented state migration.")
    try:
        _validate_feature_slug(state.get("feature"))
    except TransitionError as exc:
        raise TransitionError("Pipeline state has an invalid feature slug. Recreate state with initial_state().") from exc
    try:
        Phase(state.get("phase"))
    except ValueError as exc:
        raise TransitionError("Pipeline state has an invalid phase. Restore a valid state snapshot.") from exc
    approval = state.get("approval")
    expected_approvals = {"spec", "design", "plan"}
    if not isinstance(approval, dict) or set(approval) != expected_approvals:
        raise TransitionError("Pipeline state has an invalid approval schema.")
    if any(type(value) is not bool for value in approval.values()):
        raise TransitionError("Pipeline state approval records must be booleans.")
    if not isinstance(state.get("task_retries"), dict):
        raise TransitionError("Pipeline state is missing task retry records.")


# Controller API -----------------------------------------------------------
# These functions deliberately know nothing about hook environment variables.

def state_path(project_root: Path, feature: str | None = None) -> Path:
    """Return the canonical state path, with per-feature paths for coexistence."""
    base = project_root / ".harness/state"
    if feature is None:
        return base / "pipeline.json"
    _validate_feature_slug(feature)
    canonical = base / "pipeline.json"
    existing = load_json(canonical)
    if existing is None or (isinstance(existing, dict) and existing.get("feature") == feature):
        return canonical
    return base / "pipelines" / f"{feature}.json"


def controller_start(project_root: Path, feature: str) -> dict[str, Any]:
    if _feature_slug_error(feature):
        return _invalid_feature_result()
    path = state_path(project_root, feature)
    try:
        with exclusive_lock(_lock_path(project_root)):
            existing = load_json(path) if path.exists() else None
            if path.exists() and existing is None:
                return _result("STATE_INVALID", "state file is malformed", f"restore or remove {path}")
            if existing is not None:
                try:
                    _validate_state(existing)
                except TransitionError as exc:
                    return _result("STATE_INVALID", str(exc), f"restore {path}")
                return inspect_state(project_root, feature, state=existing, initialized=False)
            created = initial_state(feature)
            atomic_write_json(path, created)
            return _result("INITIALIZED", "created project-local state", "state resume " + feature, state=created)
    except StateBusyError:
        return _result("STATE_BUSY", "another controller owns the state lock", "retry state start " + feature)
    except OSError as exc:
        return _result("STATE_INVALID", f"could not create state: {exc}", "check .harness/state permissions")


def controller_status(project_root: Path, feature: str | None = None) -> dict[str, Any]:
    if feature is not None and _feature_slug_error(feature):
        return _invalid_feature_result()
    return inspect_state(project_root, feature)


def controller_resume(project_root: Path, feature: str | None = None) -> dict[str, Any]:
    """Read-only alias for inspection; it never advances state implicitly."""
    if feature is not None and _feature_slug_error(feature):
        return _invalid_feature_result()
    return inspect_state(project_root, feature)


def inspect_state(project_root: Path, feature: str | None = None, *, state: dict[str, Any] | None = None,
                  initialized: bool = False) -> dict[str, Any]:
    if feature is not None and _feature_slug_error(feature):
        return _invalid_feature_result()
    if state is None:
        candidates = _states(project_root)
        if feature:
            candidates = [
                (path, value) for path, value in candidates
                if isinstance(value, dict) and value.get("feature") == feature
            ]
        if not candidates:
            return _result("BLOCKED_ARTIFACT", "no project-local state exists", "state start <feature>")
        if len(candidates) > 1:
            names = sorted(str(value.get("feature", "invalid")) if isinstance(value, dict) else "invalid" for _, value in candidates)
            return _result("AMBIGUOUS_FEATURE", "multiple active features: " + ", ".join(names), "state resume <feature>")
        _, state = candidates[0]
        if state is None:
            return _result("STATE_INVALID", "state file is malformed", "restore a valid .harness/state/pipeline.json")
    try:
        _validate_state(state)
    except TransitionError as exc:
        return _result("STATE_INVALID", str(exc), "restore a valid .harness/state/pipeline.json")
    phase = Phase(state["phase"])
    if phase is Phase.RESULT:
        result_dir = project_root / "docs/sdd/result"
        if _has_feature_document(result_dir, state["feature"]):
            return _result("COMPLETE", "result artifact is present", "review result and run optional compound sync", state=state)
        return _result("ACTION", "result artifact is required", "generate docs/sdd/result/<date>-" + state["feature"] + ".md", state=state)
    target = Phase(list(Phase)[_phase_index(phase) + 1])
    artifact_error = _artifact_error(project_root, state, target)
    if artifact_error:
        return _result("BLOCKED_ARTIFACT", artifact_error, _artifact_command(state, target), state=state)
    approval = {Phase.DESIGN: "spec", Phase.PLAN: "design", Phase.EXECUTE: "plan"}.get(target)
    if approval and not state["approval"].get(approval):
        return _result("WAITING_USER", f"explicit {approval} approval is required", f"state transition --feature {state['feature']} --expected {phase.value} --target {target.value} --approve {approval}", state=state)
    return _result("ACTION", f"ready to enter {target.value}", _artifact_command(state, target), state=state)


def controller_transition(project_root: Path, *, feature: str, expected: Phase, target: Phase,
                          approve: str | None = None, worktree: Path | None = None,
                          retry_task: str | None = None) -> dict[str, Any]:
    """Compare-and-transition under the sole writer lock."""
    if _feature_slug_error(feature):
        return _invalid_feature_result()
    try:
        with exclusive_lock(_lock_path(project_root)):
            path = state_path(project_root, feature)
            state = load_json(path)
            if state is None:
                return _result("STATE_INVALID", "state is missing or malformed", "state start " + feature)
            try:
                _validate_state(state)
            except TransitionError as exc:
                return _result("STATE_INVALID", str(exc), "restore state from a valid snapshot")
            if state["phase"] != expected.value:
                return _result("STATE_INVALID", f"expected {expected.value}, found {state['phase']}", "state status " + feature, state=state)
            updated = deepcopy(state)
            if retry_task:
                if retry_task in updated.get("escalations", []):
                    return _result("ESCALATED", f"{retry_task} already reached the retry limit", "do not retry; request review", state=state)
                updated = record_retry(updated, retry_task)
                updated["updated_at"] = _now()
                atomic_write_json(path, updated)
                code = "ESCALATED" if retry_task in updated.get("escalations", []) else "ACTION"
                return _result(code, f"retry recorded for {retry_task}", "do not retry; request review" if code == "ESCALATED" else "rerun task", state=updated)
            required_approval = {Phase.DESIGN: "spec", Phase.PLAN: "design", Phase.EXECUTE: "plan"}.get(target)
            if approve:
                if approve != required_approval:
                    return _result(
                        "STATE_INVALID",
                        "approval is only valid for the immediate phase transition",
                        "approve " + (required_approval or "no approval for this transition"),
                        state=state,
                    )
                updated["approval"][approve] = True
            artifact_error = _artifact_error(project_root, updated, target, worktree)
            if artifact_error:
                return _result("BLOCKED_ARTIFACT", artifact_error, _artifact_command(updated, target), state=state)
            try:
                updated = transition(updated, target, worktree=worktree)
            except TransitionError as exc:
                return _result("BLOCKED_APPROVAL", str(exc), "obtain explicit approval then retry", state=state)
            updated["updated_at"] = _now()
            atomic_write_json(path, updated)
            return _result("ACTION", f"advanced to {target.value}", "state resume " + feature, state=updated)
    except StateBusyError:
        return _result("STATE_BUSY", "another controller owns the state lock", "retry transition after the active writer finishes")
    except OSError as exc:
        return _result("STATE_INVALID", f"could not persist state: {exc}", "check .harness/state permissions")


def controller_doctor(project_root: Path, feature: str | None = None) -> dict[str, Any]:
    if feature is not None and _feature_slug_error(feature):
        return _invalid_feature_result()
    current = inspect_state(project_root, feature)
    hook = project_root / ".harness/hooks"
    if not hook.is_dir():
        return _result("ADVISORY_UNAVAILABLE", "optional local hooks are not installed", current["next_step"], state=current.get("state"))
    return _result("ACTION", "optional local hooks are available", current["next_step"], state=current.get("state"))


def _states(root: Path) -> list[tuple[Path, dict[str, Any] | None]]:
    base = root / ".harness/state"
    paths = [base / "pipeline.json"]
    nested = base / "pipelines"
    if nested.is_dir():
        paths.extend(sorted(nested.glob("*.json")))
    return [(path, load_json(path)) for path in paths if path.exists()]


def _lock_path(root: Path) -> Path:
    return root / ".harness/state/pipeline.lock"


def _artifact_error(root: Path, state: dict[str, Any], target: Phase, worktree: Path | None = None) -> str | None:
    feature = state["feature"]
    if target in (Phase.DESIGN, Phase.PLAN, Phase.EXECUTE, Phase.RESULT) and not _has_feature_document(root / "docs/sdd/spec", feature):
        return "spec artifact is missing"
    if target in (Phase.PLAN, Phase.EXECUTE, Phase.RESULT) and not _has_feature_document(root / "docs/sdd/design/arch", feature):
        return "architecture artifact is missing"
    if target in (Phase.EXECUTE, Phase.RESULT):
        if not _has_markdown(root / "docs/sdd/task" / feature):
            return "task artifacts are missing"
        if not (root / "docs/sdd/ORCHESTRATOR_STATE.md").is_file():
            return "orchestrator state artifact is missing"
        candidate = worktree or (Path(state["worktree"]) if state.get("worktree") else None)
        if target is Phase.EXECUTE and (candidate is None or not candidate.is_dir()):
            return "isolated worktree is missing"
    if target is Phase.RESULT:
        return _task_completion_error(
            root / "docs/sdd/ORCHESTRATOR_STATE.md", root / "docs/sdd/task" / feature, feature
        )
    return None


def _artifact_command(state: dict[str, Any], target: Phase) -> str:
    feature = state["feature"]
    commands = {Phase.DESIGN: f"create docs/sdd/spec/<date>-{feature}.md", Phase.PLAN: f"create docs/sdd/design/arch/<date>-{feature}.md", Phase.EXECUTE: f"create docs/sdd/task/{feature}/ and docs/sdd/ORCHESTRATOR_STATE.md", Phase.RESULT: f"create docs/sdd/result/<date>-{feature}.md"}
    return commands[target]


def _feature_slug_error(feature: object) -> bool:
    return not isinstance(feature, str) or _FEATURE_SLUG.fullmatch(feature) is None


def _validate_feature_slug(feature: object) -> None:
    if _feature_slug_error(feature):
        raise TransitionError(
            "feature must be a lowercase kebab-case slug (letters and digits separated by hyphens)"
        )


def _invalid_feature_result() -> dict[str, Any]:
    return _result(
        "STATE_INVALID",
        "feature must be a lowercase kebab-case slug (letters and digits separated by hyphens)",
        "state start <feature>",
    )


def _result(code: str, message: str, next_step: str, *, state: dict[str, Any] | None = None) -> dict[str, Any]:
    answer: dict[str, Any] = {"code": code, "message": message, "next_step": next_step}
    if state is not None:
        answer["state"] = state
    return answer


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
