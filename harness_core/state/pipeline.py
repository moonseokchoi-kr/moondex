"""Pure phase transitions and project-artifact preflight."""

from __future__ import annotations

from copy import deepcopy
from enum import Enum
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = 1
MAX_RETRIES = 3


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
    return {
        "schema_version": SCHEMA_VERSION,
        "feature": feature,
        "phase": phase.value,
        "approval": {"spec": False, "design": False, "plan": False},
        "worktree": None,
        "run_id": None,
        "task_retries": {},
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

    if target in (Phase.DESIGN, Phase.PLAN, Phase.EXECUTE, Phase.RESULT) and not _has_markdown(spec_dir):
        missing.append("Create docs/sdd/spec/<date>-<feature>.md.")
    if target in (Phase.PLAN, Phase.EXECUTE, Phase.RESULT) and not _has_markdown(design_dir):
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
    return directory.is_dir() and any(directory.glob("*.md"))


def _phase_index(phase: Phase) -> int:
    return list(Phase).index(phase)


def _validate_state(state: dict[str, Any]) -> None:
    if state.get("schema_version") != SCHEMA_VERSION:
        raise TransitionError("Unsupported pipeline schema. Run the documented state migration.")
    if not isinstance(state.get("feature"), str) or not state["feature"]:
        raise TransitionError("Pipeline state is missing feature. Recreate state with initial_state().")
    try:
        Phase(state.get("phase"))
    except ValueError as exc:
        raise TransitionError("Pipeline state has an invalid phase. Restore a valid state snapshot.") from exc
    if not isinstance(state.get("approval"), dict):
        raise TransitionError("Pipeline state is missing approval records.")
    if not isinstance(state.get("task_retries"), dict):
        raise TransitionError("Pipeline state is missing task retry records.")

