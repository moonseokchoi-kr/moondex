"""Rules-aware, opt-in publication of AI-authored records; raw is never writable."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .contracts import digest, require, within
from ..state.storage import atomic_write_json, exclusive_lock


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_context(config):
    root = Path(config["root"]).expanduser().resolve()
    refs = [config[k] for k in ("rules", "template", "index", "log")]
    if config.get("hub"):
        refs.append(config["hub"])
    return {p: within(root, p).read_text() for p in refs}


def accept(engine, submission):
    config = engine.bundle.get("compound", {})
    require(config.get("enabled"), "Compound is not configured")
    root = Path(config["root"]).expanduser().resolve()
    context = read_context(config)
    require(submission.get("context_digest") == digest(context), "Compound rules/index changed; reread", "SYNC_CONFLICT")
    files = submission.get("files", [])
    allowed = {config[k] for k in ("criteria_page", "result_page", "index", "log")}
    if config.get("hub"):
        allowed.add(config["hub"])
    require(len(files) == len(allowed) and {f["path"] for f in files} == allowed, "record all configured pages/index/log/hub once")
    template = context[config["template"]]
    keys = re.findall(r"^([a-z_]+):", template, flags=re.M)
    for item in files:
        rel = item["path"]
        require(rel.startswith("wiki/") and not rel.startswith("raw/"), "Compound writes are wiki-only", "SCOPE_VIOLATION")
        path = within(root, rel)
        before = path.read_bytes() if path.exists() else b""
        require(item.get("before_sha256") == sha(before), "Compound user edit detected", "SYNC_CONFLICT")
        text = item.get("text")
        require(isinstance(text, str), "record text required")
        if rel in {config["criteria_page"], config["result_page"]}:
            require(text.startswith("---\n") and all(re.search(rf"^{k}:", text, re.M) for k in keys), "page template frontmatter required")
            sections = re.findall(r"^## .+$", template.split('<!--', 1)[0], re.M)
            require(all(heading in text for heading in sections), "page template sections required")
        if rel == config["criteria_page"] and before:
            require(text.startswith(before.decode()), "criteria history may only be appended", "BASELINE_CHANGED")
    key = engine.store.object(submission)
    engine.s["compound_draft"] = key
    engine.save("compound_draft", {"object": key})
    return {"code": "SUBMITTED"}


def sync(engine, report):
    config = engine.bundle.get("compound", {})
    if not config.get("enabled"):
        return {"status": "SKIPPED"}
    context = read_context(config)
    draft_key = engine.s.get("compound_draft")
    if not draft_key:
        return {"status": "PENDING", "context": context, "context_digest": digest(context),
                "config": config, "report": engine.s["report"], "next": "submit kind=compound with files/path/before_sha256/text"}
    draft = engine.store.load(draft_key)
    root = Path(config["root"]).expanduser().resolve()
    applied = engine.s.setdefault("compound_applied", {})
    # Rules/template must remain unchanged; index/log legitimately change during this batch.
    initial = draft.get("rules_digest")
    rules_digest = digest({k: context[config[k]] for k in ("rules", "template")})
    if initial != rules_digest:
        return {"status": "PENDING", "reason": "rules/template changed or not attested", "context_digest": digest(context)}
    with exclusive_lock(within(root, ".moondex-record.lock")):
        for item in draft["files"]:
            path = within(root, item["path"])
            current = path.read_bytes() if path.exists() else b""
            desired = item["text"].encode()
            if current == desired:
                applied[item["path"]] = sha(desired)
                engine.save("compound_reconciled", {"path": item["path"]})
                continue
            if sha(current) != item["before_sha256"]:
                return {"status": "PENDING", "reason": "user edit preserved", "path": item["path"]}
            # Journal before each write, never roll back a user's concurrent changes.
            engine.save("compound_write_intent", {"path": item["path"], "before": sha(current), "after": sha(desired)})
            path.parent.mkdir(parents=True, exist_ok=True)
            import os, tempfile
            fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".moondex-")
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(desired)
                    stream.flush()
                    os.fsync(stream.fileno())
                latest = path.read_bytes() if path.exists() else b""
                if latest != current:
                    return {"status": "PENDING", "reason": "concurrent user edit preserved", "path": item["path"]}
                os.replace(tmp, path)
                dfd = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(dfd)
                finally:
                    os.close(dfd)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
            applied[item["path"]] = sha(desired)
            engine.save("compound_written", {"path": item["path"]})
    return {"status": "RECORDED", "files": applied}
