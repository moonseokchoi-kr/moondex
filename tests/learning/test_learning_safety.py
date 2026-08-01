from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness_core.learning import (
    benchmark_adoption_outcome,
    knowledge_sync_outcome,
    process,
    route_change,
)


FIXTURES = Path(__file__).parents[1] / "fixtures" / "learning"


def _write(root: Path, name: str, content: str = "pass\n") -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_project_target_applies_only_with_complete_local_records(tmp_path: Path) -> None:
    fixture = json.loads((FIXTURES / "project-change.json").read_text(encoding="utf-8"))
    _write(tmp_path, "src/service.py")

    result = route_change(root=tmp_path, **fixture)

    assert result["tier"] == "project"
    assert result["action"] == "APPLY"
    assert result["canonical_paths"] == ["src/service.py"]


@pytest.mark.parametrize("path", ["app/../scripts/verify.py", "/tmp/escape.py", "bad\0path.py"])
def test_invalid_targets_are_blocked_without_an_automatic_edit(tmp_path: Path, path: str) -> None:
    result = route_change(
        [path], root=tmp_path, protected_roots=("scripts",), train_improved=True,
        held_out_regressions=0, rollback_record={"id": "rollback"}, run_cap=1,
        recurrence_confirmed=True, critic_passed=True,
    )
    assert result["action"] == "BLOCKED"
    assert result["automatic_edit"] is False


def test_symlink_alias_and_broken_link_do_not_apply(tmp_path: Path) -> None:
    _write(tmp_path, "scripts/verify.py")
    (tmp_path / "linked").symlink_to("scripts", target_is_directory=True)
    alias = route_change(
        ["linked/verify.py"], root=tmp_path, protected_roots=("scripts",), train_improved=True,
        held_out_regressions=0, rollback_record={"id": "rollback"}, run_cap=1,
        recurrence_confirmed=True, critic_passed=True,
    )
    (tmp_path / "broken").symlink_to("missing", target_is_directory=True)
    broken = route_change(
        ["broken/file.py"], root=tmp_path, protected_roots=("scripts",), train_improved=True,
        held_out_regressions=0, rollback_record={"id": "rollback"}, run_cap=1,
        recurrence_confirmed=True, critic_passed=True,
    )
    assert alias["action"] == "PROPOSAL" and alias["tier"] == "harness"
    assert broken["action"] == "BLOCKED"


def test_local_additive_protection_is_proposal_only(tmp_path: Path) -> None:
    _write(tmp_path, "infra/release.py")
    result = route_change(
        ["infra/release.py"], root=tmp_path, protected_roots=(".harness", "infra"), train_improved=True,
        held_out_regressions=0, rollback_record={"id": "rollback"}, run_cap=1,
        recurrence_confirmed=True, critic_passed=True,
    )
    assert result["action"] == "PROPOSAL" and result["tier"] == "harness"


def test_supplied_policy_cannot_waive_t7_immutable_plugin_boundaries(tmp_path: Path) -> None:
    _write(tmp_path, ".codex-plugin/plugin.json", "{}")
    _write(tmp_path, "scripts/evil.py")
    result = route_change(
        ["scripts/evil.py"], root=tmp_path, protected_roots=("src",), train_improved=True,
        held_out_regressions=0, rollback_record={"id": "rollback"}, run_cap=1,
        recurrence_confirmed=True, critic_passed=True,
    )

    assert result["action"] == "PROPOSAL"
    assert result["tier"] == "harness"
    assert result["automatic_edit"] is False


def test_current_t7_policy_is_loaded_even_when_caller_omits_it(tmp_path: Path) -> None:
    _write(tmp_path, "src/service.py")
    result = route_change(
        ["src/service.py"], root=tmp_path, train_improved=True,
        held_out_regressions=0, rollback_record={"id": "rollback"}, run_cap=1,
        recurrence_confirmed=True, critic_passed=True,
    )
    assert result["action"] == "APPLY"


def test_caller_roots_cannot_omit_configured_t7_protected_root(tmp_path: Path) -> None:
    _write(tmp_path, ".harness/config.json", '{"security":{"protected_paths":["infra/release.py"]}}')
    _write(tmp_path, "infra/release.py")

    result = route_change(
        ["infra/release.py"], root=tmp_path, protected_roots=("src",), train_improved=True,
        held_out_regressions=0, rollback_record={"id": "rollback"}, run_cap=1,
        recurrence_confirmed=True, critic_passed=True,
    )

    assert result["tier"] == "harness"
    assert result["action"] == "PROPOSAL"
    assert result["automatic_edit"] is False


@pytest.mark.parametrize("paths", [
    ["src/service.py"],
    ["app/../scripts/verify.py"],
    ["/tmp/escape.py"],
    [],
])
def test_compatibility_routing_never_authorizes_an_edit_without_local_proof(paths: list[str]) -> None:
    result = route_change(
        paths,
        train_improved=True,
        held_out_regressions=0,
        rollback_record={"id": "rollback"},
        run_cap=1,
        recurrence_confirmed=True,
        critic_passed=True,
    )

    assert result["action"] == "PROPOSAL"
    assert result["automatic_edit"] is False
    assert result["compatibility_mode"] is True
    assert "T-7" in result["reason"]


@pytest.mark.parametrize("missing", ["rollback_record", "run_cap"])
def test_missing_apply_record_is_a_proposal(tmp_path: Path, missing: str) -> None:
    _write(tmp_path, "src/service.py")
    kwargs = {"rollback_record": {"id": "rollback"}, "run_cap": 1}
    kwargs[missing] = None
    result = route_change(
        ["src/service.py"], root=tmp_path, protected_roots=(".harness",), train_improved=True,
        held_out_regressions=0, recurrence_confirmed=True, critic_passed=True, **kwargs,
    )
    assert result["action"] == "PROPOSAL"
    assert missing in result["missing_requirements"]


def test_harness_adoption_requires_baseline_and_held_out_success() -> None:
    missing = json.loads((FIXTURES / "benchmark-missing.json").read_text(encoding="utf-8"))
    assert benchmark_adoption_outcome(**missing)["action"] == "PROPOSAL"
    assert benchmark_adoption_outcome(baseline_recorded=True, train_improved=True, held_out_regressions=1)["action"] == "PROPOSAL"
    assert benchmark_adoption_outcome(baseline_recorded=True, train_improved=True, held_out_regressions=0)["action"] == "ADOPT"


def test_cursor_is_idempotent_and_records_provenance() -> None:
    entries = [{"id": "one", "source": "test"}, {"id": "one", "source": "test"}, "bad"]
    result = process(entries, known_entry_ids={"one"})
    assert result["entries"] == []
    assert result["duplicate_entry_ids"] == ["one", "one"]
    assert result["next_cursor"] == 3


def test_unconfigured_sync_is_skipped() -> None:
    assert knowledge_sync_outcome({}) == {"status": "SKIPPED", "reason": "not configured"}
