"""Public Orca CLI adapter. Unknown mutations never become blind retries."""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

from .contracts import ExecutionError, digest, require, within
from ..state.storage import atomic_write_json


def executable():
    if os.environ.get("ORCA_CLI_COMMAND"):
        return shlex.split(os.environ["ORCA_CLI_COMMAND"])
    if os.environ.get("ORCA_DEV_REPO_ROOT"):
        return ["orca-dev"]
    return ["orca-ide" if sys.platform.startswith("linux") else "orca"]


def rpc(engine, key, args, repeatable=False):
    argv = executable() + ["orchestration", *args, "--json"]
    requests = engine.s["requests"]
    prior = requests.get(key)
    if prior:
        require(prior["argv"] == argv, "request identity changed", "OUTCOME_UNKNOWN")
        if prior.get("receipt"):
            return engine.store.load(prior["receipt"])["result"]
        require(repeatable, "external request outcome unknown", "OUTCOME_UNKNOWN")
    requests[key] = {"argv": argv, "status": "INTENT"}
    engine.save("orca_intent", {"key": key, "argv": argv})
    try:
        result = subprocess.run(argv, cwd=engine.root, capture_output=True, text=True, timeout=65)
        payload = json.loads(result.stdout)
        receipt = {"argv": argv, "exit_code": result.returncode, "payload": payload, "stderr": result.stderr}
        proof = engine.store.object(receipt)
        requests[key]["observation"] = proof
        engine.save("orca_observed", {"key": key, "receipt": proof})
        require(result.returncode == 0 and payload.get("ok") is True, "Orca did not confirm the request", "OUTCOME_UNKNOWN")
        require(isinstance(payload.get("result"), dict), "unknown Orca receipt shape", "OUTCOME_UNKNOWN")
        requests[key].update(status="CONFIRMED", receipt=engine.store.object(payload))
        engine.save("orca_confirmed", {"key": key})
        return payload["result"]
    except (subprocess.TimeoutExpired, OSError, ValueError) as exc:
        raise ExecutionError("OUTCOME_UNKNOWN", f"Orca request needs reconciliation: {type(exc).__name__}") from exc


def launch(engine, node, attempt):
    try:
        if not engine.s.get("orca_run"):
            result = rpc(engine, "run", ["run-create", "--objective", f"Moondex {engine.s['run_id']}: {engine.bundle['goal']}"])
            engine.s["orca_run"] = result["run"]["id"]
            engine.save("orca_bound")
        submission = {"node_id": node["id"], "attempt_id": attempt["id"], "action_key": attempt["action_key"],
                      "bundle": engine.s["bundle"], "summary": "Describe the actual changes",
                      "criteria_review": {c: "Explain the observed behavior against this criterion" for c in node["criteria"]}}
        cli = Path(__file__).with_name("cli.py").resolve()
        assignment_path = within(engine.root, f".moondex/assignments/{node['id']}.json")
        atomic_write_json(assignment_path, engine.action(node["id"], attempt))
        submit_path = engine.root / ".moondex" / ("worker-" + node["id"] + ".json")
        command = shlex.join([sys.executable, str(cli), "--root", str(engine.root), "submit", "--file", str(submit_path)])
        spec = (f"Implement this approved Moondex node in {engine.root}. Current worktree only. "
                "Do not inspect other worktrees or change baseline/gate files. Do not spawn agents. "
                f"Node contract: {json.dumps(node, ensure_ascii=False)}. "
                f"Approved criteria: {json.dumps([c for c in engine.bundle['criteria'] if c['id'] in node['criteria']], ensure_ascii=False)}. "
                "The parent script independently runs required gates. "
                f"Read the script-owned current assignment from {assignment_path}; never edit it. "
                f"After implementation, write {submit_path} with node_id, attempt_id, bundle and action_key copied from that assignment, "
                "plus summary and criteria_review mapping each criterion ID to your actual observation. "
                f"Run {command}; on STATE_BUSY repeat the same submit, never edit STATE.json. "
                "Then report worker_done once with your injected IDs and actual outcome. End the dispatched turn. "
                "If blocked, ask through your injected Orca question command. Do not claim tests passed without running them.")
        previous = engine.s["nodes"][node["id"]]["attempts"][:-1]
        retry = previous[-1] if previous and previous[-1].get("worker_outcome") == "failed" else None
        if retry:
            attempt["orca_task"] = retry["orca_task"]
        else:
            task = rpc(engine, "task-" + attempt["id"], ["task-create", "--run", engine.s["orca_run"], "--spec", spec])
            attempt["orca_task"] = task["task"]["id"]
        engine.save("orca_task", {"node": node["id"]})
        args = ["worker-start", "--task", attempt["orca_task"], "--worktree", "current", "--agent", "codex"]
        if retry:
            # Keep the platform's failed-dispatch lineage/circuit breaker intact.
            # The unchanged task reads its new assignment; no undocumented task-spec update.
            args += ["--retry-of", retry["orca_dispatch"]]
        if node.get("model"):
            args += ["--model", node["model"]]
        if node.get("effort"):
            args += ["--effort", node["effort"]]
        result = rpc(engine, "launch-" + attempt["id"], args)
        attempt["orca_dispatch"] = result["dispatchId"]
        attempt["launch"] = result
        engine.save("orca_dispatched", {"node": node["id"]})
    except (ExecutionError, KeyError) as exc:
        engine.question("orca_unknown", str(exc), node["id"], {"attempt": attempt["id"]})


def reconcile(engine):
    if not engine.s.get("orca_run"):
        return
    try:
        # A fresh read has a fresh identity; request/receipt audit is durable.
        from .engine import uid
        for node_id, state in engine.s["nodes"].items():
            if not state["attempts"]:
                continue
            a = state["attempts"][-1]
            if a.get("orca_task") and not a.get("orca_dispatch"):
                found = rpc(engine, "lookup-" + uid(), ["dispatch-show", "--task", a["orca_task"]], repeatable=True)
                dispatch = found.get("dispatch") or {}
                require(dispatch.get("task_id") == a["orca_task"] and dispatch.get("run_id") == engine.s["orca_run"] and dispatch.get("id"),
                        "cannot prove existing dispatch ownership", "OUTCOME_UNKNOWN")
                a["orca_dispatch"] = dispatch["id"]
                for q in engine.s["questions"].values():
                    if q["kind"] == "orca_unknown" and q["node_id"] == node_id and q["status"] == "OPEN":
                        q.update(status="RESOLVED", reconciliation={"dispatch": dispatch["id"], "task": a["orca_task"]})
                engine.save("orca_reconnected", {"node": node_id, "dispatch": dispatch["id"]})
        payload = rpc(engine, "check-" + uid(), ["check", "--run", engine.s["orca_run"]], repeatable=True)
        messages = payload.get("messages")
        require(isinstance(messages, list), "unknown Delivery shape", "OUTCOME_UNKNOWN")
        if not messages:
            return
        identity = {k: payload[k] for k in ("runId", "deliveryId", "messages", "count")}
        require(identity["runId"] == engine.s["orca_run"], "wrong Run delivery", "OUTCOME_UNKNOWN")
        delivery_id = identity["deliveryId"]
        prior = engine.s["deliveries"].get(delivery_id)
        key = engine.store.object(identity)
        require(not prior or prior["object"] == key, "replayed Delivery content changed", "OUTCOME_UNKNOWN")
        engine.s["deliveries"][delivery_id] = {"object": key, "acked": False}
        engine.save("delivery_stored", {"delivery": delivery_id})
        for message in messages:
            mid = message["id"]
            mkey = engine.store.object(message)
            saved = engine.s["messages"].get(mid)
            require(not saved or saved["object"] == mkey, "replayed message changed", "OUTCOME_UNKNOWN")
            if saved and saved.get("applied"):
                continue
            engine.s["messages"][mid] = {"object": mkey, "applied": False}
            data = message.get("payload") or {}
            if isinstance(data, str):
                data = json.loads(data)
            matched = None
            for node_id, state in engine.s["nodes"].items():
                if state["attempts"]:
                    a = state["attempts"][-1]
                    if data.get("dispatchId") == a.get("orca_dispatch") and data.get("taskId") == a.get("orca_task") and a.get("orca_dispatch"):
                        matched = (node_id, a)
            if message["type"] == "worker_done":
                require(matched and message.get("run_id") == engine.s["orca_run"], "stale or foreign completion", "OUTCOME_UNKNOWN")
                node_id, attempt = matched
                result = rpc(engine, "release-" + attempt["id"], ["worker-release", "--dispatch", attempt["orca_dispatch"]], repeatable=True)
                if result.get("state") != "released":
                    engine.question("orca_unknown", "Worker release is not settled; follow recorded recovery receipt.", node_id, result)
                    return
                attempt.update(settled=True, release=result, worker_outcome=data.get("outcome"))
                if data.get("outcome") != "succeeded" or not attempt.get("submission"):
                    attempt.update(status="FAILED", failure={"kind": "worker_failed_or_missing_submission", "message": mkey})
                    engine.s["nodes"][node_id]["status"] = "FAILED"
            elif message["type"] in {"question", "escalation"}:
                node_id = matched[0] if matched else None
                engine.question("worker_question", message.get("body") or message.get("subject") or "Worker requests judgment", node_id,
                                {"orca_message": mid, "message": mkey})
            engine.s["messages"][mid]["applied"] = True
            engine.save("message_applied", {"message": mid})
        rpc(engine, "ack-" + delivery_id, ["check", "--run", engine.s["orca_run"], "--ack", delivery_id], repeatable=True)
        engine.s["deliveries"][delivery_id]["acked"] = True
        engine.save("delivery_acked", {"delivery": delivery_id})
    except (ExecutionError, KeyError, ValueError) as exc:
        engine.question("orca_unknown", str(exc), None)
