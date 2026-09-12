import copy
import hashlib
import json
from pathlib import Path

import pytest

from harness_core.execution.contracts import ExecutionError, digest
from harness_core.execution.compound import read_context
from harness_core.execution.engine import Engine
from harness_core.execution.store import Store
from test_execution import bundle, approved, implement, until, complete


def two_nodes():
    b = bundle()
    c2 = copy.deepcopy(b["criteria"][0]); c2["id"] = "C2"
    b["criteria"].append(c2)
    b["inputs"] = ["left", "right"]
    first = b["nodes"][0]
    first.update(inputs=["left"], write_scope=["left"], outputs=["left/value.txt"])
    second = copy.deepcopy(first)
    second.update(id="N2", inputs=["right"], write_scope=["right"], outputs=["right/value.txt"], criteria=["C2"], gates=["other"])
    b["nodes"].append(second)
    for mode in (b["gates"][0], b["gates"][0]["oracle"]):
        mode["argv"][2] = mode["argv"][2].replace("src/", "left/")
    other = copy.deepcopy(b["gates"][0]); other.update(id="other", criteria=["C2"])
    for mode in (other, other["oracle"]):
        mode["argv"][2] = mode["argv"][2].replace("left/", "right/").replace("C1", "C2")
    b["gates"].append(other)
    b["integration_gates"].append("other")
    return b


def populate(e):
    while True:
        a = until(e, lambda r: r["code"] == "ACTION")
        if a["kind"] == "integration_review":
            e.submit({"kind": "integration_review", "action_key": a["action_key"], "summary": "Both outputs are 42",
                      "criteria_review": {"C1": "left is 42", "C2": "right is 42"}})
            return e.advance()
        n = a["node"]
        p = e.root / n["outputs"][0]; p.parent.mkdir(exist_ok=True); p.write_text("42")
        e.submit({**{k: a[k] for k in ("node_id", "attempt_id", "bundle", "action_key")}, "summary": "Implemented answer",
                  "criteria_review": {c: "Observed 42" for c in n["criteria"]}})


def test_feedback_preserves_unrelated_evidence_and_old_report(tmp_path):
    e = approved(tmp_path, two_nodes())
    first = populate(e)
    old_bytes = (tmp_path / first["report"]).read_bytes()
    before = e.store.status()["nodes"]["N2"]["attempts"][-1]
    result = e.feedback("implementation", ["N1"], "Left has an edge-case defect")
    assert result["affected"] == ["N1"]
    assert populate(e)["code"] == "COMPLETED"
    assert e.store.status()["nodes"]["N2"]["attempts"][-1] == before
    assert (tmp_path / first["report"]).read_bytes() == old_bytes


def test_verification_weakening_requires_user_revision(tmp_path):
    e = approved(tmp_path)
    e.submit(implement(e, e.advance()))
    complete(e)
    new = bundle(); new["revision"] = "v2"
    new["criteria"][0]["expected"] = "any number"
    with pytest.raises(ExecutionError, match="baseline approval"):
        e.feedback("verification", ["N1"], "make the test pass", new)


def test_baseline_change_waits_for_matching_user_answer(tmp_path):
    e = approved(tmp_path)
    e.submit(implement(e, e.advance())); complete(e)
    new = bundle(); new["revision"] = "r2"; new["design"] = ["Also document the saved answer"]
    q = e.feedback("baseline", ["N1"], "new requested design", new)["question"]
    assert e.advance()["code"] == "WAITING_USER"
    with pytest.raises(ExecutionError, match="stale"):
        e.answer(q["id"], "wrong", "yes", "user", "approve_revision")
    e.answer(q["id"], q["bundle"], "Approve r2 design", "user", "approve_revision")
    a = e.advance()
    assert a["bundle"] == digest(new)
    assert list((tmp_path / "docs/execution/example/revisions").glob("r1-*.json"))


def knowledge(tmp_path):
    root = tmp_path / "knowledge"
    (root / "wiki").mkdir(parents=True)
    (root / "raw").mkdir(); (root / "raw/source.md").write_text("User-owned source")
    (root / "CLAUDE.md").write_text("Write wiki only. Raw is read-only. Use the template.")
    (root / "template.md").write_text("---\ntitle: Page\nstatus: active\n---\n# Page\n## Content\n## TODO\n")
    (root / "wiki/index.md").write_text("# Index\n")
    (root / "wiki/log.md").write_text("# Log\n")
    return {"enabled": True, "required": True, "root": str(root), "rules": "CLAUDE.md", "template": "template.md",
            "index": "wiki/index.md", "log": "wiki/log.md", "criteria_page": "wiki/criteria.md", "result_page": "wiki/result.md"}


def draft(config):
    context = read_context(config)
    files = []
    for field in ("criteria_page", "result_page", "index", "log"):
        p = Path(config["root"]) / config[field]
        before = p.read_bytes() if p.exists() else b""
        text = context["template.md"].replace("Page", field) if field.endswith("page") else before.decode() + "[[criteria]] [[result]]\n"
        files.append({"path": config[field], "before_sha256": hashlib.sha256(before).hexdigest(), "text": text})
    return {"kind": "compound", "context_digest": digest(context),
            "rules_digest": digest({k: context[config[k]] for k in ("rules", "template")}), "files": files}


def test_required_compound_recording_and_idempotence(tmp_path):
    config = knowledge(tmp_path)
    b = bundle(); b["compound"] = config
    e = approved(tmp_path / "project", b)
    e.submit(implement(e, e.advance()))
    r = complete(e)
    assert r["kind"] == "compound_record"
    assert e.store.status()["status"] == "REPORTING"
    e.submit(draft(config))
    assert e.advance()["code"] == "COMPLETED"
    root = Path(config["root"])
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    assert e.advance()["code"] == "COMPLETED"
    assert before == {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    assert (root / "raw/source.md").read_text() == "User-owned source"


def test_compound_user_edit_after_draft_is_preserved(tmp_path):
    config = knowledge(tmp_path)
    b = bundle(); b["compound"] = config
    e = approved(tmp_path / "project", b)
    e.submit(implement(e, e.advance())); complete(e)
    e.submit(draft(config))
    p = Path(config["root"]) / config["index"]
    p.write_text("User edit after draft\n")
    r = e.advance()
    assert r["status"] == "PENDING"
    assert p.read_text() == "User edit after draft\n"
    assert e.store.status()["status"] == "REPORTING"


def test_compound_rejects_raw_and_changed_criteria_history(tmp_path):
    config = knowledge(tmp_path)
    b = bundle(); b["compound"] = config
    e = approved(tmp_path / "project", b)
    e.submit(implement(e, e.advance())); complete(e)
    d = draft(config); d["files"][0]["path"] = "raw/source.md"
    with pytest.raises(ExecutionError): e.submit(d)
    assert (Path(config["root"]) / "raw/source.md").read_text() == "User-owned source"
