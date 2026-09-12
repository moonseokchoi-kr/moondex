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
    state = destination / ".harness/state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "tdd-manifest.json").write_text(json.dumps({"red_evidence":"panel behavior regression", "green_command":"python3 tests/consumer_panel_e2e.py"}))
    (state / "e2e-config.json").write_text(json.dumps({"command":"python3 tests/consumer_panel_e2e.py"}))
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

def _production_browser_bundle(project: Path, runtime: Path) -> dict:
    b = json.loads((ROOT / "tests/fixtures/execution/bundle.json").read_text())
    b.update(feature="browser-execution", inputs=["src", "web", "tests"])
    b["criteria"][0].update(action="Click Complete in rendered panel", expected="Status Complete and aria-pressed true", failure="button with no effect")
    b["nodes"][0].update(goal="Implement observable panel behavior", inputs=["src", "web", "tests"], write_scope=["src", "web"], outputs=["web/Panel.tsx"], gates=["browser", "policy"])
    code = '''import json,sys,subprocess,tempfile,shutil
from pathlib import Path
root=Path.cwd()
with tempfile.TemporaryDirectory() as tmp:
    if sys.argv[2]=='defect':
        check=Path(tmp)
        for d in ['web','tests']: shutil.copytree(root/d,check/d)
        p=check/'web/Panel.tsx'
        p.write_text(p.read_text().replace('status.textContent = "Complete";', 'status.textContent = "Ready";'))
    else: check=root
    r=subprocess.run([sys.executable,'tests/consumer_panel_e2e.py'],cwd=check,capture_output=True,text=True)
    print(r.stdout);print(r.stderr,file=sys.stderr)
    ok=r.returncode==0
    Path(sys.argv[1]).write_text(json.dumps({'tests':1,'failures':int(not ok),'criteria':{'C1':ok}}))
    sys.exit(0 if ok else 1)
'''
    definitions={str(p.relative_to(project)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (project/'tests').glob('*') if p.is_file()}
    browser={"id":"browser","kind":"e2e","criteria":["C1"],"format":"json","min_tests":1,"definitions":definitions,
             "argv":[sys.executable,"-c",code,"{report}","actual"],"oracle":{"argv":[sys.executable,"-c",code,"{report}","defect"],"reason":"Rendered click must change state; source strings are insufficient"}}
    policy_code = '''import json,sys,subprocess
from pathlib import Path
r=subprocess.run([sys.executable,sys.argv[3],'verify','--project-root','.','--source','explicit','--branch',('main' if sys.argv[2]=='defect' else 'feature/browser'),'--changed-file','web/Panel.tsx'],capture_output=True,text=True)
print(r.stdout);print(r.stderr,file=sys.stderr)
ok=r.returncode==0
Path(sys.argv[1]).write_text(json.dumps({'tests':1,'failures':int(not ok),'criteria':{'C1':ok}}))
sys.exit(0 if ok else 1)
'''
    # Runtime is an installed, inventory-validated external tool, carried in argv as data.
    policy={"id":"policy","kind":"integration","criteria":["C1"],"format":"json","min_tests":1,
            "argv":[sys.executable,"-c",policy_code,"{report}","actual",str(runtime)],
            "oracle":{"argv":[sys.executable,"-c",policy_code,"{report}","defect",str(runtime)],"reason":"Default-branch implementation must fail"}}
    policy['tools']={str(runtime):hashlib.sha256(runtime.read_bytes()).hexdigest()}
    b['gates']=[browser,policy];b['integration_gates']=['browser','policy']
    b['verification']={k:{'required':k in {'e2e','integration'},'reason':'Browser fixture with policy check'} for k in ('build','unit','integration','e2e')}
    return b


def _production_start(project: Path, runtime: Path):
    b=_production_browser_bundle(project,runtime)
    _write_json(project/'bundle.json',b)
    ready=_json_run(runtime,project,'execute','prepare','--file','bundle.json')
    _json_run(runtime,project,'execute','approve','--digest',ready['digest'],'--quote','Implement browser fixture','--source','test user')
    return _json_run(runtime,project,'execute','advance')


def _production_submit(project: Path, runtime: Path, assignment: dict):
    submission={k:assignment[k] for k in ('node_id','attempt_id','bundle','action_key')}
    submission.update(summary='Panel implementation ready for browser verification',criteria_review={'C1':'The click handler is implemented; script must verify the rendered state transition.'})
    _write_json(project/'submission.json',submission)
    return _json_run(runtime,project,'execute','submit','--file','submission.json')


def _production_observe(project: Path, runtime: Path):
    import time
    deadline=time.monotonic()+90
    while time.monotonic()<deadline:
        result=_json_run(runtime,project,'execute','advance')
        if result['code']=='ACTION' or result['code']=='COMPLETED': return result
        time.sleep(.05)
    raise AssertionError(result)


def test_clean_environment_production_execution_and_browser_result(tmp_path: Path) -> None:
    project=_project(tmp_path)
    installation,runtime=_opaque_runtime(tmp_path)
    before=_snapshot(installation)
    a=_production_start(project,runtime)
    _production_submit(project,runtime,a)
    review=_production_observe(project,runtime)
    assert review['kind']=='integration_review',review
    _write_json(project/'review.json',{'kind':'integration_review','action_key':review['action_key'],'summary':'Actual browser and policy receipts reviewed','criteria_review':{'C1':'Rendered click changes both status and aria-pressed; deliberately broken handler fails.'}})
    _json_run(runtime,project,'execute','submit','--file','review.json')
    result=_json_run(runtime,project,'execute','advance')
    assert result['code']=='COMPLETED'
    assert (project/result['report']).is_file()
    assert not (project/'.harness/state/pipeline.json').exists()
    assert _snapshot(installation)==before


@pytest.mark.parametrize('failure',('consumer-e2e','shared-verify'))
def test_production_blocks_completion_when_required_gate_fails(tmp_path: Path, failure: str) -> None:
    project=_project(tmp_path,failure)
    _,runtime=_opaque_runtime(tmp_path/failure)
    a=_production_start(project,runtime)
    if failure=='consumer-e2e':
        p=project/'web/Panel.tsx'
        p.write_text(p.read_text().replace('status.textContent = "Complete";', 'status.textContent = "Ready";'))
    else:
        (project/'.harness/state/e2e-config.json').unlink()
    _production_submit(project,runtime,a)
    result=_production_observe(project,runtime)
    assert result['kind']=='repair',result
    assert not (project/'docs/execution/browser-execution/results').exists()
