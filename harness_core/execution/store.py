"""Fsynced event commits with disposable snapshots, a single local writer."""
from __future__ import annotations

import copy
import hashlib
import os
import time
from contextlib import contextmanager
from pathlib import Path

from .contracts import ExecutionError, canonical, digest, read_json, require, within
from ..state.storage import atomic_write_json, exclusive_lock, StateBusyError


class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.directory = within(self.root, ".moondex")
        self.events = within(self.root, ".moondex/events.jsonl")
        self.snapshot = within(self.root, ".moondex/STATE.json")
        self.state = None
        self.sequence = 0
        self.chain = "0" * 64

    @contextmanager
    def writer(self):
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            with exclusive_lock(within(self.root, ".moondex/writer.lock")):
                self.recover()
                yield self
        except StateBusyError as exc:
            raise ExecutionError("STATE_BUSY", str(exc)) from exc

    def recover(self):
        self.sequence, self.chain, self.state = 0, "0" * 64, None
        if not self.events.exists():
            require(not self.snapshot.exists(), "snapshot without event history", "STATE_INVALID")
            return
        data = self.events.read_bytes()
        end = data.rfind(b"\n") + 1
        if end != len(data):
            # Only a torn final record is repairable. Preserve the original bytes.
            archive = self.directory / ("torn-" + hashlib.sha256(data).hexdigest() + ".bin")
            if not archive.exists():
                with archive.open("xb") as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
            with self.events.open("r+b") as stream:
                stream.truncate(end)
                stream.flush()
                os.fsync(stream.fileno())
        import json
        for raw in data[:end].splitlines():
            try:
                event = json.loads(raw)
                proof = event.pop("hash")
                require(digest(event) == proof and event["previous"] == self.chain and event["sequence"] == self.sequence + 1,
                        "broken event chain", "STATE_INVALID")
                self.state = event["state"]
                self.sequence, self.chain = event["sequence"], proof
            except (ValueError, KeyError, TypeError) as exc:
                raise ExecutionError("STATE_INVALID", "corrupt committed event") from exc
        if self.state is not None:
            atomic_write_json(self.snapshot, self.envelope())

    def envelope(self):
        return {"schema_version": 1, "sequence": self.sequence, "event_hash": self.chain,
                "state_hash": digest(self.state), "state": self.state}

    def commit(self, kind, state, detail=None):
        event = {"sequence": self.sequence + 1, "previous": self.chain, "kind": kind,
                 "time": time.time(), "detail": detail or {}, "state": copy.deepcopy(state)}
        proof = digest(event)
        event["hash"] = proof
        with self.events.open("ab") as stream:
            stream.write(canonical(event) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        self.sequence += 1
        self.chain, self.state = proof, copy.deepcopy(state)
        atomic_write_json(self.snapshot, self.envelope())

    def object(self, value):
        key = digest(value)
        path = within(self.root, f".moondex/objects/{key}.json")
        if path.exists():
            require(read_json(path) == value, "immutable object changed", "STATE_INVALID")
        else:
            atomic_write_json(path, value)
        return key

    def load(self, key):
        require(isinstance(key, str) and len(key) == 64 and all(c in "0123456789abcdef" for c in key), "invalid object key", "STATE_INVALID")
        value = read_json(within(self.root, f".moondex/objects/{key}.json"))
        require(digest(value) == key, "immutable object digest mismatch", "BASELINE_CHANGED")
        return value

    def status(self):
        if not self.snapshot.exists():
            return {"code": "NOT_STARTED"}
        value = read_json(self.snapshot)
        require(digest(value.get("state")) == value.get("state_hash"), "snapshot checksum mismatch; resume required", "RECOVERY_REQUIRED")
        return value["state"]


def source_snapshot(root, scopes):
    """Content, mode and absence bind inputs, including untracked source files."""
    result = {}
    for scope in scopes:
        p = within(root, scope)
        paths = sorted(p.rglob("*")) if p.is_dir() else [p]
        if not p.exists():
            result[scope] = None
        for path in paths:
            rel = path.relative_to(root).as_posix()
            if any(part in {"__pycache__", ".pytest_cache", ".git", ".moondex"} for part in path.parts):
                continue
            within(root, rel)
            if path.is_file():
                result[rel] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "mode": path.stat().st_mode & 0o777}
    return result


def changed(before, after):
    return {p for p in before.keys() | after.keys() if before.get(p) != after.get(p)}
