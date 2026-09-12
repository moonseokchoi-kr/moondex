"""Observable contracts: wrong behavior must never become a completed run."""
import copy
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from harness_core.execution.contracts import ExecutionError, digest, validate
from harness_core.execution.engine import Engine
from harness_core.execution.store import Store


CHECK = """import json,sys
from pathlib import Path
value = int(Path('src/value.txt').read_text())
if sys.argv[2] == 'defect': value += 1
ok = value == 42
Path(sys.argv[1]).write_text(json.dumps({'tests':1,'failures':int(not ok),'criteria':{'C1':ok}}))
sys.exit(0 if ok else 1)
"""


def bundle():
    return {"schema_version": 1, "feature": "example", "revision": "r1", "goal": "Produce the agreed answer",
            "before": "answer missing", "after": "answer is 42", "sources": [{"source": "fixture user", "text": "Return 42"}],
            "design": ["Store the answer in src/value.txt"], "exclusions": ["No deployment"],
            "criteria": [{"id": "C1", "requirement": "R1", "input": "fixture", "action": "read value", "expected": "42", "failure": "43"}],
            "inputs": ["src"], "policy": {"concurrency": 1, "recovery_attempts": 2, "time_limit": None, "token_limit": None},
            "verification": {k: {"required": k == "unit", "reason": "small local data fixture"} for k in ("build", "unit", "integration", "e2e")},
            "gates": [{"id": "answer", "kind": "unit", "argv": [sys.executable, "-c", CHECK, "{report}", "actual"],
                       "format": "json", "min_tests": 1, "criteria": ["C1"],
                       "oracle": {"argv": [sys.executable, "-c", CHECK, "{report}", "defect"], "reason": "off-by-one must fail"}}],
            "nodes": [{"id": "N1", "goal": "write 42", "executor": "current", "inputs": ["src"], "write_scope": ["src"],
                       "outputs": ["src/value.txt"], "depends_on": [], "criteria": ["C1"], "gates": ["answer"], "locks": [], "split_rationale": "one small task"}],
            "integration_gates": ["answer"], "compound": {"enabled": False}}


def approved(tmp_path, spec=None):
    e = Engine(tmp_path)
    ready = e.prepare(spec or bundle())
    e.approve(ready["digest"], "Implement the fixture", "test user message")
    return e


def implement(e, action, value=42):
    (e.root / "src").mkdir(exist_ok=True)
    (e.root / "src/value.txt").write_text(str(value))
    submission = {k: action[k] for k in ("node_id", "attempt_id", "bundle", "action_key")}
    submission.update(summary=f"Wrote {value}", criteria_review={"C1": f"The saved value is {value}; the gate independently checks 42."})
    return submission


def until(e, wanted, limit=15):
    deadline = time.monotonic() + limit
    while time.monotonic() < deadline:
        r = e.advance()
        if wanted(r):
            return r
        time.sleep(.025)
    raise AssertionError((r, e.store.status()))


def complete(e):
    review = until(e, lambda r: r.get("kind") == "integration_review")
    e.submit({"kind": "integration_review", "action_key": review["action_key"], "summary": "Actual answer observed",
              "criteria_review": {"C1": "Both actual and off-by-one oracle receipts checked against 42."}})
    return e.advance()


def test_current_session_real_gate_and_integration(tmp_path):
    e = approved(tmp_path)
    a = e.advance()
    assert a["code"] == "ACTION"
    assert e.advance()["attempt_id"] == a["attempt_id"]
    s = implement(e, a)
    assert e.submit(s)["code"] == "SUBMITTED"
    assert e.submit(s)["duplicate"]
    assert complete(e)["code"] == "COMPLETED"
    state = Store(tmp_path).status()
    assert len(state["nodes"]["N1"]["attempts"]) == 1
    assert len(state["integration"]["receipts"]) == 2
    assert not (tmp_path / "docs/sdd").exists()


@pytest.mark.parametrize("mutation", ["cycle", "gate", "criterion", "scope", "zero"])
def test_contract_rejects_unexecutable_intent(mutation):
    b = bundle()
    if mutation == "cycle": b["nodes"][0]["depends_on"] = ["N1"]
    elif mutation == "gate": b["nodes"][0]["gates"] = []
    elif mutation == "criterion": b["criteria"][0]["expected"] = ""
    elif mutation == "scope": b["nodes"][0]["write_scope"] = ["../outside"]
    else: b["gates"][0]["min_tests"] = 0
    with pytest.raises(ExecutionError): validate(b)


def test_approval_binds_actual_revision_and_tamper(tmp_path):
    e = Engine(tmp_path)
    p = e.prepare(bundle())
    with pytest.raises(ExecutionError, match="different bundle"):
        e.approve("0" * 64, "yes", "user")
    with pytest.raises(ExecutionError, match="approval required"):
        e.advance()
    e.approve(p["digest"], "yes", "user")
    target = tmp_path / p["revision_path"]
    b = json.loads(target.read_text()); b["criteria"][0]["expected"] = "43"
    target.write_text(json.dumps(b))
    with pytest.raises(ExecutionError, match="revision changed"):
        e.advance()


def test_wrong_implementation_repairs_twice_then_intervenes(tmp_path):
    e = approved(tmp_path)
    a = e.advance()
    for i in range(3):
        e.submit(implement(e, a, 41))
        r = until(e, lambda r: r["code"] in {"ACTION", "WAITING_USER"})
        if i < 2:
            assert r["kind"] == "repair"
            a = r
        else:
            assert r["code"] == "WAITING_USER"
    assert e.store.status()["nodes"]["N1"]["repairs"] == 2
    q = r["questions"][0]
    e.answer(q["id"], q["bundle"], "One additional repair is authorized", "user", "one_more_repair")
    assert e.answer(q["id"], q["bundle"], "One additional repair is authorized", "user", "one_more_repair")["duplicate"]
    a = e.advance()
    e.submit(implement(e, a, 42))
    assert complete(e)["code"] == "COMPLETED"


def test_forged_submission_and_stale_assignment_rejected(tmp_path):
    e = approved(tmp_path)
    a = e.advance()
    s = implement(e, a)
    s["attempt_id"] = "stale"
    with pytest.raises(ExecutionError, match="stale assignment"): e.submit(s)
    s["attempt_id"] = a["attempt_id"]
    s.pop("criteria_review")
    s["verified"] = True
    with pytest.raises(ExecutionError, match="intent review"): e.submit(s)
    assert e.store.status()["nodes"]["N1"]["status"] == "RUNNING"


def test_submit_then_parent_restart_before_advance(tmp_path):
    e = approved(tmp_path)
    e.submit(implement(e, e.advance()))
    resumed = Engine(tmp_path)
    assert complete(resumed)["code"] == "COMPLETED"
    assert len(resumed.store.status()["nodes"]["N1"]["attempts"]) == 1


def test_snapshot_loss_and_torn_tail_preserve_committed_state(tmp_path):
    e = approved(tmp_path)
    a = e.advance()
    (tmp_path / ".moondex/STATE.json").write_text("broken")
    with (tmp_path / ".moondex/events.jsonl").open("ab") as f:
        f.write(b'{"partial":')
    assert Engine(tmp_path).advance()["attempt_id"] == a["attempt_id"]
    assert list((tmp_path / ".moondex").glob("torn-*.bin"))


def test_mid_history_corruption_is_not_silently_reset(tmp_path):
    e = approved(tmp_path)
    path = tmp_path / ".moondex/events.jsonl"
    path.write_bytes(path.read_bytes().replace(b'"prepared"', b'"forged"', 1))
    with pytest.raises(ExecutionError, match="corrupt committed event"): e.advance()


def test_two_real_process_writers_do_not_duplicate_assignment(tmp_path):
    e = approved(tmp_path)
    cli = Path(__file__).resolve().parents[2] / "harness_core/execution/cli.py"
    processes = [subprocess.Popen([sys.executable, str(cli), "--root", str(tmp_path), "advance"], stdout=subprocess.PIPE) for _ in range(2)]
    results = [json.loads(p.communicate()[0]) for p in processes]
    ids = {r["attempt_id"] for r in results if r["code"] == "ACTION"}
    assert len(ids) == 1
    assert all(r["code"] in {"ACTION", "STATE_BUSY"} for r in results)
    assert len(e.store.status()["nodes"]["N1"]["attempts"]) == 1


def test_zero_collected_tests_never_complete(tmp_path):
    b = bundle()
    b["gates"][0]["argv"] = [sys.executable, "-c", "import sys,json;from pathlib import Path;Path(sys.argv[1]).write_text(json.dumps({'tests':0,'failures':0,'criteria':{'C1':True}}))", "{report}"]
    e = approved(tmp_path, b)
    e.submit(implement(e, e.advance()))
    r = until(e, lambda r: r.get("kind") == "repair")
    assert r["failure"]["kind"] == "verification_failed"
    assert not e.store.status()["integration"]


def test_live_test_wait_does_not_count_as_failure(tmp_path):
    b = bundle()
    b["gates"][0]["oracle"]["argv"][2] = "import time;time.sleep(.8)\n" + CHECK
    e = approved(tmp_path, b)
    e.submit(implement(e, e.advance()))
    assert e.advance()["code"] == "WAITING_PROCESS"
    for _ in range(5):
        assert e.advance()["code"] == "WAITING_PROCESS"
    assert e.store.status()["nodes"]["N1"]["repairs"] == 0
    assert complete(e)["code"] == "COMPLETED"


def test_tree_change_after_submission_invalidates_candidate(tmp_path):
    e = approved(tmp_path)
    e.submit(implement(e, e.advance()))
    (tmp_path / "src/value.txt").write_text("43")
    result = e.advance()
    assert result["kind"] == "repair"
    assert result["failure"]["kind"] == "source_changed_after_submission"


def test_status_read_only_and_cancel_does_not_restart(tmp_path):
    e = approved(tmp_path)
    a = e.advance()
    path = tmp_path / ".moondex/events.jsonl"
    before = path.read_bytes()
    assert e.store.status()["nodes"]["N1"]["status"] == "RUNNING"
    assert path.read_bytes() == before
    assert e.cancel("user requested cancellation")["remaining"]
    assert e.advance()["code"] == "CANCELLED"
    with pytest.raises(ExecutionError): e.submit(implement(e, a))
    with pytest.raises(ExecutionError, match="still owns live resources"): e.prepare(bundle())
    state = e.store.status()
    q = next(q for q in state["questions"].values() if q["kind"] == "cancel_resources")
    assert e.cancel("repeat")["duplicate"]
    with pytest.raises(ExecutionError): e.answer(q["id"], state["bundle"], "continue", "user", "continue")
    result = e.answer(q["id"], state["bundle"], "Current AI action ended; no child process was launched.", "user stop confirmation", "confirmed_stopped")
    assert result == {"code": "CANCELLED", "remaining": {}}
    assert e.advance()["code"] == "CANCELLED"
    with pytest.raises(ExecutionError): e.feedback("ambiguous", [], "restart cancelled work")
    assert e.prepare(bundle())["code"] == "WAITING_USER"


def test_draft_approval_never_changes_old_sdd_records(tmp_path):
    old = tmp_path / "docs/sdd/past.md"
    old.parent.mkdir(parents=True); old.write_text("historical approval=true")
    e = approved(tmp_path)
    e.submit(implement(e, e.advance()))
    assert complete(e)["code"] == "COMPLETED"
    assert old.read_text() == "historical approval=true"
