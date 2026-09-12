"""One observed gate process. It never schedules another task after session exit."""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    __package__ = "harness_core.execution"

from .contracts import digest, read_json, require, within
from .store import source_snapshot
from ..state.storage import atomic_write_json, exclusive_lock


def report_result(path, gate):
    try:
        if gate["format"] == "junit":
            root = ET.parse(path).getroot()
            cases = list(root.iter("testcase"))
            count = len(cases)
            failures = sum(any(c.tag in {"failure", "error", "skipped"} for c in case) for case in cases)
            return {"count": count, "failures": failures, "pass": count >= gate["min_tests"] and failures == 0}
        value = read_json(path)
        count, failures = value.get("tests"), value.get("failures")
        ok = type(count) is int and count >= gate["min_tests"] and failures == 0 and type(failures) is int
        ok = ok and all(value.get("criteria", {}).get(c) is True for c in gate["criteria"])
        return {"count": count, "failures": failures, "pass": bool(ok)}
    except Exception:
        return {"count": 0, "pass": False, "error": "missing or invalid structured report"}


def start(root, gate, scopes, binding, negative=False, run_id=None):
    run_id = run_id or uuid.uuid4().hex
    directory = within(root, f".moondex/processes/{run_id}")
    directory.mkdir(parents=True, mode=0o700)
    request = {"gate": gate, "scopes": scopes, "binding": binding, "negative": negative, "id": run_id}
    atomic_write_json(directory / "request.json", request)
    # Receipt and ownership lock are written by the actual observing process.
    script = Path(__file__).resolve()
    with (directory / "supervisor.log").open("wb") as log:
        process = subprocess.Popen([sys.executable, str(script), "--root", str(root), "--id", run_id],
                                   stdout=log, stderr=log, start_new_session=True)
    return {"id": run_id, "pid": process.pid, "request_digest": digest(request), "started": time.time()}


def recover_handle(root, run_id):
    directory = within(root, f".moondex/processes/{run_id}")
    for name in ("receipt.json", "running.json"):
        if (directory / name).exists():
            receipt = read_json(directory / name)
            return {"id": run_id, "pid": receipt["pid"], "request_digest": digest(read_json(directory / "request.json")), "started": receipt["started"]}
    return None


def observe(root, handle):
    directory = within(root, f".moondex/processes/{handle['id']}")
    request = read_json(directory / "request.json")
    require(digest(request) == handle["request_digest"], "gate request changed", "EVIDENCE_INVALID")
    receipt = directory / "receipt.json"
    if receipt.exists():
        value = read_json(receipt)
        require(value.get("id") == handle["id"] and value.get("pid") == handle["pid"] and value.get("provenance") == "runner-observed"
                and value.get("gate_digest") == digest(request["gate"]) and value.get("binding") == request["binding"],
                "receipt does not match observed process request", "EVIDENCE_INVALID")
        if value.get("status") == "PASS":
            import hashlib
            require(value.get("logs") and all(hashlib.sha256((directory / name).read_bytes()).hexdigest() == proof for name, proof in value["logs"].items()),
                    "gate log changed", "EVIDENCE_INVALID")
            actual = report_result(directory / "assertions.json", request["gate"])
            require(actual == value.get("assertions"), "assertion report changed", "EVIDENCE_INVALID")
        return value
    try:
        os.kill(handle["pid"], 0)
        identity = subprocess.run(["ps", "-p", str(handle["pid"]), "-o", "args="], capture_output=True, text=True)
        if handle["id"] not in identity.stdout or str(Path(__file__).resolve()) not in identity.stdout:
            return {"status": "LOST", "id": handle["id"], "reason": "supervisor identity no longer matches PID"}
        return {"status": "RUNNING", "id": handle["id"]}
    except ProcessLookupError:
        return {"status": "LOST", "id": handle["id"], "reason": "supervisor exited without receipt"}


def run(root, run_id):
    directory = within(root, f".moondex/processes/{run_id}")
    with exclusive_lock(directory / "owner.lock"):
        request = read_json(directory / "request.json")
        gate = request["gate"]
        report = directory / "assertions.json"
        argv = gate["oracle"]["argv"] if request["negative"] else gate["argv"]
        argv = [a.replace("{report}", str(report)) for a in argv]
        cwd = within(root, gate.get("cwd", "."))
        before = source_snapshot(root, request["scopes"])
        receipt = {"id": run_id, "binding": request["binding"], "gate_digest": digest(gate),
                   "request_digest": digest(request),
                   "provenance": "runner-observed", "negative": request["negative"],
                   "argv": argv, "cwd": str(cwd), "started": time.time(), "pid": os.getpid(),
                   "environment": {"python": sys.version, "platform": platform.platform()},
                   "inputs": before, "status": "RUNNING"}
        atomic_write_json(directory / "running.json", receipt)
        try:
            with (directory / "stdout.log").open("wb") as stdout, (directory / "stderr.log").open("wb") as stderr:
                process = subprocess.Popen(argv, cwd=cwd, stdout=stdout, stderr=stderr)
                receipt["child_pid"] = process.pid
                atomic_write_json(directory / "running.json", receipt)
                code = process.wait()  # no wall-clock limit on required verification
            assertions = report_result(report, gate)
            after = source_snapshot(root, request["scopes"])
            receipt.update(exit_code=code, assertions=assertions, finished=time.time(), input_digest=digest(before))
            if request["negative"]:
                passed = code != 0 and assertions.get("count", 0) and not assertions["pass"]
            else:
                passed = code == 0 and assertions["pass"]
            receipt["status"] = "PASS" if passed and before == after else "FAIL"
            receipt["tree_changed"] = before != after
            import hashlib
            receipt["logs"] = {name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
                               for name in ("stdout.log", "stderr.log")}
        except Exception as exc:
            receipt.update(status="FAIL", error=type(exc).__name__, finished=time.time())
        atomic_write_json(directory / "receipt.json", receipt)


if __name__ == "__main__":
    # Direct script launches must resolve imports without a consumer PYTHONPATH.
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--id", required=True)
    args = parser.parse_args()
    run(args.root.resolve(), args.id)
