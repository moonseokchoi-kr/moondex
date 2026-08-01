from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from harness_core.state import (
    Phase, PreflightError, TransitionError, controller_doctor, controller_resume,
    controller_start, controller_status, controller_transition, initial_state,
    preflight_phase, record_retry, transition,
)
from harness_core.state.storage import exclusive_lock
from harness_core.state.pipeline import check_owned_paths
from harness_core.state.storage import atomic_write_json, load_json
from harness_core.cli import main


def _approved_plan_state() -> dict:
    state = initial_state("example", Phase.PLAN)
    state["approval"] = {"spec": True, "design": True, "plan": True}
    return state


def test_transition_requires_adjacent_approved_phase(tmp_path: Path) -> None:
    state = initial_state("example")
    with pytest.raises(TransitionError, match="one approved phase"):
        transition(state, Phase.PLAN)
    with pytest.raises(TransitionError, match="spec approval"):
        transition(state, Phase.DESIGN)


def test_execute_requires_worktree() -> None:
    state = _approved_plan_state()
    with pytest.raises(TransitionError, match="isolated worktree"):
        transition(state, Phase.EXECUTE)


def test_execute_transition_records_worktree(tmp_path: Path) -> None:
    state = transition(_approved_plan_state(), Phase.EXECUTE, worktree=tmp_path)
    assert state["phase"] == "EXECUTE"
    assert state["worktree"] == str(tmp_path)


def test_retry_limit_records_escalation() -> None:
    state = initial_state("example")
    for _ in range(3):
        state = record_retry(state, "T-2")
    assert state["task_retries"]["T-2"] == 3
    assert state["escalations"] == ["T-2"]


def test_preflight_reports_missing_plan_evidence(tmp_path: Path) -> None:
    state = _approved_plan_state()
    with pytest.raises(PreflightError) as exc:
        preflight_phase(tmp_path, state, Phase.EXECUTE)
    assert "Create docs/sdd/spec" in str(exc.value)
    assert "Record explicit plan approval" not in str(exc.value)


def test_preflight_accepts_resume_evidence(tmp_path: Path) -> None:
    (tmp_path / "docs/sdd/spec").mkdir(parents=True)
    (tmp_path / "docs/sdd/design/arch").mkdir(parents=True)
    (tmp_path / "docs/sdd/task/example").mkdir(parents=True)
    (tmp_path / "docs/sdd/spec/2026-07-20-example.md").write_text("# Spec", encoding="utf-8")
    (tmp_path / "docs/sdd/design/arch/2026-07-20-example.md").write_text("# Design", encoding="utf-8")
    (tmp_path / "docs/sdd/task/example/t-1.md").write_text("# Task", encoding="utf-8")
    (tmp_path / "docs/sdd/ORCHESTRATOR_STATE.md").write_text("# State", encoding="utf-8")
    state = _approved_plan_state()
    state["worktree"] = str(tmp_path)
    preflight_phase(tmp_path, state, Phase.EXECUTE)


def _result_ready_fixture(tmp_path: Path, *, table: str, metadata: str | None = "- Feature: `portable`") -> dict:
    """Create the minimum feature-scoped EXECUTE fixture for RESULT gating."""

    (tmp_path / "docs/sdd/spec").mkdir(parents=True)
    (tmp_path / "docs/sdd/design/arch").mkdir(parents=True)
    task_dir = tmp_path / "docs/sdd/task/portable"
    task_dir.mkdir(parents=True)
    (tmp_path / "docs/sdd/spec/2026-07-20-portable.md").write_text("# spec", encoding="utf-8")
    (tmp_path / "docs/sdd/design/arch/2026-07-20-portable.md").write_text("# arch", encoding="utf-8")
    (task_dir / "2026-07-20-T-2-controller.md").write_text("# task", encoding="utf-8")
    metadata_section = "## Metadata\n\n" + (metadata or "") + "\n\n"
    (tmp_path / "docs/sdd/ORCHESTRATOR_STATE.md").write_text(
        table.replace("## Task status", metadata_section + "## Task status", 1), encoding="utf-8"
    )
    state = initial_state("portable", Phase.EXECUTE)
    state["worktree"] = str(tmp_path)
    state["approval"] = {"spec": True, "design": True, "plan": True}
    state_path = tmp_path / ".harness/state/pipeline.json"
    atomic_write_json(state_path, state)
    return state


def test_result_transition_rejects_stub_task_state(tmp_path: Path) -> None:
    _result_ready_fixture(
        tmp_path,
        table="""# Orchestrator State

## Task status

| ID | Wave | Status | Iteration | Role profile | Notes |
|---|---:|---|---:|---|---|
| T-2 | 1 | implementing | 1 | sdd-python-engineer | work started |
""",
    )
    before = (tmp_path / ".harness/state/pipeline.json").read_text(encoding="utf-8")

    result = controller_transition(
        tmp_path, feature="portable", expected=Phase.EXECUTE, target=Phase.RESULT
    )

    assert result["code"] == "BLOCKED_ARTIFACT"
    assert result["message"] == "feature tasks are not complete: T-2"
    assert (tmp_path / ".harness/state/pipeline.json").read_text(encoding="utf-8") == before


def test_result_transition_requires_complete_feature_scoped_task_evidence(tmp_path: Path) -> None:
    _result_ready_fixture(
        tmp_path,
        table="""# Orchestrator State

## Task status

| ID | Wave | Status | Iteration | Role profile | Notes |
|---|---:|---|---:|---|---|
| T-2 | 1 | complete | 2 | sdd-python-engineer | compliance, review, and tests passed |
""",
    )

    result = controller_transition(
        tmp_path, feature="portable", expected=Phase.EXECUTE, target=Phase.RESULT
    )

    assert result["code"] == "ACTION"
    assert result["state"]["phase"] == "RESULT"


def test_result_transition_rejects_duplicate_task_document_id_without_writing_state(tmp_path: Path) -> None:
    _result_ready_fixture(
        tmp_path,
        table="""# Orchestrator State

## Task status

| ID | Wave | Status | Iteration | Role profile | Notes |
|---|---:|---|---:|---|---|
| T-2 | 1 | complete | 2 | sdd-python-engineer | compliance, review, and tests passed |
""",
    )
    task_dir = tmp_path / "docs/sdd/task/portable"
    (task_dir / "2026-07-21-T-2-duplicate-controller.md").write_text("# duplicate task", encoding="utf-8")
    path = tmp_path / ".harness/state/pipeline.json"
    before = path.read_text(encoding="utf-8")

    result = controller_transition(
        tmp_path, feature="portable", expected=Phase.EXECUTE, target=Phase.RESULT
    )

    assert result["code"] == "BLOCKED_ARTIFACT"
    assert result["message"] == "feature task documents duplicate task ids: T-2"
    assert path.read_text(encoding="utf-8") == before


def test_result_transition_accepts_distinct_completed_task_document_ids(tmp_path: Path) -> None:
    _result_ready_fixture(
        tmp_path,
        table="""# Orchestrator State

## Task status

| ID | Wave | Status | Iteration | Role profile | Notes |
|---|---:|---|---:|---|---|
| T-2 | 1 | complete | 2 | sdd-python-engineer | compliance, review, and tests passed |
| T-3 | 1 | complete | 1 | sdd-python-engineer | compliance, review, and tests passed |
""",
    )
    task_dir = tmp_path / "docs/sdd/task/portable"
    (task_dir / "2026-07-21-T-3-next-controller.md").write_text("# next task", encoding="utf-8")

    result = controller_transition(
        tmp_path, feature="portable", expected=Phase.EXECUTE, target=Phase.RESULT
    )

    assert result["code"] == "ACTION"
    assert result["state"]["phase"] == "RESULT"


@pytest.mark.parametrize("metadata", [
    None,
    "- Feature: `other-feature`",
    "- Feature: `portable`\n- Feature: `portable`",
])
def test_result_transition_fails_closed_when_state_feature_metadata_is_not_exact(
    tmp_path: Path, metadata: str | None
) -> None:
    """A foreign state with the same T-2 cannot complete portable."""

    _result_ready_fixture(
        tmp_path,
        metadata=metadata,
        table="""# Orchestrator State

## Task status

| ID | Wave | Status | Iteration | Role profile | Notes |
|---|---:|---|---:|---|---|
| T-2 | 1 | complete | 2 | sdd-python-engineer | compliance, review, and tests passed |
""",
    )
    before = (tmp_path / ".harness/state/pipeline.json").read_text(encoding="utf-8")

    result = controller_transition(
        tmp_path, feature="portable", expected=Phase.EXECUTE, target=Phase.RESULT
    )

    assert result["code"] == "BLOCKED_ARTIFACT"
    assert result["message"].startswith("task completion evidence is invalid:")
    assert (tmp_path / ".harness/state/pipeline.json").read_text(encoding="utf-8") == before


@pytest.mark.parametrize("table", [
    "# Orchestrator State\n",
    """# Orchestrator State

## Task status

| ID | Wave | Status | Iteration | Role profile | Notes |
|---|---:|---|---:|---|---|
| T-2 | 1 | complete | 1 | engineer | passed |
| T-2 | 1 | complete | 2 | engineer | passed |
""",
])
def test_result_transition_fails_closed_on_malformed_or_ambiguous_task_state(tmp_path: Path, table: str) -> None:
    _result_ready_fixture(tmp_path, table=table)
    result = controller_transition(
        tmp_path, feature="portable", expected=Phase.EXECUTE, target=Phase.RESULT
    )
    assert result["code"] == "BLOCKED_ARTIFACT"
    assert result["message"].startswith("task completion evidence is invalid:")


def test_atomic_storage_keeps_valid_json(tmp_path: Path) -> None:
    path = tmp_path / "state/pipeline.json"
    atomic_write_json(path, {"schema_version": 1})
    assert load_json(path) == {"schema_version": 1}
    assert json.loads(path.read_text(encoding="utf-8")) == {"schema_version": 1}


def test_ownership_check_finds_outside_change(tmp_path: Path) -> None:
    owned = tmp_path / "owned"
    outside = tmp_path / "outside.txt"
    owned.mkdir()
    assert check_owned_paths([owned / "a.py", outside], [owned]) == [outside]


def test_cli_preflight_reports_missing_runtime_state(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["preflight", "phase", "--project-root", str(tmp_path), "--target-phase", "EXECUTE"]) == 2
    assert "PREFLIGHT_FAILED: state not found" in capsys.readouterr().out


def test_start_is_idempotent_and_resume_is_read_only(tmp_path: Path) -> None:
    created = controller_start(tmp_path, "portable")
    path = tmp_path / ".harness/state/pipeline.json"
    before = path.read_text(encoding="utf-8")
    assert created["code"] == "INITIALIZED"
    assert controller_start(tmp_path, "portable")["code"] == "BLOCKED_ARTIFACT"
    assert controller_resume(tmp_path, "portable")["code"] == "BLOCKED_ARTIFACT"
    assert path.read_text(encoding="utf-8") == before


def test_clean_environment_has_identical_controller_decisions(tmp_path: Path) -> None:
    command = ["python3", "-m", "harness_core", "state", "--project-root", str(tmp_path), "start", "portable"]
    clean = os.environ.copy()
    clean.pop("HARNESS_HOOKS", None)
    clean.pop("CODEX_PLUGIN_ROOT", None)
    first = subprocess.run(command, text=True, capture_output=True, check=True, env=clean)
    arbitrary = {**clean, "HARNESS_HOOKS": "/not/a/hook", "CODEX_PLUGIN_ROOT": "/not/a/plugin"}
    second = subprocess.run(command, text=True, capture_output=True, check=True, env=arbitrary)
    assert json.loads(first.stdout)["code"] == "INITIALIZED"
    assert json.loads(second.stdout)["code"] == "BLOCKED_ARTIFACT"
    statuses = [
        subprocess.run(["python3", "-m", "harness_core", "state", "--project-root", str(tmp_path), "status", "portable"], text=True, capture_output=True, check=True, env=env)
        for env in (clean, arbitrary)
    ]
    assert [json.loads(result.stdout)["code"] for result in statuses] == ["BLOCKED_ARTIFACT", "BLOCKED_ARTIFACT"]


def test_status_requires_explicit_approval_and_transition_requires_artifacts(tmp_path: Path) -> None:
    controller_start(tmp_path, "portable")
    assert controller_status(tmp_path, "portable")["code"] == "BLOCKED_ARTIFACT"
    (tmp_path / "docs/sdd/spec").mkdir(parents=True)
    (tmp_path / "docs/sdd/spec/2026-07-20-portable.md").write_text("# spec", encoding="utf-8")
    assert controller_status(tmp_path, "portable")["code"] == "WAITING_USER"
    blocked = controller_transition(tmp_path, feature="portable", expected=Phase.SPEC, target=Phase.DESIGN)
    assert blocked["code"] == "BLOCKED_APPROVAL"
    advanced = controller_transition(tmp_path, feature="portable", expected=Phase.SPEC, target=Phase.DESIGN, approve="spec")
    assert advanced["code"] == "ACTION"
    assert advanced["state"]["phase"] == "DESIGN"


def test_feature_scoped_spec_gate_rejects_other_feature_and_accepts_target(tmp_path: Path) -> None:
    """A sibling feature's spec cannot authorize this feature's transition."""

    controller_start(tmp_path, "portable")
    spec_dir = tmp_path / "docs/sdd/spec"
    spec_dir.mkdir(parents=True)
    (spec_dir / "2026-07-20-other-feature.md").write_text("# Other", encoding="utf-8")

    blocked = controller_status(tmp_path, "portable")
    assert blocked["code"] == "BLOCKED_ARTIFACT"
    assert blocked["message"] == "spec artifact is missing"

    # The date prefix is intentionally not parsed: existing valid date formats
    # remain compatible, while the feature suffix remains mandatory.
    (spec_dir / "legacy-date-portable.md").write_text("# Portable", encoding="utf-8")
    assert controller_status(tmp_path, "portable")["code"] == "WAITING_USER"


def test_feature_scoped_architecture_gate_rejects_other_feature_and_accepts_target(tmp_path: Path) -> None:
    """A sibling feature's architecture cannot advance a target feature."""

    controller_start(tmp_path, "portable")
    spec_dir = tmp_path / "docs/sdd/spec"
    arch_dir = tmp_path / "docs/sdd/design/arch"
    spec_dir.mkdir(parents=True)
    arch_dir.mkdir(parents=True)
    (spec_dir / "2026-07-20-portable.md").write_text("# Portable", encoding="utf-8")
    assert controller_transition(
        tmp_path, feature="portable", expected=Phase.SPEC, target=Phase.DESIGN, approve="spec"
    )["code"] == "ACTION"
    (arch_dir / "2026-07-20-other-feature.md").write_text("# Other", encoding="utf-8")

    blocked = controller_status(tmp_path, "portable")
    assert blocked["code"] == "BLOCKED_ARTIFACT"
    assert blocked["message"] == "architecture artifact is missing"

    (arch_dir / "legacy-date-portable.md").write_text("# Portable", encoding="utf-8")
    assert controller_status(tmp_path, "portable")["code"] == "WAITING_USER"


@pytest.mark.parametrize("feature", ["port*", "port?", "port[able]", "../portable", "portable/next", "Portable", "portable_name", ""])
def test_controller_rejects_non_literal_feature_slugs_without_writing_state(tmp_path: Path, feature: str) -> None:
    """Every controller command rejects metacharacters before artifact lookup."""

    state_dir = tmp_path / ".harness/state"
    state_dir.mkdir(parents=True)
    path = state_dir / "pipeline.json"
    original = initial_state("portable")
    path.write_text(json.dumps(original), encoding="utf-8")
    spec_dir = tmp_path / "docs/sdd/spec"
    spec_dir.mkdir(parents=True)
    (spec_dir / "2026-07-20-portable.md").write_text("# sibling", encoding="utf-8")
    before = path.read_text(encoding="utf-8")

    results = [
        controller_start(tmp_path, feature),
        controller_status(tmp_path, feature),
        controller_resume(tmp_path, feature),
        controller_doctor(tmp_path, feature),
        controller_transition(tmp_path, feature=feature, expected=Phase.SPEC, target=Phase.DESIGN),
    ]

    assert all(result["code"] == "STATE_INVALID" for result in results)
    assert all("lowercase kebab-case" in result["message"] for result in results)
    assert path.read_text(encoding="utf-8") == before


@pytest.mark.parametrize("feature", ["portable", "port7", "codex-harness-parity"])
def test_literal_feature_slug_matches_only_its_exact_document_suffix(tmp_path: Path, feature: str) -> None:
    controller_start(tmp_path, feature)
    spec_dir = tmp_path / "docs/sdd/spec"
    spec_dir.mkdir(parents=True)
    (spec_dir / f"2026-07-20-{feature}.md").write_text("# Target", encoding="utf-8")
    (spec_dir / f"2026-07-20-{feature}-other.md").write_text("# Other", encoding="utf-8")

    assert controller_status(tmp_path, feature)["code"] == "WAITING_USER"


def test_transition_cannot_preregister_a_later_phase_approval(tmp_path: Path) -> None:
    controller_start(tmp_path, "portable")
    (tmp_path / "docs/sdd/spec").mkdir(parents=True)
    (tmp_path / "docs/sdd/spec/2026-07-20-portable.md").write_text("# spec", encoding="utf-8")
    path = tmp_path / ".harness/state/pipeline.json"
    before = path.read_text(encoding="utf-8")

    result = controller_transition(
        tmp_path, feature="portable", expected=Phase.SPEC, target=Phase.DESIGN, approve="plan"
    )

    assert result["code"] == "STATE_INVALID"
    assert path.read_text(encoding="utf-8") == before
    assert controller_transition(
        tmp_path, feature="portable", expected=Phase.SPEC, target=Phase.DESIGN, approve="spec"
    )["state"]["approval"]["plan"] is False


@pytest.mark.parametrize("approval", [
    {"spec": True, "design": False, "plan": "yes"},
    {"spec": True, "design": False},
    {"spec": True, "design": False, "plan": False, "unexpected": False},
])
def test_malformed_approval_schema_is_invalid_and_never_written(tmp_path: Path, approval: dict) -> None:
    controller_start(tmp_path, "portable")
    path = tmp_path / ".harness/state/pipeline.json"
    malformed = initial_state("portable")
    malformed["approval"] = approval
    path.write_text(json.dumps(malformed), encoding="utf-8")
    before = path.read_text(encoding="utf-8")

    result = controller_transition(
        tmp_path, feature="portable", expected=Phase.SPEC, target=Phase.DESIGN, approve="spec"
    )

    assert result["code"] == "STATE_INVALID"
    assert path.read_text(encoding="utf-8") == before


def test_corruption_busy_and_ambiguous_are_non_destructive(tmp_path: Path) -> None:
    path = tmp_path / ".harness/state/pipeline.json"
    path.parent.mkdir(parents=True)
    path.write_text("{broken", encoding="utf-8")
    assert controller_status(tmp_path)["code"] == "STATE_INVALID"
    assert path.read_text(encoding="utf-8") == "{broken"
    path.write_text(json.dumps(initial_state("one")), encoding="utf-8")
    other = tmp_path / ".harness/state/pipelines/two.json"
    other.parent.mkdir(parents=True)
    other.write_text(json.dumps(initial_state("two")), encoding="utf-8")
    assert controller_status(tmp_path)["code"] == "AMBIGUOUS_FEATURE"
    with exclusive_lock(tmp_path / ".harness/state/pipeline.lock"):
        assert controller_start(tmp_path, "three")["code"] == "STATE_BUSY"


def test_retry_escalation_and_doctor_are_durable_and_advisory(tmp_path: Path) -> None:
    controller_start(tmp_path, "portable")
    for retry in range(1, 4):
        result = controller_transition(tmp_path, feature="portable", expected=Phase.SPEC, target=Phase.SPEC, retry_task="T-2")
        assert result["code"] == ("ESCALATED" if retry == 3 else "ACTION")
    assert controller_doctor(tmp_path, "portable")["code"] == "ADVISORY_UNAVAILABLE"
