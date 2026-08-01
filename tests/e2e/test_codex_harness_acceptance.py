from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import stat
import subprocess
import sys

import pytest

from harness_core.pr import revision_key


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/e2e_sample_project"
ACTIVE_SURFACE = json.loads(
    (ROOT / "skills/ACTIVE_SURFACE.json").read_text(encoding="utf-8")
)
RAW_CREDENTIAL = "e2e-local-credential-7C2X9"


def _project(tmp_path: Path, name: str = "sample-project") -> Path:
    destination = tmp_path / name
    shutil.copytree(FIXTURE, destination)
    return destination


def _opaque_runtime(tmp_path: Path) -> tuple[Path, Path]:
    installation = tmp_path / "opaque-plugin"
    for relative in [".codex-plugin/plugin.json", *ACTIVE_SURFACE["included"]]:
        source = ROOT / relative
        target = installation / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return installation, installation / "skills/sdd/runtime/moondex-runtime.py"


def _snapshot(root: Path) -> dict[str, tuple[str, int, bytes | str]]:
    result: dict[str, tuple[str, int, bytes | str]] = {}
    for path in [root, *sorted(root.rglob("*"))]:
        relative = "." if path == root else path.relative_to(root).as_posix()
        mode = stat.S_IMODE(path.lstat().st_mode)
        if path.is_symlink():
            result[relative] = ("symlink", mode, os.readlink(path))
        elif path.is_dir():
            result[relative] = ("directory", mode, "")
        else:
            result[relative] = ("file", mode, path.read_bytes())
    return result


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    for name in (
        "PYTHONPATH",
        "HARNESS_HOOKS",
        "CODEX_PLUGIN_ROOT",
        "CLAUDE_PLUGIN_ROOT",
        "CODEX_SESSION_ID",
        "GITHUB_TOKEN",
        "GH_TOKEN",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
    ):
        environment.pop(name, None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment


def _run(runtime: Path, project: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(runtime), *arguments],
        cwd=project,
        env=_environment(),
        check=False,
        text=True,
        capture_output=True,
    )


def _json_run(runtime: Path, project: Path, *arguments: str) -> dict[str, object]:
    completed = _run(runtime, project, *arguments)
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return json.loads(completed.stdout)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _transition(
    runtime: Path,
    project: Path,
    feature: str,
    expected: str,
    target: str,
    *extra: str,
) -> dict[str, object]:
    return _json_run(
        runtime,
        project,
        "state",
        "--project-root",
        ".",
        "transition",
        "--feature",
        feature,
        "--expected",
        expected,
        "--target",
        target,
        *extra,
    )


class _SoleWriterSimulation:
    """Test-owned orchestration simulator; this is not a production controller API."""

    STAGES = ("engineer", "compliance", "review", "test")
    STATUSES = ("DONE", "DONE_WITH_CONCERNS", "NEEDS_CONTEXT", "BLOCKED")
    REQUIRED = {
        "schema_version",
        "task_id",
        "stage",
        "status",
        "iteration",
        "changed_files",
        "validation",
        "evidence",
    }

    def __init__(self, project: Path, feature: str, task_id: str = "T-1") -> None:
        self.project = project
        self.feature = feature
        self.task_id = task_id
        self.events_path = (
            project
            / f".harness/state/sdd/{feature}/e2e-simulation/events.jsonl"
        )
        self.events: list[dict[str, object]] = []
        self.stage_index = 0
        self.failures: dict[str, int] = {}
        self.open_escalations: set[str] = set()
        self.gates: dict[str, str] = {}

    def accept_worker_result(self, envelope: dict[str, object]) -> None:
        assert set(envelope) == self.REQUIRED
        assert envelope["schema_version"] == 1
        assert envelope["task_id"] == self.task_id
        stage = envelope["stage"]
        status = envelope["status"]
        assert stage in self.STAGES and status in self.STATUSES
        assert stage == self.STAGES[self.stage_index]
        assert (
            isinstance(envelope["iteration"], int)
            and not isinstance(envelope["iteration"], bool)
            and envelope["iteration"] >= 1
        )
        assert isinstance(envelope["changed_files"], list)
        assert all(
            isinstance(path, str) and path
            for path in envelope["changed_files"]
        )
        validation = envelope["validation"]
        assert isinstance(validation, list) and validation
        assert all(
            isinstance(item, dict)
            and set(item) == {"name", "status", "evidence"}
            and item["status"] in {"PASS", "FAIL"}
            and isinstance(item["name"], str)
            and isinstance(item["evidence"], str)
            for item in validation
        )
        if status in {"DONE", "DONE_WITH_CONCERNS"}:
            assert all(item["status"] == "PASS" for item in validation)
        event = {
            "schema_version": 1,
            "event_id": len(self.events) + 1,
            "event_type": "worker_result",
            **envelope,
        }
        self._append(event)
        if status in {"DONE", "DONE_WITH_CONCERNS"}:
            self.stage_index += 1
            return
        self.failures[stage] = self.failures.get(stage, 0) + 1
        if self.failures[stage] >= 3:
            escalation_id = f"{self.task_id}:{stage}"
            self.open_escalations.add(escalation_id)
            self._append(
                {
                    "schema_version": 1,
                    "event_id": len(self.events) + 1,
                    "event_type": "escalation_opened",
                    "task_id": self.task_id,
                    "stage": stage,
                    "escalation_id": escalation_id,
                    "reason": "three validated worker failures",
                }
            )

    def resolve_escalation(self, escalation_id: str) -> None:
        assert escalation_id in self.open_escalations
        self.open_escalations.remove(escalation_id)
        self._append(
            {
                "schema_version": 1,
                "event_id": len(self.events) + 1,
                "event_type": "escalation_resolved",
                "task_id": self.task_id,
                "escalation_id": escalation_id,
                "authority": "USER",
                "decision": "RETRY",
                "evidence": "explicit local acceptance decision",
            }
        )

    def accept_gate_report(self, name: str, report: dict[str, object]) -> None:
        assert name in {"consumer_e2e", "shared_verify"}
        assert report.get("schema_version") in {1, 3}
        assert report.get("status") in {"PASS", "FAIL"}
        self.gates[name] = str(report["status"])
        self._append(
            {
                "schema_version": 1,
                "event_id": len(self.events) + 1,
                "event_type": "acceptance_gate",
                "task_id": self.task_id,
                "gate": name,
                "status": report["status"],
                "evidence": report.get("evidence", report.get("outcomes", [])),
            }
        )

    @property
    def complete(self) -> bool:
        return (
            self.stage_index == len(self.STAGES)
            and not self.open_escalations
            and self.gates
            == {"consumer_e2e": "PASS", "shared_verify": "PASS"}
        )

    def render_authoritative_state(self) -> Path:
        status = "complete" if self.complete else "testing"
        notes = (
            f"test-owned schema-valid simulation; events={len(self.events)}; "
            f"open_escalations={len(self.open_escalations)}; "
            f"consumer_e2e={self.gates.get('consumer_e2e', 'MISSING')}; "
            f"shared_verify={self.gates.get('shared_verify', 'MISSING')}"
        )
        path = self.project / "docs/sdd/ORCHESTRATOR_STATE.md"
        path.write_text(
            f"""# Orchestrator State

- Feature: `{self.feature}`
- Evidence: `.harness/state/sdd/{self.feature}/e2e-simulation/events.jsonl`
- Authority: test-owned sole-writer simulation (not a production controller API)

## Task status

| ID | Wave | Status | Iteration | Role profile | Notes |
|---|---:|---|---:|---|---|
| {self.task_id} | 1 | {status} | {len(self.events)} | sdd-test-automator | {notes} |
""",
            encoding="utf-8",
        )
        return path

    def _append(self, event: dict[str, object]) -> None:
        self.events.append(event)
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")


def _worker_envelope(
    stage: str,
    status: str,
    iteration: int,
    *,
    validation_status: str | None = None,
) -> dict[str, object]:
    validation_status = validation_status or (
        "PASS" if status in {"DONE", "DONE_WITH_CONCERNS"} else "FAIL"
    )
    return {
        "schema_version": 1,
        "task_id": "T-1",
        "stage": stage,
        "status": status,
        "iteration": iteration,
        "changed_files": ["web/Panel.tsx"],
        "validation": [
            {
                "name": f"{stage}-validation",
                "status": validation_status,
                "evidence": f"deterministic {stage} evidence",
            }
        ],
        "evidence": f"{stage} returned {status}",
    }


def _run_consumer_e2e(project: Path) -> dict[str, object]:
    config = json.loads(
        (project / ".harness/state/e2e-config.json").read_text(encoding="utf-8")
    )
    command = shlex.split(config["command"])
    completed = subprocess.run(
        command,
        cwd=project,
        env=_environment(),
        check=False,
        text=True,
        capture_output=True,
    )
    report = {
        "schema_version": 1,
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "command": command,
        "returncode": completed.returncode,
        "changed_file": "web/Panel.tsx",
        "evidence": {
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        },
    }
    _write_json(project / ".harness/reports/consumer-e2e.json", report)
    return report


def _run_shared_verify(
    runtime: Path, project: Path, *, branch: str = "feature/e2e-parity"
) -> dict[str, object]:
    report = project / ".harness/reports/shared-verify.json"
    completed = _run(
        runtime,
        project,
        "verify",
        "--project-root",
        ".",
        "--branch",
        branch,
        "--default-branch",
        "main",
        "--source",
        "explicit",
        "--changed-file",
        "web/Panel.tsx",
        "--audit-file",
        str(report),
    )
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert completed.returncode == (0 if payload["status"] == "PASS" else 2)
    return payload


def _assert_result_blocked(
    runtime: Path, project: Path, feature: str
) -> dict[str, object]:
    blocked = _transition(runtime, project, feature, "EXECUTE", "RESULT")
    assert blocked["code"] == "BLOCKED_ARTIFACT"
    assert blocked["state"]["phase"] == "EXECUTE"
    assert not (project / "docs/sdd/result").exists()
    return blocked


def _enter_execute_for_negative(
    runtime: Path, project: Path, feature: str
) -> _SoleWriterSimulation:
    _json_run(runtime, project, "state", "--project-root", ".", "start", feature)
    spec = project / f"docs/sdd/spec/2026-07-30-{feature}.md"
    spec.parent.mkdir(parents=True)
    spec.write_text("# Negative lifecycle specification\n", encoding="utf-8")
    _transition(runtime, project, feature, "SPEC", "DESIGN", "--approve", "spec")
    design = project / f"docs/sdd/design/arch/2026-07-30-{feature}.md"
    design.parent.mkdir(parents=True)
    design.write_text("# Negative lifecycle architecture\n", encoding="utf-8")
    _transition(runtime, project, feature, "DESIGN", "PLAN", "--approve", "design")
    task = project / f"docs/sdd/task/{feature}/2026-07-30-T-1-e2e.md"
    task.parent.mkdir(parents=True)
    task.write_text("# Negative lifecycle task\n", encoding="utf-8")
    simulation = _SoleWriterSimulation(project, feature)
    simulation.render_authoritative_state()
    worktree = project / f"worktrees/{feature}"
    worktree.mkdir(parents=True)
    transitioned = _transition(
        runtime,
        project,
        feature,
        "PLAN",
        "EXECUTE",
        "--approve",
        "plan",
        "--worktree",
        str(worktree),
    )
    assert transitioned["state"]["phase"] == "EXECUTE"
    for stage in _SoleWriterSimulation.STAGES:
        simulation.accept_worker_result(_worker_envelope(stage, "DONE", 1))
    return simulation


def test_clean_environment_controller_plan_to_result_and_recorded_outcomes(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    installation, runtime = _opaque_runtime(tmp_path)
    install_before = _snapshot(installation)
    feature = "e2e-parity"

    started = _json_run(
        runtime, project, "state", "--project-root", ".", "start", feature
    )
    assert started["code"] == "INITIALIZED"
    state_path = project / ".harness/state/pipeline.json"
    initial_bytes = state_path.read_bytes()

    # These are separate ordinary Codex turns: no hook helper or session identity.
    first_status = _json_run(
        runtime, project, "state", "--project-root", ".", "status", feature
    )
    first_resume = _json_run(
        runtime, project, "state", "--project-root", ".", "resume", feature
    )
    assert first_status == first_resume
    assert state_path.read_bytes() == initial_bytes

    before_doctor = _json_run(
        runtime, project, "state", "--project-root", ".", "resume", feature
    )
    doctor = _json_run(
        runtime, project, "state", "--project-root", ".", "doctor", feature
    )
    after_doctor = _json_run(
        runtime, project, "state", "--project-root", ".", "resume", feature
    )
    assert doctor["code"] == "ADVISORY_UNAVAILABLE"
    assert doctor["next_step"] == before_doctor["next_step"]
    assert before_doctor == after_doctor

    spec = project / "docs/sdd/spec/2026-07-30-e2e-parity.md"
    spec.parent.mkdir(parents=True)
    spec.write_text("# E2E parity specification\n", encoding="utf-8")
    assert _transition(
        runtime, project, feature, "SPEC", "DESIGN", "--approve", "spec"
    )["state"]["phase"] == "DESIGN"

    design = project / "docs/sdd/design/arch/2026-07-30-e2e-parity.md"
    design.parent.mkdir(parents=True)
    design.write_text("# E2E parity architecture\n", encoding="utf-8")
    assert _transition(
        runtime, project, feature, "DESIGN", "PLAN", "--approve", "design"
    )["state"]["phase"] == "PLAN"

    task = project / "docs/sdd/task/e2e-parity/2026-07-30-T-1-e2e.md"
    task.parent.mkdir(parents=True)
    task.write_text("# T-1 E2E task\n", encoding="utf-8")
    simulation = _SoleWriterSimulation(project, feature)
    simulation.render_authoritative_state()
    worktree = project / "worktrees/e2e-parity"
    worktree.mkdir(parents=True)
    executing = _transition(
        runtime,
        project,
        feature,
        "PLAN",
        "EXECUTE",
        "--approve",
        "plan",
        "--worktree",
        str(worktree),
    )
    assert executing["state"]["phase"] == "EXECUTE"

    consumer_e2e = _run_consumer_e2e(project)
    shared_verify = _run_shared_verify(runtime, project)
    assert consumer_e2e["status"] == shared_verify["status"] == "PASS"
    assert consumer_e2e["changed_file"] == "web/Panel.tsx"
    assert shared_verify["changed_files"] == [
        {"source": "explicit", "status": "M", "paths": ["web/Panel.tsx"]}
    ]
    simulation.accept_gate_report("consumer_e2e", consumer_e2e)
    simulation.accept_gate_report("shared_verify", shared_verify)

    simulation.accept_worker_result(_worker_envelope("engineer", "DONE", 1))
    simulation.accept_worker_result(_worker_envelope("compliance", "DONE", 1))
    simulation.accept_worker_result(_worker_envelope("review", "BLOCKED", 1))
    simulation.render_authoritative_state()
    _assert_result_blocked(runtime, project, feature)

    simulation.accept_worker_result(_worker_envelope("review", "DONE", 2))
    simulation.accept_worker_result(_worker_envelope("test", "BLOCKED", 1))
    simulation.render_authoritative_state()
    _assert_result_blocked(runtime, project, feature)
    simulation.accept_worker_result(_worker_envelope("test", "BLOCKED", 2))
    simulation.accept_worker_result(_worker_envelope("test", "BLOCKED", 3))
    assert simulation.open_escalations == {"T-1:test"}
    simulation.render_authoritative_state()
    _assert_result_blocked(runtime, project, feature)

    simulation.resolve_escalation("T-1:test")
    simulation.accept_worker_result(_worker_envelope("test", "DONE", 4))
    simulation.render_authoritative_state()
    assert simulation.complete is True
    persisted_events = [
        json.loads(line)
        for line in simulation.events_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [event["event_type"] for event in persisted_events].count(
        "worker_result"
    ) == 8
    assert any(
        event["event_type"] == "escalation_opened" for event in persisted_events
    )
    assert any(
        event["event_type"] == "escalation_resolved"
        and event["authority"] == "USER"
        for event in persisted_events
    )

    preflight = _run(
        runtime,
        project,
        "preflight",
        "phase",
        "--project-root",
        ".",
        "--target-phase",
        "RESULT",
    )
    assert preflight.returncode == 0, preflight.stderr or preflight.stdout
    result_phase = _transition(runtime, project, feature, "EXECUTE", "RESULT")
    assert result_phase["state"]["phase"] == "RESULT"
    controller_result = _json_run(
        runtime, project, "state", "--project-root", ".", "resume", feature
    )
    assert controller_result["code"] == "ACTION"
    controller_path = project / ".harness/result-input/controller.json"
    evidence_path = project / ".harness/result-input/evidence.json"
    _write_json(controller_path, controller_result)
    _write_json(
        evidence_path,
        {
            "schema_version": 1,
            "feature": feature,
            "completion_identity": "e2e-consumer-gates-0001",
            "verified": True,
            "summary": "Consumer-owned E2E and shared explicit verification passed.",
            "validation": [
                {
                    "name": "consumer-e2e",
                    "status": consumer_e2e["status"],
                    "evidence": ".harness/reports/consumer-e2e.json",
                },
                {
                    "name": "shared-explicit-verify",
                    "status": shared_verify["status"],
                    "evidence": ".harness/reports/shared-verify.json",
                },
                {
                    "name": "sole-writer-simulation",
                    "status": "PASS",
                    "evidence": str(simulation.events_path.relative_to(project)),
                },
            ],
        },
    )
    materialized = _json_run(
        runtime,
        project,
        "result-action",
        "--project-root",
        ".",
        "--feature",
        feature,
        "--controller-result",
        str(controller_path),
        "--evidence",
        str(evidence_path),
        "--result-date",
        "2026-07-30",
    )
    assert materialized["Status"] == "DONE"
    assert materialized["Verdict"] == "SYNC_SKIPPED"
    result = project / "docs/sdd/result/2026-07-30-e2e-parity.md"
    rendered_result = result.read_text(encoding="utf-8")
    assert "consumer-e2e" in rendered_result
    assert "shared-explicit-verify" in rendered_result
    assert "sole-writer-simulation" in rendered_result
    complete = _json_run(
        runtime, project, "state", "--project-root", ".", "resume", feature
    )
    assert complete["code"] == "COMPLETE"
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert "session" not in json.dumps(persisted).lower()
    assert not (installation / ".harness").exists()
    assert _snapshot(installation) == install_before


@pytest.mark.parametrize("failure", ("consumer-e2e", "shared-verify"))
def test_lifecycle_blocks_result_when_executable_acceptance_gate_fails(
    tmp_path: Path, failure: str,
) -> None:
    project = _project(tmp_path, failure)
    _, runtime = _opaque_runtime(tmp_path / failure)
    feature = f"{failure}-failure"
    simulation = _enter_execute_for_negative(runtime, project, feature)
    if failure == "consumer-e2e":
        (project / "web/Panel.tsx").write_text(
            """// A source-string pseudo-test would still find all of these:
// data-testid="portable-panel" >Ready</section> Complete
export function mountPanel(root) {
  const status = document.createElement('p');
  status.setAttribute('role', 'status');
  status.textContent = 'Ready';
  const button = document.createElement('button');
  button.setAttribute('aria-pressed', 'false');
  button.textContent = 'Complete';
  button.addEventListener('click', () => {});
  root.replaceChildren(status, button);
  return { status, button };
}
""",
            encoding="utf-8",
        )
    consumer_e2e = _run_consumer_e2e(project)
    if failure == "shared-verify":
        (project / ".harness/state/e2e-config.json").unlink()
    shared_verify = _run_shared_verify(runtime, project)
    assert consumer_e2e["status"] == (
        "FAIL" if failure == "consumer-e2e" else "PASS"
    )
    if failure == "consumer-e2e":
        assert "E2E_BEHAVIOR_MISMATCH" in consumer_e2e["evidence"]["stderr"]
    assert shared_verify["status"] == (
        "FAIL" if failure == "shared-verify" else "PASS"
    )
    simulation.accept_gate_report("consumer_e2e", consumer_e2e)
    simulation.accept_gate_report("shared_verify", shared_verify)
    simulation.render_authoritative_state()
    assert simulation.complete is False
    _assert_result_blocked(runtime, project, feature)
    assert not (project / ".harness/result-input").exists()


def test_consumer_runner_browser_unavailable_fails_loudly(tmp_path: Path) -> None:
    project = _project(tmp_path, "browser-unavailable")
    completed = subprocess.run(
        [
            sys.executable,
            "tests/consumer_panel_e2e.py",
            "--browser",
            str(project / "missing-browser"),
        ],
        cwd=project,
        env=_environment(),
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert completed.returncode != 0
    assert "E2E_BROWSER_UNAVAILABLE" in completed.stderr


@pytest.mark.parametrize(
    ("case", "expected_rule"),
    (
        ("default-branch", "BRANCH_DEFAULT"),
        ("missing-e2e", "E2E_EVIDENCE_MISSING"),
        ("secret", "SECRET_EXPOSED"),
    ),
)
def test_intentional_local_gate_failures_block_before_completion(
    tmp_path: Path, case: str, expected_rule: str,
) -> None:
    project = _project(tmp_path, case)
    _, runtime = _opaque_runtime(tmp_path / case)
    branch = "feature/e2e"
    changed = "src/service.py"
    if case == "default-branch":
        branch = "main"
    elif case == "missing-e2e":
        (project / ".harness/state/e2e-config.json").unlink()
        changed = "web/Panel.tsx"
    else:
        changed = "config/local.txt"
        secret = project / changed
        secret.parent.mkdir(parents=True)
        secret.write_text("Authorization: Bearer fixture-secret-123456\n", encoding="utf-8")
    report = project / f".harness/reports/{case}.json"
    completed = _run(
        runtime,
        project,
        "verify",
        "--project-root",
        ".",
        "--branch",
        branch,
        "--default-branch",
        "main",
        "--source",
        "explicit",
        "--changed-file",
        changed,
        "--audit-file",
        str(report),
    )
    assert completed.returncode == 2
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["status"] == "FAIL"
    assert expected_rule in {item["rule"] for item in payload["outcomes"]}
    assert not (project / "docs/sdd/result").exists()
    assert "fixture-secret-123456" not in completed.stdout
    assert "fixture-secret-123456" not in report.read_text(encoding="utf-8")


def _comment(identity: str, body: str, line: int) -> dict[str, object]:
    return {
        "schema_version": 1,
        "source": "inline",
        "source_identity": f"e2e:{identity}",
        "comment_id": identity,
        "revision_identity": "r1",
        "body_hash": hashlib.sha256(body.encode()).hexdigest(),
        "author": "reviewer",
        "body": body,
        "created_at": "2026-07-30T00:00:00Z",
        "path": "src/service.py",
        "line": line,
    }


def test_pr_dispositions_convergence_and_raw_audit_redaction_boundary(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    _, runtime = _opaque_runtime(tmp_path)
    comments = [
        _comment("safe", "Apply the verified local fix.", 1),
        _comment("reject", "Add a hosted provider dependency.", 2),
        _comment("question", "Should the architecture change?", 3),
    ]
    collection = {
        "schema_version": 1,
        "input_identity": "e2e-review",
        "complete": True,
        "comments": comments,
    }
    evidence = {
        revision_key(comments[0]): {
            "actionability": "ACTIONABLE",
            "alignment": {
                "spec": "ALIGNS",
                "design": "ALIGNS",
                "ownership": "OWNED",
                "verification": "AVAILABLE",
            },
            "validation_plan": ["run deterministic E2E"],
            "changed_files": ["src/service.py"],
            "repository_root": str(project.resolve()),
            "validation": [{"command": "pytest tests/e2e", "passed": True}],
            "evidence": [{"credential": RAW_CREDENTIAL, "kind": "trusted-local"}],
        },
        revision_key(comments[1]): {
            "actionability": "ACTIONABLE",
            "alignment": {
                "spec": "CONFLICTS",
                "design": "ALIGNS",
                "ownership": "OWNED",
                "verification": "AVAILABLE",
            },
            "reason": "Hosted provider publication conflicts with the local baseline.",
            "alternative": "Keep provider publication as an optional extension.",
            "evidence": [{"kind": "spec", "ref": "F5"}],
        },
        revision_key(comments[2]): {
            "actionability": "ACTIONABLE",
            "alignment": {"spec": "UNKNOWN"},
        },
    }
    collection_path = project / "review-collection.json"
    # Raw review evidence is trusted-local retained input. Keep it inside the
    # same audit-only boundary as the append-only disposition record.
    evidence_path = project / ".harness/audit/review-evidence-input.json"
    resolution_path = project / "review-resolution.json"
    _write_json(collection_path, collection)
    _write_json(evidence_path, evidence)
    audit = project / ".harness/audit/e2e-review.jsonl"
    report = project / ".harness/reports/e2e-review.json"
    passing = json.dumps([sys.executable, "-c", "raise SystemExit(0)"])
    common = (
        "pr-converge",
        "--repository-root",
        ".",
        "--collection",
        collection_path.name,
        "--evidence",
        ".harness/audit/review-evidence-input.json",
        "--audit",
        ".harness/audit/e2e-review.jsonl",
        "--report",
        ".harness/reports/e2e-review.json",
        "--build-command",
        passing,
        "--lint-command",
        passing,
        "--test-command",
        passing,
    )
    first = _run(runtime, project, *common)
    first_payload = json.loads(first.stdout)
    assert first.returncode == 0
    assert first_payload["status"] == "NEEDS_HUMAN"
    assert {item["decision"] for item in first_payload["dispositions"]} == {
        "SAFE_FIX",
        "REJECTED",
        "ESCALATED",
    }

    question = comments[2]
    _write_json(
        resolution_path,
        {
            "schema_version": 1,
            "complete": True,
            "resolutions": [
                {
                    "schema_version": 1,
                    "source_identity": question["source_identity"],
                    "revision_identity": question["revision_identity"],
                    "body_hash": question["body_hash"],
                    "comment_id": question["comment_id"],
                    "authority": "USER",
                    "decision": "REJECTED",
                    "reason": "The user kept the approved architecture.",
                    "alternative": "Open a separately approved design revision.",
                    "evidence": [{"kind": "user_decision", "ref": "e2e"}],
                }
            ],
        },
    )
    resolved = _run(
        runtime,
        project,
        *common,
        "--resolutions",
        resolution_path.name,
    )
    resolved_payload = json.loads(resolved.stdout)
    assert resolved.returncode == 0
    assert resolved_payload["status"] == "CONVERGED"
    assert [item["decision"] for item in resolved_payload["dispositions"]] == [
        "SAFE_FIX",
        "REJECTED",
        "REJECTED",
    ]

    failing = json.dumps([sys.executable, "-c", "raise SystemExit(1)"])
    not_converged = _run(
        runtime,
        project,
        *common[:-1],
        failing,
        "--resolutions",
        resolution_path.name,
    )
    assert json.loads(not_converged.stdout)["status"] == "WORKING"

    raw = audit.read_text(encoding="utf-8")
    rendered = first.stdout + resolved.stdout + not_converged.stdout
    rendered += report.read_text(encoding="utf-8")
    assert RAW_CREDENTIAL in raw
    assert RAW_CREDENTIAL not in rendered
    assert "[REDACTED]" in rendered
    assert str(audit).startswith(str(project / ".harness/audit"))

    retained_matches: list[Path] = []
    raw_bytes = RAW_CREDENTIAL.encode("utf-8")
    for candidate in project.rglob("*"):
        if (
            not candidate.is_file()
            or candidate.is_symlink()
            or "__pycache__" in candidate.parts
            or candidate.suffix in {".pyc", ".pyo"}
        ):
            continue
        if raw_bytes in candidate.read_bytes():
            retained_matches.append(candidate.relative_to(project))
    expected_audit = Path(".harness/audit/e2e-review.jsonl")
    assert expected_audit in retained_matches
    assert retained_matches
    assert all(path.parts[:2] == (".harness", "audit") for path in retained_matches)

    public_surfaces = [
        report,
        ROOT / "docs/sdd/result/2026-07-14-codex-harness-parity.md",
        ROOT
        / "docs/sdd/result/2026-07-14-codex-harness-parity-evidence.json",
    ]
    public_surfaces.extend(
        path
        for path in (project / ".harness/reports").rglob("*")
        if path.is_file() and not path.is_symlink()
    )
    assert all(raw_bytes not in path.read_bytes() for path in public_surfaces)


def test_learning_tiers_mapper_and_offline_evidence_remain_separate(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    _, runtime = _opaque_runtime(tmp_path)
    (project / ".codex-plugin").mkdir()
    (project / ".codex-plugin/plugin.json").write_text("{}\n", encoding="utf-8")
    (project / "scripts").mkdir()
    (project / "scripts/runtime.py").write_text("pass\n", encoding="utf-8")
    entries = project / "learning.json"
    _write_json(entries, [{"id": "repeat-1", "lesson": "keep deterministic checks"}])
    common = (
        "self-improve",
        "--repository-root",
        ".",
        "--entries",
        entries.name,
        "--train-improved",
        "--rollback-record",
        "rollback-e2e",
        "--run-cap",
        "2",
        "--recurrence-confirmed",
        "--critic-passed",
    )
    project_paths = project / "project-paths.json"
    harness_paths = project / "harness-paths.json"
    _write_json(project_paths, ["src/service.py"])
    _write_json(harness_paths, ["scripts/runtime.py"])
    applied = _json_run(runtime, project, *common, "--paths", project_paths.name)
    proposed = _json_run(runtime, project, *common, "--paths", harness_paths.name)
    assert applied["change"]["tier"] == "project"
    assert applied["change"]["action"] == "APPLY"
    assert proposed["change"]["tier"] == "harness"
    assert proposed["change"]["action"] == "PROPOSAL"
    assert proposed["change"]["automatic_edit"] is False
    assert applied["knowledge_sync"]["status"] == "SKIPPED"

    unavailable = _run(runtime, project, "code-mapper", "--root", ".", "--symbol", "portable_service")
    unavailable_payload = json.loads(unavailable.stdout)
    assert unavailable.returncode == 2
    assert unavailable_payload["graph_state"] == "unavailable"
    assert unavailable_payload["fallback"]["approximate"] is True
    assert "not proven" in " ".join(unavailable_payload["limitations"])

    uninitialized_command = json.dumps(
        [sys.executable, "-c", "print('graph not initialized')"]
    )
    uninitialized = _run(
        runtime,
        project,
        "code-mapper",
        "--root",
        ".",
        "--symbol",
        "portable_service",
        "--graph-command",
        uninitialized_command,
    )
    assert json.loads(uninitialized.stdout)["graph_state"] == "not_initialized"

    healthy_payload = {
        "status": "ready",
        "entry_points": ["src/service.py"],
        "candidate_calls": ["portable_service"],
        "impact_scope": ["src/service.py"],
    }
    healthy_command = json.dumps(
        [sys.executable, "-c", f"import json; print(json.dumps({healthy_payload!r}))"]
    )
    healthy = _json_run(
        runtime,
        project,
        "code-mapper",
        "--root",
        ".",
        "--symbol",
        "portable_service",
        "--graph-command",
        healthy_command,
    )
    assert healthy["mode"] == "graph"
    assert healthy["graph_state"] == "healthy"


def test_result_evidence_maps_f1_through_f10_without_raw_secret() -> None:
    evidence_path = (
        ROOT
        / "docs/sdd/result/2026-07-14-codex-harness-parity-evidence.json"
    )
    result_path = ROOT / "docs/sdd/result/2026-07-14-codex-harness-parity.md"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["schema_version"] == 1
    assert evidence["feature"] == "codex-harness-parity"
    assert set(evidence["criteria"]) == {f"F{number}" for number in range(1, 11)}
    for criterion in evidence["criteria"].values():
        assert criterion["outcome"] == "PASS"
        assert criterion["evidence"]
        assert criterion["commands"]
    limitations = evidence["limitations"]
    assert limitations == [
        {
            "scope": "optional external CI/provider extension",
            "status": "NOT_EXECUTED",
            "completion_impact": "none",
            "reason": (
                "Hosted CI required checks, remote head identity, provider posting, "
                "export, and sharing are outside the trusted-local baseline and "
                "require explicit external configuration."
            ),
        }
    ]
    rendered = evidence_path.read_text(encoding="utf-8") + result_path.read_text(
        encoding="utf-8"
    )
    assert RAW_CREDENTIAL not in rendered
    assert "/Users/" not in rendered
