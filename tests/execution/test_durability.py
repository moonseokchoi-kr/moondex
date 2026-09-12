import copy
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from harness_core.execution.contracts import ExecutionError
from harness_core.execution.engine import Engine
from harness_core.execution.store import Store
from harness_core.execution import runner, orca
from test_execution import approved, bundle, implement, complete, until
from test_feedback_sync import knowledge, draft


def test_real_process_crash_after_event_before_snapshot(tmp_path):
    s = Store(tmp_path)
    with s.writer(): s.commit("initial", {"counter": 0})
    code = '''import os,sys
from pathlib import Path
import harness_core.execution.store as module
s=module.Store(Path(sys.argv[1]))
with s.writer():
    module.atomic_write_json=lambda *a,**kw: os._exit(89)
    s.commit('committed_before_crash',{'counter':1})
'''
    result = subprocess.run([sys.executable, "-c", code, str(tmp_path)])
    assert result.returncode == 89
    assert Store(tmp_path).status() == {"counter": 0}
    recovered = Store(tmp_path)
    with recovered.writer(): assert recovered.state == {"counter": 1}


def test_gate_launch_response_loss_reconnects_same_process(tmp_path, monkeypatch):
    e = approved(tmp_path)
    e.submit(implement(e, e.advance()))
    start = runner.start
    ids = []
    def crash(*args, **kwargs):
        result = start(*args, **kwargs)
        ids.append(result["id"])
        raise SystemExit(86)
    with monkeypatch.context() as m:
        m.setattr(runner, "start", crash)
        with pytest.raises(SystemExit): e.advance()
    time.sleep(.2)
    resumed = Engine(tmp_path)
    assert complete(resumed)["code"] == "COMPLETED"
    attempt = resumed.store.status()["nodes"]["N1"]["attempts"][0]
    assert resumed.store.load(attempt["receipts"][0])["id"] == ids[0]
    assert resumed.store.status()["nodes"]["N1"]["repairs"] == 0


def test_forged_process_receipt_cannot_become_pass(tmp_path):
    b = bundle(); b["gates"][0]["oracle"]["argv"][2] = "import time;time.sleep(.5)\n" + b["gates"][0]["oracle"]["argv"][2]
    e = approved(tmp_path, b)
    e.submit(implement(e, e.advance())); e.advance()
    handle = e.store.status()["nodes"]["N1"]["attempts"][-1]["process"]
    receipt = tmp_path / ".moondex/processes" / handle["id"] / "receipt.json"
    receipt.write_text('{"status":"PASS","verified":true}')
    with pytest.raises(ExecutionError, match="receipt does not match"): e.advance()
    # Allow the actual owned process to finish and overwrite the forged candidate.
    time.sleep(.6)
    assert complete(e)["code"] == "COMPLETED"


def test_event_symlink_never_writes_outside_runtime(tmp_path):
    outside = tmp_path / "outside.txt"; outside.write_text("unchanged")
    (tmp_path / ".moondex").mkdir()
    (tmp_path / ".moondex/events.jsonl").symlink_to(outside)
    with pytest.raises(ExecutionError): Store(tmp_path)
    assert outside.read_text() == "unchanged"


def test_compound_crash_after_write_reconciles_without_duplicate(tmp_path, monkeypatch):
    config = knowledge(tmp_path)
    b = bundle(); b["compound"] = config
    e = approved(tmp_path / "project", b)
    e.submit(implement(e, e.advance())); complete(e)
    proposal = draft(config)
    e.submit(proposal)
    original = Store.commit
    def crash(self, kind, state, detail=None):
        if kind == "compound_written": raise SystemExit(86)
        return original(self, kind, state, detail)
    with monkeypatch.context() as m:
        m.setattr(Store, "commit", crash)
        with pytest.raises(SystemExit): e.advance()
    assert Engine(e.root).advance()["code"] == "COMPLETED"
    for item in proposal["files"]:
        assert (Path(config["root"]) / item["path"]).read_text() == item["text"]


def test_unknown_orca_mutation_is_not_automatically_repeated(tmp_path, monkeypatch):
    e = approved(tmp_path)
    calls = []
    def lost(*args, **kwargs):
        calls.append(args)
        raise subprocess.TimeoutExpired(args[0], 1)
    monkeypatch.setattr(orca.subprocess, "run", lost)
    with e.store.writer():
        e.load()
        with pytest.raises(ExecutionError, match="reconciliation"):
            orca.rpc(e, "worker-create", ["worker-start", "--task", "test"])
    with e.store.writer():
        e.load()
        with pytest.raises(ExecutionError, match="outcome unknown"):
            orca.rpc(e, "worker-create", ["worker-start", "--task", "test"])
    assert len(calls) == 1


def test_folder_writer_conflicts_with_descendant_reader(tmp_path):
    e = Engine(tmp_path)
    writer = {"executor": "orca", "write_scope": ["src"], "inputs": ["src"]}
    reader = {"executor": "orca", "write_scope": ["out"], "inputs": ["src/file.py", "out"]}
    assert e.conflict(writer, [reader])
    assert e.conflict(reader, [writer])


def test_old_pid_without_matching_supervisor_is_not_alive(tmp_path):
    b = bundle(); gate = b["gates"][0]
    directory = tmp_path / ".moondex/processes/identity"
    directory.mkdir(parents=True)
    request = {"gate": gate}
    (directory / "request.json").write_text(json.dumps(request))
    from harness_core.execution.contracts import digest
    result = runner.observe(tmp_path, {"id": "identity", "pid": os.getpid(), "request_digest": digest(request)})
    assert result["status"] == "LOST"


def test_worker_question_returns_ai_judgment_not_user_gate(tmp_path, monkeypatch):
    e = approved(tmp_path)
    e.advance()
    with e.store.writer():
        e.load()
        q = e.question("worker_question", "Which approved value?", "N1", {"orca_message": "message-1"})
    action = e.advance()
    assert action["kind"] == "worker_question"
    calls = []
    monkeypatch.setattr(orca, "rpc", lambda engine, key, args, **kw: calls.append(args) or {})
    e.submit({"kind": "judgment", "question_id": q["id"], "bundle": q["bundle"], "summary": "C1 already specifies 42", "decision": "reply", "text": "Use 42 as approved in C1."})
    assert calls[0][:3] == ["reply", "--id", "message-1"]
    assert e.store.status()["questions"][q["id"]]["actor"] == "current_ai"
    assert e.advance()["kind"] == "implement"


def test_unknown_launch_reconciles_existing_dispatch_without_another_start(tmp_path, monkeypatch):
    e = approved(tmp_path)
    calls = []
    def transport(engine, key, args, **kw):
        calls.append(args)
        if args[0] == "dispatch-show":
            return {"dispatch": {"id": "dispatch-1", "task_id": "task-1", "run_id": "run-1"}}
        return {"messages": []}
    monkeypatch.setattr(orca, "rpc", transport)
    with e.store.writer():
        e.load()
        a = e.new_attempt("N1")
        a.update(orca_task="task-1", settled=False)
        e.s["orca_run"] = "run-1"
        q = e.question("orca_unknown", "response lost", "N1")
        orca.reconcile(e)
        assert a["orca_dispatch"] == "dispatch-1"
        assert q["status"] == "RESOLVED"
    assert all(args[0] != "worker-start" for args in calls)


def test_failed_worker_retry_preserves_orca_task_lineage(tmp_path, monkeypatch):
    b = bundle(); b["nodes"][0]["executor"] = "orca"
    e = approved(tmp_path, b)
    calls = []
    def transport(engine, key, args, **kw):
        calls.append(args)
        assert args[0] == "worker-start"
        return {"dispatchId": "new-dispatch", "state": "ready"}
    monkeypatch.setattr(orca, "rpc", transport)
    with e.store.writer():
        e.load()
        first = e.new_attempt("N1")
        first.update(worker_outcome="failed", orca_task="same-task", orca_dispatch="old-dispatch", failure={"kind": "worker_failure"})
        e.s["orca_run"] = "same-run"
        second = e.new_attempt("N1")
        orca.launch(e, e.node("N1"), second)
    assert calls == [["worker-start", "--task", "same-task", "--worktree", "current", "--agent", "codex", "--retry-of", "old-dispatch"]]
    assignment = json.loads((tmp_path / ".moondex/assignments/N1.json").read_text())
    assert assignment["attempt_id"] == second["id"]
