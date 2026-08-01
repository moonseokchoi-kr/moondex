"""Clean-process controller-first resume contract for active SDD instructions."""

import json
import argparse
import importlib.util
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import sys
import pytest


ROOT = Path(__file__).resolve().parents[1]
SDD_SKILL = ROOT / "skills/sdd/SKILL.md"
EXECUTION_SKILL = ROOT / "skills/sdd-orchestrator/SKILL.md"
RESULT_ACTION = ROOT / "skills/sdd-orchestrator/scripts/result-action.py"
MOONDEX_RUNTIME = ROOT / "skills/sdd/runtime/moondex-runtime.py"
FIXTURES = ROOT / "tests/fixtures/sdd_resume"
AUTHORITY_COMMAND = re.compile(
    r'<!-- authority-transition (?P<expected>[A-Z]+)->(?P<target>[A-Z]+) '
    r'owner="(?P<owner>[^"]+)" -->\n```bash\n(?P<command>[^\n]+)\n```'
)
RESULT_RESUME = re.compile(
    r'<!-- authority-resume phase="RESULT" owner="execution orchestrator" '
    r'transition="forbidden" action="generate-result-report" -->'
)


def _tree_snapshot(root: Path) -> list[tuple[str, int, bytes | str]]:
    if not root.exists():
        return []
    snapshot = []
    for path in [root, *sorted(root.rglob("*"))]:
        relative = "." if path == root else path.relative_to(root).as_posix()
        mode = stat.S_IMODE(path.lstat().st_mode)
        payload: bytes | str = os.readlink(path) if path.is_symlink() else (path.read_bytes() if path.is_file() else "dir")
        snapshot.append((relative, mode, payload))
    return snapshot


def _compound_fixture(root: Path) -> None:
    root.mkdir()
    (root / "CLAUDE.md").write_text("# Compound rules\nUse wiki sources only.\n", encoding="utf-8")
    (root / "wiki").mkdir()
    (root / "wiki/index.md").write_text("# Index\n", encoding="utf-8")
    (root / "wiki/log.md").write_text("# Log\n", encoding="utf-8")
    lock = root / ".moondex-sdd-sync.lock"
    lock.write_bytes(b"")
    lock.chmod(0o600)


def _configure_sync(project: Path, compound_root: Path, destination: str = "organization-compound") -> None:
    (project / ".harness/config.json").write_text(json.dumps({
        "schema_version": 1,
        "knowledge_sync": {
            "enabled": True, "compound_root": str(compound_root),
            "destination": destination,
            "credential_source": "explicit-local-config", "retention_policy": "append-only",
        },
    }), encoding="utf-8")


def _state(project: Path, *args: str) -> dict[str, object]:
    env = os.environ.copy()
    env.pop("HARNESS_HOOKS", None)
    env.pop("CODEX_PLUGIN_ROOT", None)
    result = subprocess.run(
        [sys.executable, "-m", "harness_core", "state", "--project-root", str(project), *args],
        cwd=ROOT, env=env, check=False, text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _run_active_coordinator_transition(
    project: Path, *, expected: str, target: str, worktree: Path | None = None,
    skill: Path = SDD_SKILL, owner: str = "SDD coordinator",
    feature: str = "authority-flow",
) -> dict[str, object]:
    """Execute the transition command published by the active SDD reference."""

    matches = [
        match
        for match in AUTHORITY_COMMAND.finditer(skill.read_text(encoding="utf-8"))
        if match.group("expected") == expected and match.group("target") == target
    ]
    assert len(matches) == 1
    match = matches[0]
    assert match.group("owner") == owner
    command = match.group("command")
    command = command.replace("<moondex-runtime>", str(MOONDEX_RUNTIME))
    command = command.replace("<project-root>", str(project))
    command = command.replace("<feature>", feature)
    if worktree is not None:
        command = command.replace("<worktree>", str(worktree))
    argv = shlex.split(command)
    assert argv[:3] == ["python3", str(MOONDEX_RUNTIME), "state"]
    argv[0] = sys.executable
    env = os.environ.copy()
    env.pop("HARNESS_HOOKS", None)
    env.pop("CODEX_PLUGIN_ROOT", None)
    result = subprocess.run(
        argv, cwd=ROOT, env=env, check=False, text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _run_result_action(
    project: Path, *, feature: str, controller_fixture: str | None = None, evidence_fixture: str,
    evidence_value: dict[str, object] | None = None,
    controller_value: dict[str, object] | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict[str, object] | None]:
    inputs = project / ".harness/result-input"
    inputs.mkdir(parents=True, exist_ok=True)
    controller = inputs / "controller.json"
    evidence = inputs / "evidence.json"
    if controller_value is not None:
        controller.write_text(json.dumps(controller_value), encoding="utf-8")
    elif controller_fixture is None:
        controller.write_text(json.dumps(_state(project, "resume", feature)), encoding="utf-8")
    else:
        shutil.copyfile(FIXTURES / controller_fixture, controller)
    if evidence_value is None:
        shutil.copyfile(FIXTURES / evidence_fixture, evidence)
    else:
        evidence.write_text(json.dumps(evidence_value), encoding="utf-8")
    env = os.environ.copy()
    env.pop("HARNESS_HOOKS", None)
    env.pop("CODEX_PLUGIN_ROOT", None)
    result = subprocess.run(
        [
            sys.executable,
            str(RESULT_ACTION),
            "--project-root", str(project),
            "--feature", feature,
            "--controller-result", str(controller),
            "--evidence", str(evidence),
            "--result-date", "2026-07-23",
        ],
        cwd=ROOT,
        env=env,
        check=False,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout) if result.stdout.strip().startswith("{") else None
    return result, payload


def _reach_result(project: Path, feature: str) -> Path:
    assert _state(project, "start", feature)["state"]["phase"] == "SPEC"
    spec_dir = project / "docs/sdd/spec"
    spec_dir.mkdir(parents=True, exist_ok=True)
    (spec_dir / f"2026-07-23-{feature}.md").write_text("# Spec\n", encoding="utf-8")
    assert _run_active_coordinator_transition(
        project, expected="SPEC", target="DESIGN", feature=feature,
    )["state"]["phase"] == "DESIGN"
    arch_dir = project / "docs/sdd/design/arch"
    arch_dir.mkdir(parents=True, exist_ok=True)
    (arch_dir / f"2026-07-23-{feature}.md").write_text("# Architecture\n", encoding="utf-8")
    assert _run_active_coordinator_transition(
        project, expected="DESIGN", target="PLAN", feature=feature,
    )["state"]["phase"] == "PLAN"
    task_dir = project / "docs/sdd/task" / feature
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "2026-07-23-T-1-flow.md").write_text("# Task\n", encoding="utf-8")
    orchestrator_state = project / "docs/sdd/ORCHESTRATOR_STATE.md"
    orchestrator_state.write_text("# Orchestrator State\n", encoding="utf-8")
    worktree = project / "worktrees" / feature
    worktree.mkdir(parents=True)
    assert _run_active_coordinator_transition(
        project, expected="PLAN", target="EXECUTE", worktree=worktree, feature=feature,
    )["state"]["phase"] == "EXECUTE"
    orchestrator_state.write_text(
        f"""# Orchestrator State

- Feature: `{feature}`

## Task status
| ID | Wave | Status | Iteration | Role profile | Notes |
|---|---|---|---|---|---|
| T-1 | 1 | complete | 1 | sdd-implementer | compliance, review, and test passed |
""",
        encoding="utf-8",
    )
    assert _run_active_coordinator_transition(
        project, expected="EXECUTE", target="RESULT", skill=EXECUTION_SKILL,
        owner="execution orchestrator", feature=feature,
    )["state"]["phase"] == "RESULT"
    return project / ".harness/state/pipeline.json"


def test_start_and_normal_turn_resume_are_host_independent(tmp_path: Path) -> None:
    started = _state(tmp_path, "start", "controller-resume")
    assert started["code"] == "INITIALIZED"
    status = _state(tmp_path, "status", "controller-resume")
    resumed = _state(tmp_path, "resume", "controller-resume")
    assert status == resumed
    assert resumed["code"] == "BLOCKED_ARTIFACT"
    assert _state(tmp_path, "start", "controller-resume") == status


def test_missing_optional_local_integration_is_advisory(tmp_path: Path) -> None:
    _state(tmp_path, "start", "controller-resume")
    doctor = _state(tmp_path, "doctor", "controller-resume")
    assert doctor["code"] == "ADVISORY_UNAVAILABLE"
    assert "optional local" in str(doctor["message"])


def test_resume_waits_for_immediate_approval_and_only_transition_advances(
    tmp_path: Path,
) -> None:
    """A normal re-entry observes the gate; only the explicit transition writes."""

    _state(tmp_path, "start", "controller-resume")
    spec_dir = tmp_path / "docs/sdd/spec"
    spec_dir.mkdir(parents=True)
    (spec_dir / "2026-07-22-controller-resume.md").write_text(
        "# Controller resume spec\n", encoding="utf-8"
    )

    state_path = tmp_path / ".harness/state/pipeline.json"
    before = state_path.read_bytes()
    status = _state(tmp_path, "status", "controller-resume")
    resumed = _state(tmp_path, "resume", "controller-resume")
    assert status == resumed
    assert status["code"] == "WAITING_USER"
    assert state_path.read_bytes() == before

    blocked = _state(
        tmp_path,
        "transition",
        "--feature",
        "controller-resume",
        "--expected",
        "SPEC",
        "--target",
        "DESIGN",
    )
    assert blocked["code"] == "BLOCKED_APPROVAL"
    assert state_path.read_bytes() == before

    advanced = _state(
        tmp_path,
        "transition",
        "--feature",
        "controller-resume",
        "--expected",
        "SPEC",
        "--target",
        "DESIGN",
        "--approve",
        "spec",
    )
    assert advanced["code"] == "ACTION"
    assert advanced["state"]["phase"] == "DESIGN"
    assert state_path.read_bytes() != before


def test_active_reference_drives_approved_flow_and_hands_authority_to_execute(
    tmp_path: Path,
) -> None:
    """Follow only active-reference transition commands through the handoff."""

    feature = "authority-flow"
    assert _state(tmp_path, "start", feature)["state"]["phase"] == "SPEC"

    spec_dir = tmp_path / "docs/sdd/spec"
    spec_dir.mkdir(parents=True)
    (spec_dir / "2026-07-23-authority-flow.md").write_text("# Spec\n", encoding="utf-8")
    assert _state(tmp_path, "status", feature)["code"] == "WAITING_USER"
    assert _state(tmp_path, "resume", feature)["state"]["phase"] == "SPEC"
    design = _run_active_coordinator_transition(tmp_path, expected="SPEC", target="DESIGN")
    assert design["state"]["phase"] == "DESIGN"

    arch_dir = tmp_path / "docs/sdd/design/arch"
    arch_dir.mkdir(parents=True)
    (arch_dir / "2026-07-23-authority-flow.md").write_text("# Architecture\n", encoding="utf-8")
    assert _state(tmp_path, "status", feature)["code"] == "WAITING_USER"
    plan = _run_active_coordinator_transition(tmp_path, expected="DESIGN", target="PLAN")
    assert plan["state"]["phase"] == "PLAN"

    task_dir = tmp_path / "docs/sdd/task/authority-flow"
    task_dir.mkdir(parents=True)
    (task_dir / "2026-07-23-T-1-flow.md").write_text("# Task\n", encoding="utf-8")
    orchestrator_state = tmp_path / "docs/sdd/ORCHESTRATOR_STATE.md"
    orchestrator_state.write_text("# Orchestrator State\n", encoding="utf-8")
    worktree = tmp_path / "worktrees/authority-flow"
    worktree.mkdir(parents=True)
    plan_resume = _state(tmp_path, "resume", feature)
    assert plan_resume["code"] == "BLOCKED_ARTIFACT"
    assert "worktree" in str(plan_resume["message"])
    execute = _run_active_coordinator_transition(
        tmp_path, expected="PLAN", target="EXECUTE", worktree=worktree,
    )
    assert execute["state"]["phase"] == "EXECUTE"

    sdd = SDD_SKILL.read_text(encoding="utf-8")
    execution = (ROOT / "skills/sdd-orchestrator/SKILL.md").read_text(encoding="utf-8")
    assert "authority handoff: SDD coordinator -> execution orchestrator" in sdd
    assert "authority handoff: SDD coordinator -> execution orchestrator" in execution


def test_active_reference_resumes_result_without_a_second_transition(tmp_path: Path) -> None:
    """Recover an interrupted RESULT action through the published active path."""

    feature = "result-resume"
    state_path = _reach_result(tmp_path, feature)
    result_state = state_path.read_bytes()
    status = _state(tmp_path, "status", feature)
    resumed = _state(tmp_path, "resume", feature)
    assert status == resumed
    assert resumed["code"] == "ACTION"
    assert resumed["state"]["phase"] == "RESULT"
    assert "result artifact" in str(resumed["message"])
    assert RESULT_RESUME.search(EXECUTION_SKILL.read_text(encoding="utf-8"))

    process, outcome = _run_result_action(
        tmp_path,
        feature=feature,
        evidence_fixture="result-resume-evidence.json",
    )
    assert process.returncode == 0, process.stderr
    assert outcome and outcome["Status"] == "DONE"
    assert outcome["Verdict"] == "SYNC_SKIPPED"
    assert outcome["transition_calls"] == 0
    assert outcome["worker_dispatches"] == 0
    assert state_path.read_bytes() == result_state
    report = (tmp_path / "docs/sdd/result/2026-07-23-result-resume.md").read_text(encoding="utf-8")
    assert "fixture-secret-must-not-render" not in report
    assert "fixture-api-secret" not in report
    assert "fixture-argv-secret" not in report
    assert "[REDACTED]" in report
    terminal = _state(tmp_path, "resume", feature)
    assert terminal["code"] == "COMPLETE"
    assert terminal["state"]["phase"] == "RESULT"


def test_configured_result_action_applies_redacted_temp_sync(tmp_path: Path) -> None:
    feature = "result-sync"
    state_path = _reach_result(tmp_path, feature)
    state_bytes = state_path.read_bytes()
    compound_root = tmp_path.parent / f"{tmp_path.name}-compound"
    _compound_fixture(compound_root)
    config = tmp_path / ".harness/config.json"
    config.write_text(
        json.dumps({
            "schema_version": 1,
            "knowledge_sync": {
                "enabled": True,
                "compound_root": str(compound_root),
                "destination": "organization-compound",
                "credential_source": "explicit-local-config",
                "retention_policy": "append-only",
            },
        }),
        encoding="utf-8",
    )

    process, outcome = _run_result_action(
        tmp_path,
        feature=feature,
        evidence_fixture="result-sync-evidence.json",
    )
    assert process.returncode == 0, process.stderr
    assert outcome and outcome["Verdict"] == "SYNC_APPLIED"
    assert outcome["transition_calls"] == outcome["worker_dispatches"] == 0
    assert state_path.read_bytes() == state_bytes
    run_id = outcome["sync"]["run_id"]
    sync_path = compound_root / f"raw/projects/result-sync/sdd-2026-07-23-{run_id}/snapshot.json"
    assert sync_path.is_file()
    sync_report = sync_path.read_text(encoding="utf-8")
    assert "configured-secret-must-not-render" not in sync_report
    assert "configured-token-secret" not in sync_report
    assert "explicit-local-config" in sync_report
    assert "[REDACTED]" in sync_report
    result_path = tmp_path / "docs/sdd/result/2026-07-23-result-sync.md"
    assert "SYNC_APPLIED" in result_path.read_text(encoding="utf-8")
    assert "SDD-SYNC:result-sync" in (compound_root / "wiki/organization-compound.md").read_text(encoding="utf-8")
    assert "SDD-SYNC:result-sync" in (compound_root / "wiki/index.md").read_text(encoding="utf-8")
    assert "[SDD-SYNC]" in (compound_root / "wiki/log.md").read_text(encoding="utf-8")
    assert (tmp_path / "docs/sdd/result/2026-07-23-result-sync-compound-sync.md").is_file()
    assert _state(tmp_path, "resume", feature)["code"] == "COMPLETE"


@pytest.mark.parametrize(
    "destination", ["wiki/index.md", "wiki/log.md", "wiki/Index.md", "wiki/LOG.md"]
)
def test_reserved_index_or_log_destination_is_blocked_without_mutation(
    tmp_path: Path, destination: str,
) -> None:
    feature = "result-sync"
    state_path = _reach_result(tmp_path, feature)
    compound = tmp_path.parent / f"{tmp_path.name}-compound"
    _compound_fixture(compound)
    _configure_sync(tmp_path, compound, destination)
    action = _state(tmp_path, "resume", feature)
    inputs = tmp_path / ".harness/result-input"
    inputs.mkdir(parents=True)
    (inputs / "controller.json").write_text(json.dumps(action), encoding="utf-8")
    shutil.copyfile(FIXTURES / "result-sync-evidence.json", inputs / "evidence.json")
    project_before = _tree_snapshot(tmp_path)
    compound_before = _tree_snapshot(compound)
    state_before = state_path.read_bytes()
    process, payload = _run_result_action(
        tmp_path, feature=feature, evidence_fixture="result-sync-evidence.json",
        controller_value=action,
    )
    assert process.returncode == 2
    assert payload and payload["Status"] == "BLOCKED"
    assert "reserved output role" in str(payload["error"])
    assert _tree_snapshot(tmp_path) == project_before
    assert _tree_snapshot(compound) == compound_before
    assert state_path.read_bytes() == state_before


@pytest.mark.parametrize("alias_kind", ["hardlink", "symlink", "unicode-normalized"])
def test_destination_filesystem_aliases_are_blocked_without_mutation(
    tmp_path: Path, alias_kind: str,
) -> None:
    feature = "result-sync"
    state_path = _reach_result(tmp_path, feature)
    compound = tmp_path.parent / f"{tmp_path.name}-compound"
    _compound_fixture(compound)
    index = compound / "wiki/index.md"
    if alias_kind == "unicode-normalized":
        existing = compound / "wiki/caf\u00e9.md"
        os.link(index, existing)
        destination = "wiki/cafe\u0301.md"
    else:
        existing = compound / f"wiki/{alias_kind}-alias.md"
        if alias_kind == "hardlink":
            os.link(index, existing)
        else:
            existing.symlink_to(index)
        destination = f"wiki/{alias_kind}-alias.md"
    _configure_sync(tmp_path, compound, destination)
    action = _state(tmp_path, "resume", feature)
    inputs = tmp_path / ".harness/result-input"
    inputs.mkdir(parents=True)
    (inputs / "controller.json").write_text(json.dumps(action), encoding="utf-8")
    shutil.copyfile(FIXTURES / "result-sync-evidence.json", inputs / "evidence.json")
    project_before = _tree_snapshot(tmp_path)
    compound_before = _tree_snapshot(compound)
    state_before = state_path.read_bytes()
    process, payload = _run_result_action(
        tmp_path, feature=feature, evidence_fixture="result-sync-evidence.json",
        controller_value=action,
    )
    assert process.returncode == 2
    assert payload and payload["Status"] == "BLOCKED"
    assert _tree_snapshot(tmp_path) == project_before
    assert _tree_snapshot(compound) == compound_before
    assert state_path.read_bytes() == state_before


@pytest.mark.parametrize("alias_pair", ["index-log", "snapshot-index", "project-result-report"])
def test_non_destination_output_role_aliases_are_blocked_without_mutation(
    tmp_path: Path, alias_pair: str,
) -> None:
    feature = "result-sync"
    state_path = _reach_result(tmp_path, feature)
    compound = tmp_path.parent / f"{tmp_path.name}-compound"
    _compound_fixture(compound)
    _configure_sync(tmp_path, compound)
    action = _state(tmp_path, "resume", feature)
    evidence = json.loads((FIXTURES / "result-sync-evidence.json").read_text(encoding="utf-8"))
    if alias_pair == "index-log":
        log = compound / "wiki/log.md"
        log.unlink()
        os.link(compound / "wiki/index.md", log)
    elif alias_pair == "snapshot-index":
        run_id = __import__("hashlib").sha256(
            evidence["completion_identity"].encode("utf-8")
        ).hexdigest()[:12]
        snapshot = compound / f"raw/projects/{feature}/sdd-2026-07-23-{run_id}/snapshot.json"
        snapshot.parent.mkdir(parents=True)
        os.link(compound / "wiki/index.md", snapshot)
    else:
        result_directory = tmp_path / "docs/sdd/result"
        result_directory.mkdir(parents=True, exist_ok=True)
        result = result_directory / "2026-07-23-result-sync.md"
        report = result_directory / "2026-07-23-result-sync-compound-sync.md"
        result.write_text("aliased project output\n", encoding="utf-8")
        os.link(result, report)
    inputs = tmp_path / ".harness/result-input"
    inputs.mkdir(parents=True)
    (inputs / "controller.json").write_text(json.dumps(action), encoding="utf-8")
    (inputs / "evidence.json").write_text(json.dumps(evidence), encoding="utf-8")
    project_before = _tree_snapshot(tmp_path)
    compound_before = _tree_snapshot(compound)
    state_before = state_path.read_bytes()
    process, payload = _run_result_action(
        tmp_path, feature=feature, evidence_fixture="result-sync-evidence.json",
        evidence_value=evidence, controller_value=action,
    )
    assert process.returncode == 2
    assert payload and payload["Status"] == "BLOCKED"
    assert "alias" in str(payload["error"])
    assert _tree_snapshot(tmp_path) == project_before
    assert _tree_snapshot(compound) == compound_before
    assert state_path.read_bytes() == state_before


def test_same_day_distinct_identity_is_append_only(tmp_path: Path) -> None:
    compound = tmp_path / "compound"
    _compound_fixture(compound)
    run_ids = []
    for name, identity in (("first", "shared-completion:2026-07-23"), ("second", "distinct-completion:2026-07-23")):
        project = tmp_path / name
        project.mkdir()
        _reach_result(project, "result-sync")
        _configure_sync(project, compound)
        evidence = json.loads((FIXTURES / "result-sync-evidence.json").read_text(encoding="utf-8"))
        evidence["completion_identity"] = identity
        process, outcome = _run_result_action(
            project, feature="result-sync", evidence_fixture="result-sync-evidence.json",
            evidence_value=evidence,
        )
        assert process.returncode == 0, process.stdout
        assert outcome and outcome["Verdict"] == "SYNC_APPLIED"
        run_ids.append(outcome["sync"]["run_id"])
    assert run_ids[1] != run_ids[0]
    snapshots = sorted((compound / "raw/projects/result-sync").glob("sdd-2026-07-23-*/snapshot.json"))
    assert len(snapshots) == 2
    page = (compound / "wiki/organization-compound.md").read_text(encoding="utf-8")
    assert page.count(f"SDD-SYNC:result-sync:{run_ids[0]}") == 1
    assert page.count(f"SDD-SYNC:result-sync:{run_ids[1]}") == 1


def test_concurrent_compound_syncs_are_serialized_without_lost_updates(tmp_path: Path) -> None:
    feature = "result-sync"
    compound = tmp_path / "compound"
    _compound_fixture(compound)
    commands = []
    for number in (1, 2):
        project = tmp_path / f"project-{number}"
        project.mkdir()
        _reach_result(project, feature)
        _configure_sync(project, compound)
        action = _state(project, "resume", feature)
        inputs = project / ".harness/result-input"
        inputs.mkdir(parents=True)
        controller = inputs / "controller.json"
        evidence_path = inputs / "evidence.json"
        controller.write_text(json.dumps(action), encoding="utf-8")
        evidence = json.loads((FIXTURES / "result-sync-evidence.json").read_text(encoding="utf-8"))
        evidence["completion_identity"] = f"concurrent-completion-{number}:2026-07-23"
        evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
        commands.append([
            sys.executable, str(RESULT_ACTION), "--project-root", str(project),
            "--feature", feature, "--controller-result", str(controller),
            "--evidence", str(evidence_path), "--result-date", "2026-07-23",
        ])
    env = os.environ.copy()
    env.pop("HARNESS_HOOKS", None)
    env.pop("CODEX_PLUGIN_ROOT", None)
    processes = [subprocess.Popen(command, cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for command in commands]
    outcomes = []
    for process in processes:
        stdout, stderr = process.communicate(timeout=20)
        assert process.returncode == 0, (stdout, stderr)
        assert "Traceback" not in stdout + stderr
        outcomes.append(json.loads(stdout))
    run_ids = {outcome["sync"]["run_id"] for outcome in outcomes}
    assert len(run_ids) == 2
    assert len(list((compound / f"raw/projects/{feature}").glob("sdd-2026-07-23-*/snapshot.json"))) == 2
    page = (compound / "wiki/organization-compound.md").read_text(encoding="utf-8")
    index = (compound / "wiki/index.md").read_text(encoding="utf-8")
    log = (compound / "wiki/log.md").read_text(encoding="utf-8")
    for run_id in run_ids:
        marker = f"SDD-SYNC:{feature}:{run_id}"
        assert marker in page and marker in index and marker in log
    for number in (1, 2):
        project = tmp_path / f"project-{number}"
        assert (project / f"docs/sdd/result/2026-07-23-{feature}.md").is_file()
        assert (project / f"docs/sdd/result/2026-07-23-{feature}-compound-sync.md").is_file()


def test_same_project_complete_response_loss_retry_is_read_only_and_tamper_blocks(tmp_path: Path) -> None:
    feature = "result-sync"
    _reach_result(tmp_path, feature)
    compound = tmp_path.parent / f"{tmp_path.name}-compound"
    _compound_fixture(compound)
    _configure_sync(tmp_path, compound)
    original_action = _state(tmp_path, "resume", feature)
    first, first_outcome = _run_result_action(
        tmp_path, feature=feature, evidence_fixture="result-sync-evidence.json",
        controller_value=original_action,
    )
    assert first.returncode == 0 and first_outcome
    project_before = _tree_snapshot(tmp_path)
    compound_before = _tree_snapshot(compound)
    retry, retry_outcome = _run_result_action(
        tmp_path, feature=feature, evidence_fixture="result-sync-evidence.json",
        controller_value=original_action,
    )
    assert retry.returncode == 0 and retry_outcome and retry_outcome["recovered"] is True
    assert retry_outcome["sync"]["run_id"] == first_outcome["sync"]["run_id"]
    assert _tree_snapshot(tmp_path) == project_before
    assert _tree_snapshot(compound) == compound_before

    reordered_action = dict(reversed(list(original_action.items())))
    (tmp_path / ".harness/result-input/controller.json").write_text(
        json.dumps(reordered_action), encoding="utf-8"
    )
    reordered_project = _tree_snapshot(tmp_path)
    reordered_compound = _tree_snapshot(compound)
    reordered, reordered_outcome = _run_result_action(
        tmp_path, feature=feature, evidence_fixture="result-sync-evidence.json",
        controller_value=reordered_action,
    )
    assert reordered.returncode == 0 and reordered_outcome and reordered_outcome["recovered"] is True
    assert _tree_snapshot(tmp_path) == reordered_project
    assert _tree_snapshot(compound) == reordered_compound

    fabricated_actions = []
    changed_message = json.loads(json.dumps(original_action))
    changed_message["message"] = "fabricated same-feature RESULT message"
    fabricated_actions.append(changed_message)
    added_field = json.loads(json.dumps(original_action))
    added_field["fabricated"] = True
    fabricated_actions.append(added_field)
    missing_field = json.loads(json.dumps(original_action))
    missing_field.pop("next_step", None)
    fabricated_actions.append(missing_field)
    for fabricated in fabricated_actions:
        (tmp_path / ".harness/result-input/controller.json").write_text(
            json.dumps(fabricated), encoding="utf-8"
        )
        fabricated_project = _tree_snapshot(tmp_path)
        fabricated_compound = _tree_snapshot(compound)
        denied, denied_payload = _run_result_action(
            tmp_path, feature=feature, evidence_fixture="result-sync-evidence.json",
            controller_value=fabricated,
        )
        assert denied.returncode == 2 and denied_payload and denied_payload["Status"] == "BLOCKED"
        assert _tree_snapshot(tmp_path) == fabricated_project
        assert _tree_snapshot(compound) == fabricated_compound

    (tmp_path / ".harness/result-input/controller.json").write_text(
        json.dumps(original_action), encoding="utf-8"
    )

    mismatch = json.loads((FIXTURES / "result-sync-evidence.json").read_text(encoding="utf-8"))
    mismatch["summary"] = "different verified summary"
    (tmp_path / ".harness/result-input/evidence.json").write_text(json.dumps(mismatch), encoding="utf-8")
    mismatch_project = _tree_snapshot(tmp_path)
    mismatch_compound = _tree_snapshot(compound)
    rejected, rejected_payload = _run_result_action(
        tmp_path, feature=feature, evidence_fixture="result-sync-evidence.json",
        evidence_value=mismatch, controller_value=original_action,
    )
    assert rejected.returncode == 2 and rejected_payload and rejected_payload["Status"] == "BLOCKED"
    assert _tree_snapshot(tmp_path) == mismatch_project
    assert _tree_snapshot(compound) == mismatch_compound
    (tmp_path / ".harness/result-input/evidence.json").write_text(
        (FIXTURES / "result-sync-evidence.json").read_text(encoding="utf-8"), encoding="utf-8"
    )

    original_config = (tmp_path / ".harness/config.json").read_bytes()
    changed_config = json.loads(original_config)
    changed_config["knowledge_sync"]["retention_policy"] = "different-policy"
    (tmp_path / ".harness/config.json").write_text(json.dumps(changed_config), encoding="utf-8")
    config_project = _tree_snapshot(tmp_path)
    config_compound = _tree_snapshot(compound)
    config_blocked, config_payload = _run_result_action(
        tmp_path, feature=feature, evidence_fixture="result-sync-evidence.json",
        controller_value=original_action,
    )
    assert config_blocked.returncode == 2 and config_payload and config_payload["Status"] == "BLOCKED"
    assert _tree_snapshot(tmp_path) == config_project
    assert _tree_snapshot(compound) == config_compound
    (tmp_path / ".harness/config.json").write_bytes(original_config)

    result_file = tmp_path / "docs/sdd/result/2026-07-23-result-sync.md"
    result_original = result_file.read_bytes()
    digest = first_outcome["sync"]["controller_action_digest"]["sha256"]
    result_file.write_bytes(result_original.replace(digest.encode(), b"0" * 64))
    digest_project = _tree_snapshot(tmp_path)
    digest_compound = _tree_snapshot(compound)
    digest_blocked, digest_payload = _run_result_action(
        tmp_path, feature=feature, evidence_fixture="result-sync-evidence.json",
        controller_value=original_action,
    )
    assert digest_blocked.returncode == 2 and digest_payload and digest_payload["Status"] == "BLOCKED"
    assert _tree_snapshot(tmp_path) == digest_project
    assert _tree_snapshot(compound) == digest_compound
    result_file.write_bytes(result_original)

    sync_report = tmp_path / "docs/sdd/result/2026-07-23-result-sync-compound-sync.md"
    sync_original = sync_report.read_bytes()
    sync_report.write_bytes(sync_original.replace(f"- Controller ACTION digest: `v1:{digest}`\n".encode(), b""))
    missing_project = _tree_snapshot(tmp_path)
    missing_compound = _tree_snapshot(compound)
    missing_blocked, missing_payload = _run_result_action(
        tmp_path, feature=feature, evidence_fixture="result-sync-evidence.json",
        controller_value=original_action,
    )
    assert missing_blocked.returncode == 2 and missing_payload and missing_payload["Status"] == "BLOCKED"
    assert _tree_snapshot(tmp_path) == missing_project
    assert _tree_snapshot(compound) == missing_compound
    sync_report.write_bytes(sync_original)

    page = compound / "wiki/organization-compound.md"
    page.write_text(page.read_text(encoding="utf-8").replace("Completion:", "Tampered:"), encoding="utf-8")
    tampered_project = _tree_snapshot(tmp_path)
    tampered_compound = _tree_snapshot(compound)
    blocked, payload = _run_result_action(
        tmp_path, feature=feature, evidence_fixture="result-sync-evidence.json",
        controller_value=original_action,
    )
    assert blocked.returncode == 2 and payload and payload["Status"] == "BLOCKED"
    assert _tree_snapshot(tmp_path) == tampered_project
    assert _tree_snapshot(compound) == tampered_compound


def test_durable_snapshot_redaction_preserves_long_artifact_content(tmp_path: Path) -> None:
    feature = "result-sync"
    _reach_result(tmp_path, feature)
    compound = tmp_path.parent / f"{tmp_path.name}-compound"
    _compound_fixture(compound)
    _configure_sync(tmp_path, compound)
    long_text = (
        "PREFIX-KEEP\n" + "A" * 6000 + "\nMIDDLE-KEEP\n"
        "Authorization: Bearer long-secret-must-go\n" + "B" * 6000
        + "\nSUFFIX-KEEP\napi_key=second-long-secret\n"
    )
    spec_path = tmp_path / f"docs/sdd/spec/2026-07-23-{feature}.md"
    spec_path.write_text(long_text, encoding="utf-8")
    design_path = tmp_path / f"docs/sdd/design/arch/2026-07-23-{feature}.md"
    design_path.write_text(long_text, encoding="utf-8")
    task_path = tmp_path / f"docs/sdd/task/{feature}/2026-07-23-T-1-flow.md"
    task_path.write_text(long_text, encoding="utf-8")
    learning = tmp_path / f".harness/state/sdd/{feature}/run/learning-buffer.md"
    learning.parent.mkdir(parents=True)
    learning.write_text(long_text, encoding="utf-8")
    process, outcome = _run_result_action(
        tmp_path, feature=feature, evidence_fixture="result-sync-evidence.json",
    )
    assert process.returncode == 0 and outcome
    snapshot = Path(outcome["sync"]["snapshot"])
    payload = json.loads(snapshot.read_text(encoding="utf-8"))
    rendered = payload["artifacts"][spec_path.relative_to(tmp_path).as_posix()]
    designed = payload["artifacts"][design_path.relative_to(tmp_path).as_posix()]
    tasked = payload["artifacts"][task_path.relative_to(tmp_path).as_posix()]
    learned = payload["artifacts"][learning.relative_to(tmp_path).as_posix()]
    for value in (rendered, designed, tasked, learned):
        assert len(value) > 12000
        assert "PREFIX-KEEP" in value and "MIDDLE-KEEP" in value and "SUFFIX-KEEP" in value
        assert "A" * 6000 in value and "B" * 6000 in value
        assert "long-secret-must-go" not in value and "second-long-secret" not in value
        assert "[REDACTED]" in value


def test_result_action_rejects_symlink_input_without_partial_files(tmp_path: Path) -> None:
    feature = "result-resume"
    state_path = _reach_result(tmp_path, feature)
    state_bytes = state_path.read_bytes()
    inputs = tmp_path / ".harness/result-input"
    inputs.mkdir(parents=True)
    controller = inputs / "controller.json"
    controller.symlink_to(FIXTURES / "result-resume-action.json")
    evidence = inputs / "evidence.json"
    shutil.copyfile(FIXTURES / "result-resume-evidence.json", evidence)
    result = subprocess.run(
        [
            sys.executable, str(RESULT_ACTION), "--project-root", str(tmp_path),
            "--feature", feature, "--controller-result", str(controller),
            "--evidence", str(evidence), "--result-date", "2026-07-23",
        ],
        cwd=ROOT, check=False, text=True, capture_output=True,
    )
    assert result.returncode == 2
    assert not (tmp_path / "docs/sdd/result/2026-07-23-result-resume.md").exists()
    assert state_path.read_bytes() == state_bytes


def test_result_action_rejects_invalid_action_and_outside_evidence(tmp_path: Path) -> None:
    feature = "result-resume"
    state_path = _reach_result(tmp_path, feature)
    state_bytes = state_path.read_bytes()

    invalid, payload = _run_result_action(
        tmp_path,
        feature=feature,
        controller_fixture="result-invalid-action.json",
        evidence_fixture="result-resume-evidence.json",
    )
    assert invalid.returncode == 2
    assert payload and payload["Status"] == "BLOCKED"
    assert "phase must be RESULT" in str(payload["error"])

    controller = tmp_path / ".harness/result-input/controller.json"
    shutil.copyfile(FIXTURES / "result-resume-action.json", controller)
    outside = FIXTURES / "result-resume-evidence.json"
    outside_result = subprocess.run(
        [
            sys.executable, str(RESULT_ACTION), "--project-root", str(tmp_path),
            "--feature", feature, "--controller-result", str(controller),
            "--evidence", str(outside), "--result-date", "2026-07-23",
        ],
        cwd=ROOT, check=False, text=True, capture_output=True,
    )
    assert outside_result.returncode == 2
    assert "inside project root" in outside_result.stdout
    assert not (tmp_path / "docs/sdd/result/2026-07-23-result-resume.md").exists()
    assert state_path.read_bytes() == state_bytes


def test_result_action_rejects_fabricated_or_stale_action(tmp_path: Path) -> None:
    feature = "result-resume"
    state_path = _reach_result(tmp_path, feature)
    before = state_path.read_bytes()
    process, payload = _run_result_action(
        tmp_path, feature=feature, controller_fixture="result-resume-action.json",
        evidence_fixture="result-resume-evidence.json",
    )
    assert process.returncode == 2
    assert payload and "exactly match" in str(payload["error"])
    assert state_path.read_bytes() == before
    assert not (tmp_path / "docs/sdd/result/2026-07-23-result-resume.md").exists()


def test_result_action_rejects_malformed_validation_evidence(tmp_path: Path) -> None:
    feature = "result-resume"
    state_path = _reach_result(tmp_path, feature)
    base = json.loads((FIXTURES / "result-resume-evidence.json").read_text(encoding="utf-8"))
    invalid_entries = [
        [],
        [True],
        [{"name": "tests", "status": "FAIL", "evidence": "one failure"}],
        [{"name": "tests", "status": "PASS", "evidence": True}],
        [{"name": "", "status": "PASS", "evidence": "ok"}],
    ]
    for validation in invalid_entries:
        evidence = dict(base)
        evidence["validation"] = validation
        before = state_path.read_bytes()
        process, payload = _run_result_action(
            tmp_path, feature=feature, evidence_fixture="result-resume-evidence.json",
            evidence_value=evidence,
        )
        assert process.returncode == 2
        assert payload and payload["Status"] == "BLOCKED"
        assert state_path.read_bytes() == before
        assert not (tmp_path / "docs/sdd/result/2026-07-23-result-resume.md").exists()


def test_result_action_rejects_conflict_before_configured_sync(tmp_path: Path) -> None:
    feature = "result-sync"
    state_path = _reach_result(tmp_path, feature)
    state_bytes = state_path.read_bytes()
    compound_root = tmp_path.parent / f"{tmp_path.name}-compound"
    _compound_fixture(compound_root)
    (tmp_path / ".harness/config.json").write_text(
        json.dumps({
            "schema_version": 1,
            "knowledge_sync": {
                "enabled": True,
                "compound_root": str(compound_root),
                "destination": "organization-compound",
                "credential_source": "explicit-local-config",
                "retention_policy": "append-only",
            },
        }),
        encoding="utf-8",
    )
    result_dir = tmp_path / "docs/sdd/result"
    result_dir.mkdir(parents=True)
    result_path = result_dir / "2026-07-23-result-sync.md"
    result_path.write_text("conflicting user-owned result\n", encoding="utf-8")
    project_before = _tree_snapshot(result_dir)
    compound_before = _tree_snapshot(compound_root)

    process, payload = _run_result_action(
        tmp_path,
        feature=feature,
        controller_fixture="result-sync-action.json",
        evidence_fixture="result-sync-evidence.json",
    )
    assert process.returncode == 2
    assert payload and payload["Status"] == "BLOCKED"
    assert result_path.read_text(encoding="utf-8") == "conflicting user-owned result\n"
    assert not (compound_root / "raw/projects/result-sync").exists()
    assert _tree_snapshot(result_dir) == project_before
    assert _tree_snapshot(compound_root) == compound_before
    assert state_path.read_bytes() == state_bytes


def test_raw_snapshot_conflict_rolls_back_compound_and_project_trees(tmp_path: Path) -> None:
    feature = "result-sync"
    state_path = _reach_result(tmp_path, feature)
    compound = tmp_path.parent / f"{tmp_path.name}-compound"
    _compound_fixture(compound)
    _configure_sync(tmp_path, compound)
    evidence = json.loads((FIXTURES / "result-sync-evidence.json").read_text(encoding="utf-8"))
    run_id = __import__("hashlib").sha256(evidence["completion_identity"].encode()).hexdigest()[:12]
    snapshot = compound / f"raw/projects/{feature}/sdd-2026-07-23-{run_id}/snapshot.json"
    snapshot.parent.mkdir(parents=True)
    snapshot.write_text("user-owned conflict\n", encoding="utf-8")
    project_before = _tree_snapshot(tmp_path / "docs/sdd/result")
    compound_before = _tree_snapshot(compound)
    state_before = state_path.read_bytes()
    process, payload = _run_result_action(
        tmp_path, feature=feature, evidence_fixture="result-sync-evidence.json",
    )
    assert process.returncode == 2
    assert payload and payload["Status"] == "BLOCKED"
    assert _tree_snapshot(tmp_path / "docs/sdd/result") == project_before
    assert _tree_snapshot(compound) == compound_before
    assert state_path.read_bytes() == state_before


def test_late_result_write_failure_restores_modified_wiki_bytes_and_modes(tmp_path: Path) -> None:
    feature = "result-sync"
    state_path = _reach_result(tmp_path, feature)
    compound = tmp_path.parent / f"{tmp_path.name}-compound"
    _compound_fixture(compound)
    _configure_sync(tmp_path, compound)
    inputs = tmp_path / ".harness/result-input"
    inputs.mkdir(parents=True)
    controller = inputs / "controller.json"
    evidence = inputs / "evidence.json"
    controller.write_text(json.dumps(_state(tmp_path, "resume", feature)), encoding="utf-8")
    shutil.copyfile(FIXTURES / "result-sync-evidence.json", evidence)
    spec = importlib.util.spec_from_file_location("result_action_rollback_test", RESULT_ACTION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original_create = module._atomic_create

    def fail_final_result(path: Path, content: bytes) -> bool:
        if path.name == "2026-07-23-result-sync.md":
            raise OSError("injected late result failure")
        return original_create(path, content)

    module._atomic_create = fail_final_result
    project_before = _tree_snapshot(tmp_path / "docs/sdd/result")
    compound_before = _tree_snapshot(compound)
    state_before = state_path.read_bytes()
    with pytest.raises(OSError, match="injected late result failure"):
        module.run(argparse.Namespace(
            project_root=str(tmp_path), feature=feature,
            controller_result=str(controller), evidence=str(evidence), result_date="2026-07-23",
        ))
    assert _tree_snapshot(tmp_path / "docs/sdd/result") == project_before
    assert _tree_snapshot(compound) == compound_before
    assert state_path.read_bytes() == state_before


def test_result_action_permission_failure_leaves_both_output_trees_exact(tmp_path: Path) -> None:
    feature = "result-sync"
    state_path = _reach_result(tmp_path, feature)
    state_bytes = state_path.read_bytes()
    compound_root = tmp_path.parent / f"{tmp_path.name}-compound"
    _compound_fixture(compound_root)
    (tmp_path / ".harness/config.json").write_text(json.dumps({
        "schema_version": 1,
        "knowledge_sync": {
            "enabled": True, "compound_root": str(compound_root),
            "destination": "organization-compound",
            "credential_source": "explicit-local-config", "retention_policy": "append-only",
        },
    }), encoding="utf-8")
    original_mode = stat.S_IMODE(compound_root.stat().st_mode)
    compound_root.chmod(0o500)
    project_output = tmp_path / "docs/sdd/result"
    project_before = _tree_snapshot(project_output)
    compound_before = _tree_snapshot(compound_root)
    try:
        process, payload = _run_result_action(
            tmp_path, feature=feature, evidence_fixture="result-sync-evidence.json",
        )
        assert process.returncode == 2
        assert payload and payload["Status"] == "BLOCKED"
        assert _tree_snapshot(project_output) == project_before
        assert _tree_snapshot(compound_root) == compound_before
        assert state_path.read_bytes() == state_bytes
    finally:
        compound_root.chmod(original_mode)
