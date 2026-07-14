from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness_core.state import Phase, PreflightError, TransitionError, initial_state, preflight_phase, record_retry, transition
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
    (tmp_path / "docs/sdd/spec/example.md").write_text("# Spec", encoding="utf-8")
    (tmp_path / "docs/sdd/design/arch/example.md").write_text("# Design", encoding="utf-8")
    (tmp_path / "docs/sdd/task/example/t-1.md").write_text("# Task", encoding="utf-8")
    (tmp_path / "docs/sdd/ORCHESTRATOR_STATE.md").write_text("# State", encoding="utf-8")
    state = _approved_plan_state()
    state["worktree"] = str(tmp_path)
    preflight_phase(tmp_path, state, Phase.EXECUTE)


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
