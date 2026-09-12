"""Deterministic progress. The AI receives judgment work, never chooses ready nodes."""
from __future__ import annotations

import copy
import time
import uuid
from pathlib import Path

from .contracts import ExecutionError, covered, digest, identifier, nonempty, require, validate, within
from .store import Store, changed, source_snapshot
from . import runner
from ..state.storage import atomic_write_json
from scripts.adapter_render import redact


def uid():
    return uuid.uuid4().hex


class Engine:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.store = Store(self.root)
        self.s = None
        self.bundle = None

    def load(self, check_definitions=True):
        self.s = copy.deepcopy(self.store.state)
        require(self.s is not None, "prepare an execution bundle first", "NOT_STARTED")
        self.bundle = self.store.load(self.s["bundle"])
        validate(self.bundle)
        # The durable revision file is independently protected from local object tampering.
        from .contracts import read_json
        original = read_json(within(self.root, self.s["revision_path"]))
        require(digest(original) == self.s["bundle"], "approved revision changed", "BASELINE_CHANGED")
        import hashlib
        for gate in self.bundle["gates"] if check_definitions else []:
            for path, proof in gate.get("definitions", {}).items():
                file = within(self.root, path)
                require(file.is_file() and hashlib.sha256(file.read_bytes()).hexdigest() == proof,
                        "verification definition changed without a revision", "BASELINE_CHANGED")
            for path, proof in gate.get("tools", {}).items():
                file = Path(path)
                require(file.is_file() and hashlib.sha256(file.read_bytes()).hexdigest() == proof,
                        "verification tool changed without a revision", "BASELINE_CHANGED")
        if self.s.get("approval"):
            approval = self.store.load(self.s["approval"])
            require(approval["digest"] == self.s["approved_digest"], "approval target mismatch", "BASELINE_CHANGED")

    def save(self, event, detail=None):
        if event in {"progress", "waiting_user"} and self.s == self.store.state:
            return
        self.store.commit(event, self.s, detail)

    def node(self, key):
        return next(n for n in self.bundle["nodes"] if n["id"] == key)

    def prepare(self, bundle):
        validate(bundle)
        with self.store.writer():
            prior = self.store.state
            require(prior is None or prior["status"] in {"COMPLETED", "CANCELLED"}, "one active run per worktree", "ACTIVE_RUN")
            require(not prior or not prior.get("cancel", {}).get("remaining"), "cancelled run still owns live resources", "RECOVERY_REQUIRED")
            key = self.store.object(bundle)
            path = f"docs/execution/{bundle['feature']}/revisions/{bundle['revision']}-{key}.json"
            target = within(self.root, path)
            if target.exists():
                from .contracts import read_json
                require(digest(read_json(target)) == key, "revision already changed", "BASELINE_CHANGED")
            else:
                atomic_write_json(target, bundle)
            self.s = {"schema_version": 1, "run_id": uid(), "feature": bundle["feature"],
                      "bundle": key, "approved_digest": key, "revision_path": path, "approval": None,
                      "status": "DRAFT", "nodes": {n["id"]: {"status": "PENDING", "attempts": [], "repairs": 0} for n in bundle["nodes"]},
                      "questions": {}, "history": [], "integration": None, "requests": {}, "messages": {}, "deliveries": {},
                      "created": time.time()}
            self.save("prepared")
            return {"code": "WAITING_USER", "digest": key, "revision_path": path}

    def approve(self, target, quote, source):
        require(nonempty(quote) and nonempty(source), "actual user quote and source required")
        with self.store.writer():
            self.load()
            require(target == self.s["bundle"], "approval targets different bundle", "APPROVAL_MISMATCH")
            require(self.s["status"] in {"DRAFT", "READY"}, "cannot approve current run state")
            record = {"actor": "user", "digest": target, "quote": quote, "source": source}
            key = self.store.object(record)
            atomic_write_json(within(self.root, f"docs/execution/{self.s['feature']}/approvals/{key}.json"), record)
            self.s.update(approval=key, approved_digest=target, status="READY")
            self.save("approved", {"approval": key})
            return {"code": "READY", "run_id": self.s["run_id"]}

    def binding(self, node_id, attempt):
        return {"run_id": self.s["run_id"], "bundle": self.s["bundle"], "node_id": node_id, "attempt_id": attempt["id"]}

    def question(self, kind, reason, node_id=None, detail=None):
        for q in self.s["questions"].values():
            if q["status"] == "OPEN" and q["kind"] == kind and q["node_id"] == node_id:
                return q
        q = {"id": uid(), "kind": kind, "reason": reason, "node_id": node_id, "bundle": self.s["bundle"],
             "status": "OPEN", "detail": detail or {}, "created": time.time()}
        self.s["questions"][q["id"]] = q
        self.s["status"] = "WAITING_USER"
        self.save("question", q)
        return q

    def current_attempt(self, node_id):
        return self.s["nodes"][node_id]["attempts"][-1]

    def action(self, node_id, attempt, kind="implement"):
        return {"code": "ACTION", "kind": kind, **self.binding(node_id, attempt), "action_key": attempt["action_key"],
                "node": self.node(node_id), "failure": attempt.get("failure"),
                "next": "submit the scoped result, then advance"}

    def new_attempt(self, node_id):
        n = self.node(node_id)
        state = self.s["nodes"][node_id]
        attempt = {"id": uid(), "action_key": uid(), "started": time.time(), "status": "RUNNING",
                   "input_snapshot": source_snapshot(self.root, n["inputs"]),
                   "scope_snapshot": source_snapshot(self.root, self.bundle["inputs"]),
                   "receipts": [], "queue": None, "process": None, "submission": None,
                   "settled": n["executor"] == "current"}
        if state["attempts"]:
            attempt["failure"] = state["attempts"][-1].get("failure")
        state["attempts"].append(attempt)
        state["status"] = "RUNNING"
        self.save("attempt_started", self.binding(node_id, attempt))
        return attempt

    def submit(self, submission):
        with self.store.writer():
            self.load()
            require(self.s["status"] not in {"CANCELLED", "COMPLETED", "DRAFT"}, "run does not accept results", "STALE_RESULT")
            if submission.get("kind") == "compound":
                from .compound import accept
                require(self.s.get("integration", {}).get("review"), "integration review required before recording")
                return accept(self, submission)
            if submission.get("kind") == "judgment":
                q = self.s["questions"].get(submission.get("question_id"))
                require(q and q["kind"] == "worker_question" and q["status"] == "OPEN" and submission.get("bundle") == q["bundle"] == self.s["bundle"],
                        "stale judgment request", "STALE_RESULT")
                require(nonempty(submission.get("summary")), "judgment rationale required")
                if submission.get("decision") == "request_user":
                    q.update(kind="user_decision", reason=submission["summary"])
                else:
                    require(submission.get("decision") == "reply" and nonempty(submission.get("text")), "reply or request_user required")
                    from .orca import rpc
                    rpc(self, "judgment-" + q["id"], ["reply", "--id", q["detail"]["orca_message"], "--body", submission["text"]])
                    q.update(status="RESOLVED", judgment=self.store.object(submission), actor="current_ai")
                self.save("judgment_submitted", {"question": q["id"]})
                return {"code": "SUBMITTED"}
            if submission.get("kind") == "integration_review":
                integration = self.s["integration"]
                require(integration and integration.get("verified") and submission.get("action_key") == integration["action_key"], "stale integration review", "STALE_RESULT")
                self.review(submission, [c["id"] for c in self.bundle["criteria"]])
                require(source_snapshot(self.root, self.bundle["inputs"]) == integration["snapshot"], "tree changed before review", "STALE_RESULT")
                integration["review"] = self.store.object(submission)
                self.save("integration_reviewed")
                return {"code": "SUBMITTED"}
            node_id = submission.get("node_id")
            require(node_id in self.s["nodes"] and self.s["nodes"][node_id]["attempts"], "unknown assignment", "STALE_RESULT")
            attempt = self.current_attempt(node_id)
            require(submission.get("attempt_id") == attempt["id"] and submission.get("action_key") == attempt["action_key"] and submission.get("bundle") == self.s["bundle"], "stale assignment", "STALE_RESULT")
            key = self.store.object(submission)
            if attempt.get("submission"):
                require(attempt["submission"] == key, "assignment already submitted differently", "DUPLICATE_CONFLICT")
                return {"code": "SUBMITTED", "duplicate": True}
            require(self.s["nodes"][node_id]["status"] == "RUNNING", "assignment is not running", "STALE_RESULT")
            n = self.node(node_id)
            self.review(submission, n["criteria"])
            after = source_snapshot(self.root, self.bundle["inputs"])
            def attributable_to_other(path):
                for other in self.bundle["nodes"]:
                    if other["id"] == node_id or not covered(path, other["write_scope"]):
                        continue
                    other_state = self.s["nodes"][other["id"]]
                    if other_state["status"] in {"RUNNING", "SUBMITTED", "VERIFYING"}:
                        return True
                    for finished in other_state["attempts"]:
                        snap = finished.get("verified_snapshot", {})
                        if finished.get("started", 0) >= attempt["started"] and snap.get(path) == after.get(path) and path in snap:
                            return True
                return False
            unauthorized = [p for p in changed(attempt["scope_snapshot"], after) if not covered(p, n["write_scope"])
                            and not attributable_to_other(p)]
            require(not unauthorized, f"out of scope changes: {unauthorized}", "SCOPE_VIOLATION")
            require(all(within(self.root, p).exists() for p in n["outputs"]), "required outputs missing", "MISSING_ARTIFACT")
            attempt.update(submission=key, submitted_snapshot=source_snapshot(self.root, n["inputs"]), status="SUBMITTED")
            self.s["nodes"][node_id]["status"] = "SUBMITTED"
            self.save("submitted", {"node": node_id, "submission": key})
            return {"code": "SUBMITTED", "submission": key}

    @staticmethod
    def review(value, criteria):
        require(nonempty(value.get("summary")), "result summary required")
        require(all(nonempty(value.get("criteria_review", {}).get(c)) for c in criteria), "intent review must explain every criterion")

    def queue(self, gate_ids):
        return [{"gate": g, "negative": negative} for g in gate_ids for negative in (True, False)]

    def gates(self, node_id, attempt, gate_ids, scopes):
        if attempt["queue"] is None:
            attempt["queue"] = self.queue(gate_ids)
        if attempt.get("launch_pending") and not attempt.get("process"):
            handle = runner.recover_handle(self.root, attempt["launch_pending"])
            if handle:
                attempt.update(process=handle, launch_pending=False)
                self.save("gate_reconnected", {"node": node_id, "process": handle})
        if attempt.get("process"):
            receipt = runner.observe(self.root, attempt["process"])
            if receipt["status"] == "RUNNING":
                return False
            if receipt["status"] == "LOST":
                self.question("process_unknown", "Verification supervisor exited without a trustworthy result; do not duplicate it.", node_id, receipt)
                return False
            require(receipt["binding"] == self.binding(node_id, attempt), "receipt binding mismatch", "EVIDENCE_INVALID")
            key = self.store.object(receipt)
            attempt["receipts"].append(key)
            attempt["process"] = None
            if receipt["status"] != "PASS":
                attempt["failure"] = {"kind": "verification_failed", "receipt": key}
                attempt["status"] = "FAILED"
                self.save("gate_failed", {"node": node_id, "receipt": key})
                return False
            attempt["queue"].pop(0)
            self.save("gate_passed", {"node": node_id, "receipt": key})
        if attempt["queue"]:
            task = attempt["queue"][0]
            gate = next(g for g in self.bundle["gates"] if g["id"] == task["gate"])
            # STARTING intent survives a parent crash between launch and handle receipt.
            if attempt.get("launch_pending"):
                self.question("process_unknown", "Gate launch outcome unknown; inspect process receipts before retry.", node_id)
                return False
            attempt["launch_pending"] = uid()
            self.save("gate_launch_intent", {"node": node_id, **task})
            handle = runner.start(self.root, gate, scopes, self.binding(node_id, attempt), task["negative"], attempt["launch_pending"])
            attempt["process"] = handle
            attempt["launch_pending"] = False
            self.save("gate_started", {"node": node_id, "process": handle})
            return False
        return True

    def fail(self, node_id, attempt):
        state = self.s["nodes"][node_id]
        state["status"] = "FAILED"
        if state["repairs"] >= self.bundle["policy"]["recovery_attempts"]:
            self.question("recovery_exhausted", "Two automatic repairs failed. Decide whether to change the baseline or authorize another repair.", node_id,
                          {"attempts": [a["id"] for a in state["attempts"]], "failure": attempt.get("failure")})
        else:
            # The same AI diagnoses the receipt, reproduces, repairs and resubmits.
            state["repairs"] += 1
            state["status"] = "PENDING"
            self.save("repair_scheduled", {"node": node_id, "repair": state["repairs"]})

    def blocked_nodes(self):
        blocked = set()
        for q in self.s["questions"].values():
            if q["status"] == "OPEN":
                if q.get("detail", {}).get("nodes"):
                    blocked.update(q["detail"]["nodes"])
                    continue
                if q["node_id"] is None or q["node_id"] == "integration":
                    return set(self.s["nodes"])
                blocked.add(q["node_id"])
        return self.downstream(blocked)

    def downstream(self, nodes):
        nodes = set(nodes)
        while True:
            expanded = nodes | {n["id"] for n in self.bundle["nodes"] if set(n["depends_on"]) & nodes}
            if expanded == nodes:
                return nodes
            nodes = expanded

    def conflict(self, node, active):
        def overlap(left, right):
            return any(covered(p, [q]) or covered(q, [p]) for p in left for q in right)
        for other in active:
            if node["executor"] == other["executor"] == "current":
                return True
            if set(node.get("locks", [])) & set(other.get("locks", [])):
                return True
            if overlap(node["write_scope"], other["inputs"] + other["write_scope"]):
                return True
            if overlap(other["write_scope"], node["inputs"] + node["write_scope"]):
                return True
        return False

    def advance(self):
        with self.store.writer():
            self.load()
            if self.s["status"] in {"COMPLETED", "CANCELLED"}:
                if self.s["status"] == "COMPLETED":
                    require(source_snapshot(self.root, self.bundle["inputs"]) == self.s["integration"]["snapshot"],
                            "completed report belongs to an older source snapshot", "STALE_RESULT")
                    from .contracts import read_json
                    require(digest(read_json(within(self.root, self.s["report"]))) == self.s["report_digest"],
                            "completed report changed", "EVIDENCE_INVALID")
                    for state in self.s["nodes"].values():
                        self.check_receipts(state["attempts"][-1])
                    self.check_receipts(self.s["integration"])
                return {"code": self.s["status"], "report": self.s.get("report")}
            require(self.s["approval"], "explicit bundle approval required", "WAITING_USER")
            self.s["status"] = "RUNNING"
            if any(n["executor"] == "orca" for n in self.bundle["nodes"]):
                from .orca import reconcile
                reconcile(self)
            blocked = self.blocked_nodes()
            for node_id, state in self.s["nodes"].items():
                if node_id in blocked or not state["attempts"]:
                    continue
                a, n = state["attempts"][-1], self.node(node_id)
                if a["status"] == "FAILED" and state["status"] != "PENDING":
                    self.fail(node_id, a)
                if state["status"] in {"SUBMITTED", "VERIFYING"} and a["settled"]:
                    # Defer validation while another writer can alter this gate's source inputs.
                    other_writers = [self.node(k) for k, v in self.s["nodes"].items() if k != node_id and v["status"] == "RUNNING"]
                    if self.conflict(n, other_writers):
                        continue
                    if source_snapshot(self.root, n["inputs"]) != a["submitted_snapshot"]:
                        a.update(status="FAILED", failure={"kind": "source_changed_after_submission"})
                        self.fail(node_id, a)
                        continue
                    state["status"] = "VERIFYING"
                    if self.gates(node_id, a, n["gates"], n["inputs"]):
                        state["status"] = a["status"] = "SUCCEEDED"
                        a["verified_snapshot"] = source_snapshot(self.root, n["inputs"])
                        a["verified_bundle"] = self.s["bundle"]
                        self.save("node_succeeded", {"node": node_id})
                    elif a["status"] == "FAILED":
                        self.fail(node_id, a)
            blocked = self.blocked_nodes()
            active = [self.node(k) for k, v in self.s["nodes"].items() if v["status"] in {"RUNNING", "SUBMITTED", "VERIFYING"}]
            for n in sorted(self.bundle["nodes"], key=lambda n: n["id"]):
                state = self.s["nodes"][n["id"]]
                if n["id"] in blocked or state["status"] != "PENDING" or len(active) >= self.bundle["policy"]["concurrency"]:
                    continue
                if not all(self.s["nodes"][d]["status"] == "SUCCEEDED" for d in n["depends_on"]) or self.conflict(n, active):
                    continue
                for dep in n["depends_on"]:
                    da = self.current_attempt(dep)
                    if source_snapshot(self.root, self.node(dep)["inputs"]) != da["verified_snapshot"]:
                        self.invalidate({dep}, "dependency source changed")
                        break
                else:
                    a = self.new_attempt(n["id"])
                    if n["executor"] == "orca":
                        from .orca import launch
                        launch(self, n, a)
                    active.append(n)
            for n in active:
                if n["executor"] == "current" and self.s["nodes"][n["id"]]["status"] == "RUNNING" and n["id"] not in self.blocked_nodes():
                    a = self.current_attempt(n["id"])
                    return self.action(n["id"], a, "repair" if a.get("failure") else "implement")
            if all(v["status"] == "SUCCEEDED" for v in self.s["nodes"].values()) and not self.blocked_nodes():
                return self.integrate()
            questions = [q for q in self.s["questions"].values() if q["status"] == "OPEN"]
            judgment = next((q for q in questions if q["kind"] == "worker_question"), None)
            if judgment:
                return {"code": "ACTION", "kind": "worker_question", "question": judgment, "next": "submit judgment reply or request_user"}
            if questions:
                self.s["status"] = "WAITING_USER"
                self.save("waiting_user")
                return {"code": "RECOVERY_REQUIRED" if any("unknown" in q["kind"] for q in questions) else "WAITING_USER", "questions": questions}
            self.save("progress")
            return {"code": "WAITING_PROCESS", "next": "advance", "nodes": {k: v["status"] for k, v in self.s["nodes"].items()}}

    def integrate(self):
        for node_id, state in self.s["nodes"].items():
            self.check_receipts(state["attempts"][-1])
            if source_snapshot(self.root, self.node(node_id)["inputs"]) != state["attempts"][-1]["verified_snapshot"]:
                self.invalidate({node_id}, "source changed after node verification")
                return {"code": "WAITING_PROCESS", "next": "advance", "reason": "node evidence invalidated"}
        snapshot = source_snapshot(self.root, self.bundle["inputs"])
        a = self.s["integration"]
        if a and a["snapshot"] != snapshot:
            self.s["history"].append({"integration_invalidated": a, "reason": "source changed"})
            a = self.s["integration"] = None
        if a is None:
            a = {"id": uid(), "action_key": uid(), "snapshot": snapshot, "queue": None, "process": None, "receipts": [], "status": "VERIFYING"}
            self.s["integration"] = a
            self.save("integration_started")
        if a["status"] == "FAILED":
            return {"code": "ACTION", "kind": "diagnose_integration", "failure": a.get("failure"), "next": "feedback"}
        if not a.get("verified"):
            if not self.gates("integration", a, self.bundle["integration_gates"], self.bundle["inputs"]):
                return {"code": "WAITING_PROCESS", "next": "advance"}
            a["verified"] = True
            self.save("integration_verified")
        if not a.get("review"):
            return {"code": "ACTION", "kind": "integration_review", "action_key": a["action_key"], "criteria": self.bundle["criteria"], "receipts": a["receipts"]}
        return self.finish()

    def check_receipts(self, attempt):
        for key in attempt["receipts"]:
            receipt = self.store.load(key)
            observed = runner.observe(self.root, {"id": receipt["id"], "pid": receipt["pid"], "request_digest": receipt["request_digest"]})
            require(observed == receipt and receipt["status"] == "PASS", "completion evidence changed", "EVIDENCE_INVALID")

    def invalidate(self, nodes, reason):
        affected = self.downstream(nodes)
        for node_id in affected:
            state = self.s["nodes"][node_id]
            attempt = state["attempts"][-1] if state["attempts"] else None
            busy = state["status"] == "RUNNING" or (state["status"] == "SUBMITTED" and not attempt["settled"])
            if state["status"] == "VERIFYING" and attempt.get("process"):
                observed = runner.observe(self.root, attempt["process"])
                busy = observed["status"] in {"RUNNING", "LOST"}
            require(not busy, "affected writer/process must settle before invalidation", "WAITING_PROCESS")
            if state["attempts"]:
                state["attempts"][-1]["invalidation"] = reason
            state["status"] = "PENDING"
        if self.s["integration"]:
            self.s["history"].append({"integration_invalidated": self.s["integration"], "reason": reason})
        self.s["integration"] = None
        self.save("invalidated", {"affected": sorted(affected), "reason": reason})
        return sorted(affected)

    def feedback(self, kind, nodes, reason, replacement=None):
        require(nonempty(reason), "feedback reason required")
        with self.store.writer():
            self.load(check_definitions=False)
            require(self.s["status"] != "CANCELLED", "cancelled run cannot be resumed by feedback", "STALE_RESULT")
            if self.s["status"] == "COMPLETED":
                self.s["history"].append({"completed_report": self.s["report"], "feedback": reason})
            require(set(nodes) <= set(self.s["nodes"]), "unknown impacted node")
            if kind in {"baseline", "ambiguous"}:
                detail = {"nodes": nodes}
                if replacement:
                    validate(replacement)
                    require(replacement["feature"] == self.bundle["feature"], "cannot change feature identity")
                    # Derive direct impact instead of trusting a caller's reduced affected list.
                    old_c = {c["id"]: c for c in self.bundle["criteria"]}
                    new_c = {c["id"]: c for c in replacement["criteria"]}
                    changed_c = {key for key in old_c.keys() | new_c.keys() if old_c.get(key) != new_c.get(key)}
                    old_g = {g["id"]: g for g in self.bundle["gates"]}
                    new_g = {g["id"]: g for g in replacement["gates"]}
                    changed_g = {key for key in old_g.keys() | new_g.keys() if old_g.get(key) != new_g.get(key)}
                    new_n = {n["id"]: n for n in replacement["nodes"]}
                    impact = set(nodes) | {n["id"] for n in self.bundle["nodes"] if set(n["criteria"]) & changed_c or set(n["gates"]) & changed_g or new_n.get(n["id"]) != n}
                    if any(self.bundle.get(k) != replacement.get(k) for k in ("goal", "before", "after", "design", "inputs", "policy")):
                        impact = set(self.s["nodes"])
                    detail["nodes"] = sorted(self.downstream(impact))
                    detail["replacement"] = self.store.object(replacement)
                q = self.question(kind, reason, nodes[0] if len(nodes) == 1 else None, detail)
                return {"code": "WAITING_USER", "question": q}
            require(kind in {"implementation", "verification", "plan"}, "unknown feedback kind")
            require(nodes, "feedback must name affected nodes")
            affected = self.downstream(nodes)
            # Check busy ownership before committing any revision change.
            require(not any(self.s["nodes"][n]["status"] in {"RUNNING", "SUBMITTED", "VERIFYING"} for n in affected),
                    "affected work must settle first", "WAITING_PROCESS")
            if replacement:
                validate(replacement)
                old, new = copy.deepcopy(self.bundle), copy.deepcopy(replacement)
                for value in (old, new):
                    value.pop("revision", None)
                    if kind == "plan":
                        value.pop("nodes", None)
                    elif kind == "verification":
                        value.pop("gates", None)
                require(old == new, "change requires baseline approval", "BASELINE_CHANGE_REQUIRED")
                if kind == "plan":
                    allowed_scopes = [p for n in self.bundle["nodes"] for p in n["write_scope"]]
                    for n in replacement["nodes"]:
                        prior = next((v for v in self.bundle["nodes"] if v["id"] == n["id"]), None)
                        require(all(covered(p, allowed_scopes) for p in n["write_scope"]), "plan expands scope", "BASELINE_CHANGE_REQUIRED")
                        if prior is not None and n != prior:
                            affected.add(n["id"])
                if kind == "verification":
                    old_gates = {g["id"]: g for g in self.bundle["gates"]}
                    require(set(old_gates) == {g["id"] for g in replacement["gates"]}, "gate removal requires baseline approval", "BASELINE_CHANGE_REQUIRED")
                    changed_gates = set()
                    for g in replacement["gates"]:
                        prior = old_gates[g["id"]]
                        require(g["criteria"] == prior["criteria"] and g["kind"] == prior["kind"] and g["min_tests"] >= prior["min_tests"],
                                "verification change weakens approved coverage", "BASELINE_CHANGE_REQUIRED")
                        if g != prior:
                            changed_gates.add(g["id"])
                    affected |= {n["id"] for n in self.bundle["nodes"] if set(n["gates"]) & changed_gates}
                # Invalidate under the old graph before adding/removing nodes.
                self.invalidate(affected, reason)
                self.replace_bundle(replacement, reason, approval=None)
                affected &= set(self.s["nodes"])
            affected = self.invalidate(affected, reason)
            if kind in {"implementation", "verification"}:
                for node_id in nodes:
                    state = self.s["nodes"][node_id]
                    if state["repairs"] >= 2:
                        self.question("recovery_exhausted", "Two repairs already used; authorize further repair or change the baseline.", node_id)
                    else:
                        state["repairs"] += 1
            for q in self.s["questions"].values():
                if q["kind"] == "integration_failed" and q["status"] == "OPEN":
                    q["status"] = "RESOLVED"
            self.s["status"] = "RUNNING"
            self.save("feedback", {"kind": kind, "affected": affected, "reason": reason})
            return {"code": "READY", "affected": affected}

    def replace_bundle(self, replacement, reason, approval):
        old_nodes = {n["id"]: n for n in self.bundle["nodes"]}
        old_states = copy.deepcopy(self.s["nodes"])
        key = self.store.object(replacement)
        path = f"docs/execution/{replacement['feature']}/revisions/{replacement['revision']}-{key}.json"
        atomic_write_json(within(self.root, path), replacement)
        self.s["history"].append({"bundle": self.s["bundle"], "reason": reason, "approval": self.s["approval"]})
        self.s.update(bundle=key, revision_path=path)
        self.bundle = replacement
        self.s["nodes"] = {
            n["id"]: old_states.get(n["id"], {"status": "PENDING", "attempts": [],
                "repairs": max((v["repairs"] for key, v in old_states.items() if set(old_nodes[key]["criteria"]) & set(n["criteria"])), default=0)})
            for n in replacement["nodes"]}
        removed = {key: value for key, value in old_states.items() if key not in self.s["nodes"]}
        if removed:
            self.s["history"].append({"removed_nodes": removed})
        for node_id, state in self.s["nodes"].items():
            if node_id not in old_states and state["repairs"] >= 2:
                self.question("recovery_exhausted", "Replanning cannot reset exhausted repair history.", node_id)
        if approval:
            self.s.update(approval=self.store.object(approval), approved_digest=key)

    def answer(self, question_id, target, text, source, decision):
        require(nonempty(text) and nonempty(source), "user answer/source required")
        with self.store.writer():
            self.load(check_definitions=False)
            q = self.s["questions"].get(question_id)
            require(q and q["bundle"] == target, "stale question", "STALE_ANSWER")
            answer = {"text": text, "source": source, "decision": decision}
            if q["status"] == "RESOLVED":
                require(q["answer"] == answer, "duplicate answer conflicts", "STALE_ANSWER")
                return {"code": "CANCELLED" if self.s["status"] == "CANCELLED" else "READY", "duplicate": True}
            require(target == self.s["bundle"], "question belongs to older revision", "STALE_ANSWER")
            if self.s["status"] == "CANCELLED":
                require(q["kind"] == "cancel_resources" and decision == "confirmed_stopped",
                        "cancelled execution only accepts resource stop confirmation", "STALE_ANSWER")
                self.s["cancel"]["remaining"].pop(q["detail"]["resource"], None)
                q.update(status="RESOLVED", answer=answer)
                self.save("cancel_resource_confirmed", {"question": question_id, "answer": answer})
                return {"code": "CANCELLED", "remaining": self.s["cancel"]["remaining"]}
            if q["kind"] == "baseline":
                require(decision == "approve_revision" and q["detail"].get("replacement"), "replacement approval required")
                replacement = self.store.load(q["detail"]["replacement"])
                affected = q["detail"]["nodes"] or list(self.s["nodes"])
                self.invalidate(affected, q["reason"])
                self.replace_bundle(replacement, q["reason"], {"actor": "user", "digest": digest(replacement), "quote": text, "source": source})
            elif q["kind"] == "recovery_exhausted":
                require(decision == "one_more_repair", "explicit extra repair decision required")
                self.s["nodes"][q["node_id"]]["status"] = "PENDING"
            elif "unknown" in q["kind"]:
                require(decision == "confirmed_stopped", "unknown execution requires proof of stopped ownership")
                require(nonempty(q.get("detail", {}).get("stop_evidence")) or nonempty(text), "stop evidence required")
                if q["node_id"] in self.s["nodes"]:
                    a = self.current_attempt(q["node_id"])
                    a.update(status="FAILED", settled=True, process=None, launch_pending=False,
                             failure={"kind": "user_confirmed_stopped", "evidence": text})
                    self.s["nodes"][q["node_id"]]["status"] = "FAILED"
            else:
                require(decision == "continue", "explicit continuation required")
                if q["kind"] == "worker_question":
                    from .orca import rpc
                    rpc(self, "answer-" + question_id, ["reply", "--id", q["detail"]["orca_message"], "--body", text])
            q.update(status="RESOLVED", answer=answer)
            self.s["status"] = "RUNNING"
            self.save("answered", {"question": question_id, "answer": answer})
            return {"code": "READY"}

    def finish(self):
        self.check_receipts(self.s["integration"])
        self.s["status"] = "REPORTING"
        report = {"schema_version": 1, "run_id": self.s["run_id"], "bundle": self.s["bundle"],
                  "approval": self.s["approval"], "implementation": "VERIFIED", "recording": "PENDING",
                  "nodes": self.s["nodes"], "integration": self.s["integration"], "history": self.s["history"], "questions": self.s["questions"]}
        path = f"docs/execution/{self.s['feature']}/results/{self.s['run_id']}-{self.s['integration']['id']}.json"
        atomic_write_json(within(self.root, path), redact(report))
        self.s["report"] = path
        from .compound import sync
        try:
            result = sync(self, report)
        except (OSError, ExecutionError) as exc:
            result = {"status": "PENDING", "reason": str(exc), "next": "repair recording environment and advance"}
        report["recording"] = result["status"]
        atomic_write_json(within(self.root, path), redact(report))
        self.s["report_digest"] = digest(redact(report))
        if result["status"] == "PENDING" and self.bundle.get("compound", {}).get("required"):
            self.save("recording_pending", result)
            return {"code": "ACTION", "kind": "compound_record", **result}
        self.s["status"] = "COMPLETED"
        self.save("completed", {"report": path, "recording": result})
        return {"code": "COMPLETED", "report": path, "recording": result}

    def cancel(self, reason):
        with self.store.writer():
            self.load()
            if self.s["status"] == "CANCELLED":
                return {"code": "CANCELLED", "remaining": self.s["cancel"]["remaining"], "duplicate": True}
            self.s["status"] = "CANCELLED"
            remaining = {k: copy.deepcopy(v) for k, v in self.s["nodes"].items() if v["status"] in {"RUNNING", "SUBMITTED", "VERIFYING"}}
            integration = self.s.get("integration")
            if integration and (integration.get("process") or integration.get("launch_pending")):
                remaining["integration"] = copy.deepcopy(integration)
            self.s["cancel"] = {"reason": reason, "time": time.time(), "remaining": remaining}
            for resource in remaining:
                question_id = uid()
                self.s["questions"][question_id] = {"id": question_id, "kind": "cancel_resources",
                    "reason": "Confirm owned execution has stopped, with observed stop evidence before releasing ownership.",
                    "node_id": resource if resource in self.s["nodes"] else None, "bundle": self.s["bundle"],
                    "status": "OPEN", "detail": {"resource": resource}, "created": time.time()}
            self.save("cancelled")
            return {"code": "CANCELLED", "remaining": self.s["cancel"]["remaining"], "note": "No new work. Live resources remain recorded; stop only proven owned processes."}
