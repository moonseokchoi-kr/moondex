"""Deterministic, offline review-request disposition and convergence.

This module deliberately knows nothing about a hosting provider, git, or an
LLM.  An adapter supplies one complete local JSON collection and explicit
local evidence; the core validates, records, and classifies that data.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path, PureWindowsPath
import re
import tempfile
from typing import Any, Iterable, Mapping


MAX_ITERATIONS = 15
MAX_ATTEMPTS = 3
MAX_SAFE_INTEGER = 9_007_199_254_740_991
TERMINAL_DECISIONS = frozenset({"SAFE_FIX", "REJECTED", "NON_ACTIONABLE"})


class StrictInputError(ValueError):
    """An input is not the complete, strict local review collection."""


class AuditWriteError(RuntimeError):
    """The append-only audit record could not be safely persisted."""


def _reject_constant(value: str) -> None:
    raise StrictInputError(f"non-standard JSON constant: {value}")


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StrictInputError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_json_loads(raw: str | bytes) -> Any:
    """Load exactly one RFC-8259 JSON value, rejecting permissive defaults."""
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise StrictInputError("input is not UTF-8") from exc
    if not isinstance(raw, str):
        raise StrictInputError("input must be JSON text")
    decoder = json.JSONDecoder(object_pairs_hook=_no_duplicate_keys, parse_constant=_reject_constant)
    # RFC 8259 permits JSON whitespace around a single value.  ``raw_decode``
    # deliberately does not skip it, so locate the first value explicitly.
    start = len(raw) - len(raw.lstrip(" \t\r\n"))
    try:
        value, end = decoder.raw_decode(raw, start)
    except (json.JSONDecodeError, StrictInputError) as exc:
        raise StrictInputError(f"invalid strict JSON: {exc}") from exc
    if raw[end:].strip():
        raise StrictInputError("trailing JSON data")
    return value


def _string(value: Any, field: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str) or (nonempty and not value.strip()):
        raise StrictInputError(f"{field} must be a non-empty string")
    if "\x00" in value:
        raise StrictInputError(f"{field} contains NUL")
    return value


def _safe_int(value: Any, field: str, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise StrictInputError(f"{field} must be an integer JSON number")
    if not math.isfinite(value) or abs(value) > MAX_SAFE_INTEGER or (positive and value <= 0):
        raise StrictInputError(f"{field} is outside the safe integer range")
    return value


def _timestamp(value: Any) -> str:
    text = _string(value, "created_at")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", text):
        raise StrictInputError("created_at must be an RFC 3339 date-time with timezone")
    try:
        datetime.fromisoformat(f"{text[:-1]}+00:00" if text.endswith("Z") else text)
    except ValueError as exc:
        raise StrictInputError("created_at must be RFC 3339") from exc
    return text


def _normal_body(body: str) -> str:
    return body.replace("\r\n", "\n").replace("\r", "\n").strip()


def _body_hash(body: str) -> str:
    return hashlib.sha256(_normal_body(body).encode("utf-8")).hexdigest()


def _relative_path(value: Any) -> str:
    path = _string(value, "path")
    candidate = Path(path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise StrictInputError("path must be repository-relative")
    return path


def normalize_comment(comment: Mapping[str, Any]) -> dict[str, Any]:
    """Validate one provider-neutral request and produce a stable revision."""
    if not isinstance(comment, Mapping):
        raise StrictInputError("comment must be an object")
    if set(comment) - {
        "schema_version", "source", "source_identity", "comment_id", "revision_identity",
        "body_hash", "author", "body", "created_at", "review_state", "path", "line",
    }:
        raise StrictInputError("comment has unsupported fields")
    if _safe_int(comment.get("schema_version"), "schema_version") != 1:
        raise StrictInputError("unsupported comment schema_version")
    source = _string(comment.get("source"), "source")
    if source not in {"conversation", "inline", "review_body"}:
        raise StrictInputError("unsupported source")
    identity = _string(comment.get("source_identity"), "source_identity")
    if any(ch.isspace() for ch in identity):
        raise StrictInputError("source_identity must be a stable token")
    comment_id = comment.get("comment_id")
    if isinstance(comment_id, int) and not isinstance(comment_id, bool):
        comment_id = _safe_int(comment_id, "comment_id", positive=True)
    else:
        comment_id = _string(comment_id, "comment_id")
    revision = _string(comment.get("revision_identity"), "revision_identity")
    body = _string(comment.get("body"), "body", nonempty=False)
    provided_hash = _string(comment.get("body_hash"), "body_hash")
    actual_hash = _body_hash(body)
    if provided_hash != actual_hash:
        raise StrictInputError("body_hash does not match normalized body")
    normalized: dict[str, Any] = {
        "schema_version": 1, "source": source, "source_identity": identity,
        "comment_id": comment_id, "revision_identity": revision, "body_hash": actual_hash,
        "author": _string(comment.get("author"), "author"), "body": body,
        "created_at": _timestamp(comment.get("created_at")),
    }
    if "review_state" in comment:
        normalized["review_state"] = _string(comment["review_state"], "review_state")
    if "path" in comment:
        normalized["path"] = _relative_path(comment["path"])
    if "line" in comment:
        normalized["line"] = _safe_int(comment["line"], "line", positive=True)
    return normalized


def parse_collection(raw: str | bytes) -> dict[str, Any]:
    """Parse a complete local collection snapshot, or fail closed."""
    data = strict_json_loads(raw)
    if not isinstance(data, dict) or set(data) != {"schema_version", "input_identity", "complete", "comments"}:
        raise StrictInputError("collection has an invalid schema")
    if _safe_int(data.get("schema_version"), "schema_version") != 1:
        raise StrictInputError("unsupported collection schema_version")
    if data.get("complete") is not True:
        raise StrictInputError("collection is incomplete")
    identity = _string(data.get("input_identity"), "input_identity")
    comments = data.get("comments")
    if not isinstance(comments, list):
        raise StrictInputError("comments must be an array")
    normalized = [normalize_comment(item) for item in comments]
    identities = [item["source_identity"] for item in normalized]
    if len(identities) != len(set(identities)):
        raise StrictInputError("source_identity must occur once per collection")
    derived_keys = [revision_key(item) for item in normalized]
    if len(derived_keys) != len(set(derived_keys)):
        raise StrictInputError("derived revision key must occur once per collection")
    snapshot_seed = json.dumps(
        {"input_identity": identity, "comments": [{k: c[k] for k in ("source_identity", "revision_identity", "body_hash")} for c in normalized]},
        sort_keys=True, separators=(",", ":"),
    )
    return {
        "schema_version": 1, "input_identity": identity, "complete": True, "comments": normalized,
        "snapshot_id": hashlib.sha256(snapshot_seed.encode("utf-8")).hexdigest(),
    }


def revision_key(comment: Mapping[str, Any]) -> str:
    """Return a collision-free, versioned key over the complete typed identity."""
    comment_id = comment["comment_id"]
    identity = {
        "body_hash": str(comment["body_hash"]),
        "comment_id": {
            "type": "integer" if isinstance(comment_id, int) and not isinstance(comment_id, bool) else "string",
            "value": comment_id,
        },
        "revision_identity": str(comment["revision_identity"]),
        "source_identity": str(comment["source_identity"]),
        "version": 1,
    }
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"rk1:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def _legacy_revision_key(comment: Mapping[str, Any]) -> str:
    return ":".join((str(comment["source_identity"]), str(comment["revision_identity"]), str(comment["body_hash"])))


def _canonicalize_prior_events(
    snapshot: Mapping[str, Any], prior_events: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Map unambiguous legacy current-revision events and reject identity conflicts."""
    comments = list(snapshot.get("comments", []))
    current = {revision_key(comment): comment for comment in comments}
    legacy: dict[str, list[Mapping[str, Any]]] = {}
    for comment in comments:
        legacy.setdefault(_legacy_revision_key(comment), []).append(comment)
    normalized: list[dict[str, Any]] = []
    relevant: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for raw_event in prior_events:
        event = dict(raw_event)
        if event.get("event_type") not in {"disposition", "escalation_resolution"}:
            normalized.append(event)
            continue
        key = event.get("revision_key")
        comment = current.get(key)
        if comment is None and isinstance(key, str) and key in legacy:
            candidates = [
                candidate for candidate in legacy[key]
                if event.get("source_identity") == candidate.get("source_identity")
                and event.get("revision_identity") == candidate.get("revision_identity")
                and event.get("request_id") == str(candidate.get("comment_id"))
            ]
            if len(candidates) != 1:
                raise StrictInputError("legacy audit revision identity is ambiguous")
            comment = candidates[0]
            event["legacy_revision_key"] = key
            event["revision_key"] = revision_key(comment)
        if comment is None:
            normalized.append(event)
            continue
        if (
            event.get("source_identity") != comment.get("source_identity")
            or event.get("revision_identity") != comment.get("revision_identity")
            or ("body_hash" in event and event.get("body_hash") != comment.get("body_hash"))
            or ("comment_id" in event and event.get("comment_id") != comment.get("comment_id"))
            or event.get("request_id") != str(comment.get("comment_id"))
        ):
            raise StrictInputError("audit event identity conflicts with its derived revision key")
        normalized.append(event)
        relevant.setdefault((event["revision_key"], event["event_type"]), []).append(event)
    for (_, event_type), events in relevant.items():
        if event_type == "disposition" and len(events) > 1:
            raise StrictInputError("duplicate disposition identity in audit")
        if event_type == "escalation_resolution":
            digests = {event.get("resolution_digest") for event in events}
            if len(digests) > 1:
                raise StrictInputError("duplicate conflicting resolution")
    return normalized


def _comment_id(value: Any, field: str = "comment_id") -> str | int:
    if isinstance(value, int) and not isinstance(value, bool):
        return _safe_int(value, field, positive=True)
    return _string(value, field)


def normalize_resolution(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate one immutable user decision for an existing escalation."""
    if not isinstance(value, Mapping):
        raise StrictInputError("resolution must be an object")
    allowed = {
        "schema_version", "source_identity", "revision_identity", "body_hash",
        "comment_id", "authority", "decision", "reason", "alternative",
        "evidence", "fix",
    }
    if set(value) - allowed or not {
        "schema_version", "source_identity", "revision_identity", "body_hash",
        "comment_id", "authority", "decision", "reason", "evidence",
    }.issubset(value):
        raise StrictInputError("resolution has an invalid schema")
    if _safe_int(value.get("schema_version"), "resolution schema_version") != 1:
        raise StrictInputError("unsupported resolution schema_version")
    authority = _string(value.get("authority"), "resolution authority")
    if authority != "USER":
        raise StrictInputError("resolution authority must be USER")
    decision = _string(value.get("decision"), "resolution decision")
    if decision not in {"SAFE_FIX", "REJECTED"}:
        raise StrictInputError("resolution decision must be SAFE_FIX or REJECTED")
    reason = _string(value.get("reason"), "resolution reason")
    alternative = value.get("alternative")
    if alternative is not None:
        alternative = _string(alternative, "resolution alternative")
    if decision == "REJECTED" and alternative is None:
        raise StrictInputError("rejected resolution requires an alternative")
    evidence = value.get("evidence")
    if not isinstance(evidence, list) or not evidence or not all(isinstance(item, Mapping) for item in evidence):
        raise StrictInputError("resolution evidence must be a non-empty object array")
    fix = value.get("fix", {})
    if not isinstance(fix, Mapping) or set(fix) - {"repository_root", "changed_files", "validation"}:
        raise StrictInputError("resolution fix has an invalid schema")
    normalized_fix = {
        "repository_root": fix.get("repository_root"),
        "changed_files": list(fix.get("changed_files", [])) if isinstance(fix.get("changed_files", []), list) else None,
        "validation": list(fix.get("validation", [])) if isinstance(fix.get("validation", []), list) else None,
    }
    if normalized_fix["changed_files"] is None or normalized_fix["validation"] is None:
        raise StrictInputError("resolution fix arrays are invalid")
    return {
        "schema_version": 1,
        "source_identity": _string(value.get("source_identity"), "resolution source_identity"),
        "revision_identity": _string(value.get("revision_identity"), "resolution revision_identity"),
        "body_hash": _string(value.get("body_hash"), "resolution body_hash"),
        "comment_id": _comment_id(value.get("comment_id"), "resolution comment_id"),
        "authority": authority,
        "decision": decision,
        "reason": reason,
        "alternative": alternative,
        "evidence": [dict(item) for item in evidence],
        "fix": normalized_fix,
    }


def parse_resolution_collection(raw: str | bytes | None) -> list[dict[str, Any]]:
    if raw is None:
        return []
    data = strict_json_loads(raw)
    if not isinstance(data, Mapping) or set(data) != {"schema_version", "complete", "resolutions"}:
        raise StrictInputError("resolution collection has an invalid schema")
    if _safe_int(data.get("schema_version"), "resolution collection schema_version") != 1:
        raise StrictInputError("unsupported resolution collection schema_version")
    if data.get("complete") is not True or not isinstance(data.get("resolutions"), list):
        raise StrictInputError("resolution collection must be complete")
    result: dict[tuple[str, str, str, str | int], dict[str, Any]] = {}
    for raw_resolution in data["resolutions"]:
        resolution = normalize_resolution(raw_resolution)
        key = (
            resolution["source_identity"], resolution["revision_identity"],
            resolution["body_hash"], resolution["comment_id"],
        )
        prior = result.get(key)
        if prior is not None and prior != resolution:
            raise StrictInputError("duplicate conflicting resolution")
        result[key] = resolution
    return list(result.values())


def _resolution_digest(resolution: Mapping[str, Any]) -> str:
    payload = json.dumps(dict(resolution), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def new_revisions(snapshot: Mapping[str, Any], prior_events: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return revisions not previously terminally dispositioned.

    A body/revision change changes ``revision_key``.  Reopened reviews are
    expected to carry a new revision identity and therefore cannot inherit an
    old terminal outcome.
    """
    prior = _canonicalize_prior_events(snapshot, prior_events)
    settled = {
        event.get("revision_key") for event in prior
        if event.get("decision") in TERMINAL_DECISIONS | {"ESCALATED", "BLOCKED"}
    }
    return [dict(comment) for comment in snapshot["comments"] if revision_key(comment) not in settled]


def classify_disposition(
    comment: Mapping[str, Any],
    evidence: Mapping[str, Any],
    *,
    repository_root: Path | None = None,
) -> dict[str, Any]:
    """Classify only explicit local evidence; prose and LLM suggestions lack authority."""
    if not isinstance(evidence, Mapping):
        raise StrictInputError("local evidence must be an object")
    actionability = evidence.get("actionability", "ACTIONABLE")
    reason = evidence.get("reason")
    if actionability == "NON_ACTIONABLE":
        if not isinstance(reason, str) or not reason.strip():
            raise StrictInputError("non-actionable disposition needs a reason")
        return _event(comment, evidence, "NON_ACTIONABLE", reason)
    if actionability != "ACTIONABLE":
        return _event(comment, evidence, "BLOCKED", "invalid actionability evidence")
    alignment = evidence.get("alignment")
    if not isinstance(alignment, Mapping):
        return _event(comment, evidence, "ESCALATED", "local alignment evidence is missing")
    spec, design = alignment.get("spec"), alignment.get("design")
    ownership, verification = alignment.get("ownership"), alignment.get("verification")
    if evidence.get("llm_only") or evidence.get("design_tradeoff") or evidence.get("missing_authority"):
        return _event(comment, evidence, "ESCALATED", "automatic disposition lacks local decision authority")
    failed = evidence.get("validation_failed") or evidence.get("scope_expanded") or evidence.get("ownership_changed")
    validation = evidence.get("validation")
    if isinstance(validation, list) and any(
        not isinstance(result, Mapping) or result.get("passed") is not True
        for result in validation
    ):
        failed = True
    if failed:
        return _event(comment, evidence, "ESCALATED", "local validation or scope evidence requires a decision")
    if spec == "CONFLICTS" or design == "CONFLICTS" or ownership == "OUT_OF_SCOPE":
        alternative = evidence.get("alternative")
        if not isinstance(reason, str) or not reason.strip() or not isinstance(alternative, str) or not alternative.strip():
            return _event(comment, evidence, "ESCALATED", "rejection requires a reason and alternative")
        return _event(comment, evidence, "REJECTED", reason)
    plan = evidence.get("validation_plan")
    changed_files = evidence.get("changed_files")
    if (
        spec == design == "ALIGNS"
        and ownership == "OWNED"
        and verification == "AVAILABLE"
        and isinstance(plan, list)
        and plan
        and all(isinstance(x, str) and x.strip() for x in plan)
        and _has_completed_safe_fix_evidence(
            changed_files, validation, repository_root, evidence.get("repository_root")
        )
    ):
        return _event(
            comment, evidence, "SAFE_FIX", "aligned local rule, owned scope, changed files, and passing validation",
            repository_root=repository_root,
        )
    return _event(comment, evidence, "ESCALATED", "alignment is unknown, contradictory, or insufficient")


def _has_completed_safe_fix_evidence(
    changed_files: Any,
    validation: Any,
    repository_root: Path | None,
    recorded_root: Any,
) -> bool:
    """Return whether a fix has replayable local file and validation evidence.

    A syntactically plausible path is not proof of a changed file.  The
    caller must supply the trusted repository root and the evidence must name
    that exact canonical root, so the audit can later repeat the same local
    containment and regular-file checks.
    """
    if not isinstance(changed_files, list) or not changed_files:
        return False
    try:
        normalized_paths = [_concrete_changed_file(path) for path in changed_files]
        root = _trusted_repository_root(repository_root, recorded_root)
        for path in normalized_paths:
            candidate = (root / path).resolve(strict=True)
            if not candidate.is_relative_to(root) or not candidate.is_file():
                return False
    except StrictInputError:
        return False
    if len(normalized_paths) != len(set(normalized_paths)):
        return False
    return (
        isinstance(validation, list)
        and bool(validation)
        and all(
            isinstance(result, Mapping)
            and isinstance(result.get("command"), str)
            and bool(result["command"].strip())
            and result.get("passed") is True
            for result in validation
        )
    )


def _trusted_repository_root(repository_root: Path | None, recorded_root: Any) -> Path:
    """Return a canonical, explicit local root or fail closed.

    ``repository_root`` is trusted caller context; the duplicate evidence
    value prevents an audit record from hiding which workspace was checked.
    """
    if repository_root is None or not isinstance(recorded_root, str) or not recorded_root:
        raise StrictInputError("safe fix requires an explicit trusted repository root")
    try:
        root = Path(repository_root).resolve(strict=True)
    except OSError as exc:
        raise StrictInputError("trusted repository root is unavailable") from exc
    if not root.is_dir() or recorded_root != str(root):
        raise StrictInputError("safe fix repository root evidence does not match trusted root")
    return root


def _concrete_changed_file(value: Any) -> str:
    """Validate a changed-file record without consulting the live filesystem.

    Evidence must identify a concrete repository-relative file, not the
    repository root or a directory-shaped selector.  This check deliberately
    stays syntactic: a review audit remains reproducible even after files are
    moved or deleted.
    """
    path = _string(value, "changed file")
    if path != path.strip() or path in {".", ""} or path.endswith(("/", "\\")):
        raise StrictInputError("changed file must name a concrete repository-relative file")
    candidate = Path(path)
    windows_candidate = PureWindowsPath(path)
    raw_parts = path.replace("\\", "/").split("/")
    if (
        candidate.is_absolute()
        or windows_candidate.is_absolute()
        or bool(windows_candidate.drive)
        or any(part in {"", ".", ".."} for part in raw_parts)
    ):
        raise StrictInputError("changed file must name a concrete repository-relative file")
    return path


def _event(
    comment: Mapping[str, Any], evidence: Mapping[str, Any], decision: str, reason: str,
    *, repository_root: Path | None = None,
) -> dict[str, Any]:
    now = datetime.now().astimezone().isoformat()
    return {
        "schema_version": 1, "event_type": "disposition", "source_identity": comment["source_identity"],
        "revision_identity": comment["revision_identity"], "revision_key": revision_key(comment),
        "revision_key_version": 1, "body_hash": comment["body_hash"],
        "comment_id": comment["comment_id"], "request_id": str(comment["comment_id"]), "observed_at": now,
        "actionability": evidence.get("actionability", "ACTIONABLE"), "decision": decision,
        "reason": reason, "alignment": dict(evidence.get("alignment", {})),
        "evidence": list(evidence.get("evidence", [])),
        "fix": {
            "repository_root": str(repository_root.resolve()) if decision == "SAFE_FIX" and repository_root else None,
            "changed_files": list(evidence.get("changed_files", [])),
            "validation": list(evidence.get("validation", [])),
        },
        "alternative": evidence.get("alternative"), "posting": {"status": "NOT_REQUESTED"},
    }


class AuditWriter:
    """Single-writer, fsync + replace append-only JSONL record."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.lock_path = self.path.with_name(f".{self.path.name}.lock")

    def write_events(self, events: Iterable[Mapping[str, Any]]) -> None:
        serialized = [json.dumps(dict(event), sort_keys=True, separators=(",", ":")) for event in events]
        if not serialized:
            return
        token = os.urandom(16).hex()
        fd: int | None = None
        temp_name: str | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise AuditWriteError("concurrent writer or lock loss") from exc
        except OSError as exc:
            raise AuditWriteError(f"audit persistence failed: {exc}") from exc
        try:
            os.write(fd, token.encode("ascii")); os.fsync(fd); os.close(fd)
            old = self.path.read_bytes() if self.path.exists() else b""
            with tempfile.NamedTemporaryFile("wb", dir=self.path.parent, prefix=f".{self.path.name}.", delete=False) as temp:
                temp.write(old)
                if old and not old.endswith(b"\n"):
                    temp.write(b"\n")
                temp.write(("\n".join(serialized) + "\n").encode("utf-8"))
                temp.flush(); os.fsync(temp.fileno())
                temp_name = temp.name
            try:
                if self.lock_path.read_text(encoding="ascii") != token:
                    raise AuditWriteError("lock ownership changed")
                os.replace(temp_name, self.path)
                directory_fd = os.open(self.path.parent, os.O_RDONLY)
                try: os.fsync(directory_fd)
                finally: os.close(directory_fd)
            finally:
                if temp_name and os.path.exists(temp_name): os.unlink(temp_name)
        except AuditWriteError:
            raise
        except OSError as exc:
            raise AuditWriteError(f"audit persistence failed: {exc}") from exc
        finally:
            if fd is not None:
                try: os.close(fd)
                except OSError: pass
            try:
                if self.lock_path.exists() and self.lock_path.read_text(encoding="ascii") == token:
                    self.lock_path.unlink()
            except OSError:
                # A stale lock intentionally fails the next pass closed.
                pass

    def append(self, event: Mapping[str, Any]) -> None:
        self.write_events([event])


def load_audit(path: Path) -> list[dict[str, Any]]:
    if not Path(path).exists(): return []
    try:
        return [strict_json_loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, StrictInputError) as exc:
        raise AuditWriteError("existing audit record is unreadable") from exc


def _resolution_events(
    snapshot: Mapping[str, Any],
    resolutions: Iterable[Mapping[str, Any]],
    prior_events: Iterable[Mapping[str, Any]],
    repository_root: Path | None,
) -> list[dict[str, Any]]:
    comments = {
        (c["source_identity"], c["revision_identity"], c["body_hash"], c["comment_id"]): c
        for c in snapshot["comments"]
    }
    prior = list(prior_events)
    created: list[dict[str, Any]] = []
    for resolution in resolutions:
        identity = (
            resolution["source_identity"], resolution["revision_identity"],
            resolution["body_hash"], resolution["comment_id"],
        )
        comment = comments.get(identity)
        if comment is None:
            raise StrictInputError("resolution identity does not match the current comment revision")
        key = revision_key(comment)
        digest = _resolution_digest(resolution)
        existing = [
            event for event in prior
            if event.get("event_type") == "escalation_resolution" and event.get("revision_key") == key
        ]
        if existing:
            if any(event.get("resolution_digest") != digest for event in existing):
                raise StrictInputError("duplicate conflicting resolution")
            continue
        dispositions = [
            event for event in prior
            if event.get("event_type") == "disposition" and event.get("revision_key") == key
        ]
        if not dispositions or dispositions[-1].get("decision") != "ESCALATED":
            raise StrictInputError("resolution requires a matching open escalation")
        fix = resolution["fix"]
        if resolution["decision"] == "SAFE_FIX" and not _has_completed_safe_fix_evidence(
            fix["changed_files"], fix["validation"], repository_root, fix["repository_root"]
        ):
            raise StrictInputError("safe-fix resolution lacks trusted changed-file and validation evidence")
        event = {
            "schema_version": 1,
            "event_type": "escalation_resolution",
            "source_identity": comment["source_identity"],
            "revision_identity": comment["revision_identity"],
            "revision_key": key,
            "revision_key_version": 1,
            "body_hash": comment["body_hash"],
            "comment_id": comment["comment_id"],
            "request_id": str(comment["comment_id"]),
            "observed_at": datetime.now().astimezone().isoformat(),
            "authority": "USER",
            "decision": resolution["decision"],
            "reason": resolution["reason"],
            "alternative": resolution["alternative"],
            "evidence": resolution["evidence"],
            "fix": fix,
            "resolution_digest": digest,
            "resolves_revision_key": key,
            "posting": {"status": "NOT_REQUESTED"},
        }
        created.append(event)
    return created


def run_local_review(
    raw: str | bytes,
    evidence_by_revision: Mapping[str, Mapping[str, Any]],
    audit_path: Path,
    *,
    repository_root: Path | None = None,
    raw_resolutions: str | bytes | None = None,
) -> dict[str, Any]:
    """Persist a collection snapshot and all new dispositions in one transaction."""
    try:
        snapshot = parse_collection(raw)
        resolutions = parse_resolution_collection(raw_resolutions)
        prior = _canonicalize_prior_events(snapshot, load_audit(audit_path))
        fresh = new_revisions(snapshot, prior)
        snapshot_event = {"schema_version": 1, "event_type": "collection_snapshot", "snapshot_id": snapshot["snapshot_id"], "input_identity": snapshot["input_identity"], "complete": True, "revisions": [revision_key(c) for c in snapshot["comments"]]}
        events = [snapshot_event]
        for comment in fresh:
            key = revision_key(comment)
            event = classify_disposition(
                comment, evidence_by_revision.get(key, {}), repository_root=repository_root
            )
            event["collection_snapshot_id"] = snapshot["snapshot_id"]
            events.append(event)
        for event in _resolution_events(snapshot, resolutions, prior, repository_root):
            event["collection_snapshot_id"] = snapshot["snapshot_id"]
            events.append(event)
        AuditWriter(audit_path).write_events(events)
        return {"status": "RECORDED", "snapshot": snapshot, "events": events[1:]}
    except (StrictInputError, AuditWriteError) as exc:
        return {"status": "BLOCKED", "reason": str(exc), "code": "AUDIT_WRITE_FAILED" if isinstance(exc, AuditWriteError) else "INVALID_INPUT"}


def convergence_state(
    snapshot: Mapping[str, Any] | None,
    events: Iterable[Mapping[str, Any]],
    command_results: Mapping[str, bool],
    *,
    repository_root: Path | None = None,
) -> dict[str, str]:
    """Compute local convergence from caller-supplied, trusted local context.

    Persisted audit events are untrusted input at this boundary.  In
    particular, a ``SAFE_FIX`` event cannot choose the repository root that
    validates it: callers must provide the current trusted local root, and
    the recorded root must exactly match it.
    """
    if not snapshot or snapshot.get("complete") is not True:
        return {"status": "BLOCKED", "reason": "Complete valid local input is required."}
    if not command_results or not all(value is True for value in command_results.values()):
        return {"status": "WORKING", "reason": "Configured local build/lint/test commands have not all passed."}
    try:
        event_list = _canonicalize_prior_events(snapshot, events)
    except StrictInputError as exc:
        return {"status": "BLOCKED", "reason": str(exc)}
    latest = {
        event.get("revision_key"): event for event in event_list
        if event.get("event_type") in {"disposition", "escalation_resolution"}
    }
    required = {revision_key(comment) for comment in snapshot.get("comments", [])}
    if any(key not in latest for key in required):
        return {"status": "WORKING", "reason": "Actionable review request remains."}
    comments = {revision_key(comment): comment for comment in snapshot.get("comments", [])}
    for key in required:
        resolutions = [
            event for event in event_list
            if event.get("event_type") == "escalation_resolution" and event.get("revision_key") == key
        ]
        if len({event.get("resolution_digest") for event in resolutions}) > 1:
            return {"status": "BLOCKED", "reason": "Conflicting escalation resolutions were recorded."}
        if resolutions:
            comment = comments[key]
            resolution = resolutions[-1]
            escalated = any(
                event.get("event_type") == "disposition"
                and event.get("revision_key") == key
                and event.get("decision") == "ESCALATED"
                for event in event_list
            )
            if not escalated or (
                resolution.get("source_identity") != comment.get("source_identity")
                or resolution.get("revision_identity") != comment.get("revision_identity")
                or resolution.get("body_hash") != comment.get("body_hash")
                or resolution.get("comment_id") != comment.get("comment_id")
                or resolution.get("request_id") != str(comment.get("comment_id"))
            ):
                return {"status": "BLOCKED", "reason": "An escalation resolution identity is invalid."}
    decisions = [latest[key].get("decision") for key in required]
    if "ESCALATED" in decisions:
        return {"status": "NEEDS_HUMAN", "reason": "An escalation remains open."}
    if any(decision not in TERMINAL_DECISIONS for decision in decisions):
        return {"status": "BLOCKED", "reason": "A disposition is not terminal."}
    if any(
        event.get("event_type") == "escalation_resolution"
        and (
            event.get("authority") != "USER"
            or event.get("decision") not in {"SAFE_FIX", "REJECTED"}
            or not isinstance(event.get("reason"), str)
            or not event["reason"].strip()
            or not isinstance(event.get("evidence"), list)
            or not event["evidence"]
            or (event.get("decision") == "REJECTED" and not event.get("alternative"))
        )
        for event in (latest[key] for key in required)
    ):
        return {"status": "BLOCKED", "reason": "An escalation resolution is invalid."}
    if any(
        event.get("decision") == "SAFE_FIX"
        and not _has_completed_safe_fix_evidence(
            event.get("fix", {}).get("changed_files") if isinstance(event.get("fix"), Mapping) else None,
            event.get("fix", {}).get("validation") if isinstance(event.get("fix"), Mapping) else None,
            repository_root,
            event.get("fix", {}).get("repository_root") if isinstance(event.get("fix"), Mapping) else None,
        )
        for event in (latest[key] for key in required)
    ):
        return {"status": "BLOCKED", "reason": "A safe fix lacks recorded changed-file or passing validation evidence."}
    return {"status": "CONVERGED", "reason": "All local dispositions are terminal and local commands passed."}


# Compatibility helpers for the original lightweight benchmark and adapter.
def normalize_comments(groups: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    seen: set[str] = set(); result = []
    for kind in ("conversation", "inline", "review"):
        for comment in groups.get(kind, []):
            key = str(comment.get("id", ""))
            if key and key not in seen:
                seen.add(key); result.append({**comment, "source": kind})
    return result


def transition(state: dict[str, Any], signals: list[dict[str, Any]]) -> dict[str, Any]:
    attempts = state.get("fix_attempts", {})
    if state.get("iterations", 0) >= MAX_ITERATIONS or any(count >= MAX_ATTEMPTS for count in attempts.values()):
        return {"status": "BLOCKED", "reason": "Circuit breaker limit reached."}
    kinds = {signal.get("kind") for signal in signals if isinstance(signal, dict)}
    if "comment_escalate" in kinds or state.get("escalations"):
        return {"status": "NEEDS_HUMAN", "reason": "Unresolved design/question signal."}
    if kinds & {"ci_fail", "lint_fail", "build_fail", "comment_actionable"}:
        return {"status": "WORKING", "reason": "Actionable signal remains."}
    if "ci_pending" in kinds:
        return {"status": "WAITING", "reason": "CI is pending."}
    return {"status": "CONVERGED", "reason": "CI green and no actionable or escalated signal."}
