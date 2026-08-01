#!/usr/bin/env python3
"""Materialize a verified RESULT action and its optional organization sync."""

from __future__ import annotations

import argparse
from contextlib import contextmanager, nullcontext
from datetime import date
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import time
from typing import Any, Sequence
import unicodedata

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from harness_core.state import controller_resume, controller_status
from scripts.adapter_render import redact as presentation_redact


FEATURE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
RESULT_DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
FREE_TEXT_ARGV_SECRET = re.compile(
    r"(?P<flag>--?(?:password|passwd|token|secret|authorization|api[-_]?key|credential))"
    r"(?P<space>\s+)(?P<value>[^\s,;]+)", re.IGNORECASE,
)
RAW_CREDENTIAL = re.compile(
    r"gh[pousr]_[A-Za-z0-9_]+|sk-[A-Za-z0-9_-]+|AKIA[A-Z0-9]{16}", re.IGNORECASE
)
SENSITIVE_ASSIGNMENT = re.compile(
    r"(?P<label>\b(?:password|passwd|token|secret|api[-_]?key|credential)\b\s*[:=]\s*)"
    r"(?P<value>(?:Bearer\s+)?[^\s,;]+)", re.IGNORECASE,
)
AUTH_HEADER = re.compile(
    r"(?P<prefix>^|\r\n|\r|\n|\\+(?:r\\+n|[rn])|[^A-Za-z0-9_-])"
    r"(?P<label>(?:Proxy-Authorization|Authorization)[ \t]*:[ \t]*)"
    r"(?P<value>(?:(?!\\+(?:r\\+n|[rn]))[^\r\n])*)"
    r"(?=\r\n|\r|\n|\\+(?:r\\+n|[rn])|$)", re.IGNORECASE,
)
SENSITIVE_KEY = re.compile(
    r"(?:api[_-]?key|authorization|credential(?![_-]source)|password|secret|token)", re.IGNORECASE
)
class ResultActionError(ValueError):
    """A fail-closed RESULT action validation or persistence error."""


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ResultActionError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ResultActionError(f"non-standard JSON constant: {value}")


def _load_json(path: Path) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ResultActionError(f"invalid JSON input {path}: {exc}") from exc


def _inside(root: Path, candidate: Path) -> bool:
    return candidate == root or root in candidate.parents


def _normalized_components(path: Path) -> tuple[str, ...]:
    return tuple(unicodedata.normalize("NFC", part).casefold() for part in path.parts)


def _safe_project_file(root: Path, value: str, *, label: str) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        lexical_relative = candidate.relative_to(root)
    except ValueError as exc:
        raise ResultActionError(f"{label} must be a regular file inside project root") from exc
    if any(part in (".", "..") for part in lexical_relative.parts):
        raise ResultActionError(f"{label} must not contain traversal")
    lexical = root
    for part in lexical_relative.parts:
        lexical = lexical / part
        if lexical.is_symlink():
            raise ResultActionError(f"{label} crosses a symlink")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise ResultActionError(f"{label} is not a readable file: {exc}") from exc
    if not _inside(root, resolved) or not resolved.is_file():
        raise ResultActionError(f"{label} must be a regular file inside project root")
    return resolved


def _preflight_directory(root: Path, relative: Path) -> None:
    current = root
    for part in relative.parts:
        current = current / part
        if current.exists() or current.is_symlink():
            if current.is_symlink() or not current.is_dir():
                raise ResultActionError("unsafe output directory")
        else:
            ancestor = current.parent
            while not ancestor.exists():
                ancestor = ancestor.parent
            if ancestor.is_symlink() or not ancestor.is_dir() or not os.access(ancestor, os.W_OK | os.X_OK):
                raise ResultActionError("output directory is not writable")


def _validate_action(value: Any, feature: str, root: Path) -> bool:
    if not isinstance(value, dict) or value.get("code") != "ACTION":
        raise ResultActionError("controller result code must be ACTION")
    state = value.get("state")
    if not isinstance(state, dict) or state.get("phase") != "RESULT":
        raise ResultActionError("controller result phase must be RESULT")
    if state.get("feature") != feature:
        raise ResultActionError("controller result feature does not match requested feature")
    try:
        status = controller_status(root, feature)
        resumed = controller_resume(root, feature)
    except (OSError, ValueError) as exc:
        raise ResultActionError("live controller state is unavailable") from exc
    if status != resumed:
        raise ResultActionError("live controller status and resume results disagree")
    if value == resumed:
        return False
    live_state = resumed.get("state") if isinstance(resumed, dict) else None
    if (
        isinstance(resumed, dict) and resumed.get("code") == "COMPLETE"
        and isinstance(live_state, dict) and live_state.get("phase") == "RESULT"
        and live_state.get("feature") == feature
    ):
        return True
    else:
        raise ResultActionError("supplied controller action does not exactly match the live RESULT action")


def _validate_evidence(value: Any, feature: str) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ResultActionError("verified evidence schema_version must be 1")
    if value.get("feature") != feature:
        raise ResultActionError("verified evidence feature does not match requested feature")
    if value.get("verified") is not True:
        raise ResultActionError("result evidence must be explicitly verified")
    identity = value.get("completion_identity")
    if not isinstance(identity, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{7,127}", identity) is None:
        raise ResultActionError("verified evidence requires a valid completion_identity")
    if not isinstance(value.get("summary"), str) or not value["summary"].strip():
        raise ResultActionError("verified evidence requires a non-empty summary")
    validation = value.get("validation")
    if not isinstance(validation, list) or not validation:
        raise ResultActionError("verified evidence requires validation entries")
    for entry in validation:
        if not isinstance(entry, dict) or set(entry) != {"name", "status", "evidence"}:
            raise ResultActionError("each validation entry requires only name, status, and evidence")
        if not isinstance(entry["name"], str) or not entry["name"].strip():
            raise ResultActionError("validation name must be non-empty text")
        if entry["status"] != "PASS":
            raise ResultActionError("every validation status must be PASS")
        proof = entry["evidence"]
        if isinstance(proof, bool) or not isinstance(proof, str) or not proof.strip():
            raise ResultActionError("validation evidence must be non-empty text")
    return value


def _redact(value: Any) -> Any:
    rendered = presentation_redact(value)
    if isinstance(rendered, dict):
        return {key: _redact(item) for key, item in rendered.items()}
    if isinstance(rendered, list):
        return [_redact(item) for item in rendered]
    if isinstance(rendered, str):
        return FREE_TEXT_ARGV_SECRET.sub(
            lambda match: f"{match.group('flag')}{match.group('space')}[REDACTED]", rendered
        )
    return rendered


def _durable_redact_text(value: str) -> str:
    def header(match: re.Match[str]) -> str:
        raw = match.group("value")
        stripped = raw.rstrip(" \t")
        if re.fullmatch(r"[^\s,;]+[ \t]+\S.*", stripped) is None:
            return match.group(0)
        return f"{match.group('prefix')}{match.group('label')}[REDACTED]{raw[len(stripped):]}"
    rendered = AUTH_HEADER.sub(header, value)
    rendered = SENSITIVE_ASSIGNMENT.sub(lambda m: f"{m.group('label')}[REDACTED]", rendered)
    rendered = re.sub(r"(?i)(\bBearer\s+)[^\s,;]+", r"\1[REDACTED]", rendered)
    rendered = FREE_TEXT_ARGV_SECRET.sub(
        lambda m: f"{m.group('flag')}{m.group('space')}[REDACTED]", rendered
    )
    return RAW_CREDENTIAL.sub("[REDACTED]", rendered)


def _durable_redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if SENSITIVE_KEY.search(str(key)) else _durable_redact(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_durable_redact(item) for item in value]
    if isinstance(value, str):
        return _durable_redact_text(value)
    return value


def _sync_config(root: Path) -> tuple[str, dict[str, Any], str]:
    config_path = root / ".harness/config.json"
    if not config_path.exists():
        return "SYNC_SKIPPED", {"configured": False, "reason": "knowledge sync is not configured"}, "absent"
    safe = _safe_project_file(root, str(config_path), label="organization sync config")
    raw = safe.read_bytes()
    config = _load_json(safe)
    if not isinstance(config, dict) or config.get("schema_version") != 1:
        raise ResultActionError("organization sync config schema_version must be 1")
    sync = config.get("knowledge_sync", {"enabled": False})
    if not isinstance(sync, dict) or type(sync.get("enabled", False)) is not bool:
        raise ResultActionError("knowledge_sync.enabled must be a boolean")
    digest = hashlib.sha256(raw).hexdigest()
    if not sync.get("enabled"):
        return "SYNC_SKIPPED", {
            "configured": False,
            "reason": "knowledge sync is disabled",
            "config_sha256": digest,
        }, digest
    required = ("compound_root", "destination", "credential_source", "retention_policy")
    if any(not isinstance(sync.get(key), str) or not sync[key].strip() for key in required):
        raise ResultActionError("enabled knowledge sync requires compound_root, destination, credential_source, and retention_policy")
    compound = Path(sync["compound_root"])
    if not compound.is_absolute() or compound.is_symlink():
        raise ResultActionError("compound_root must be an explicit absolute non-symlink directory")
    try:
        compound = compound.resolve(strict=True)
    except OSError as exc:
        raise ResultActionError(f"compound_root is not readable: {exc}") from exc
    if not compound.is_dir() or _inside(root, compound):
        raise ResultActionError("compound_root must be a directory outside project root")
    if not os.access(compound, os.R_OK | os.W_OK):
        raise ResultActionError("compound_root must be readable and writable")
    rules = compound / "CLAUDE.md"
    index = compound / "wiki/index.md"
    if rules.is_symlink() or index.is_symlink() or not rules.is_file() or not index.is_file():
        raise ResultActionError("compound operating rules and wiki/index.md must be regular files")
    if not rules.read_text(encoding="utf-8").strip():
        raise ResultActionError("compound operating rules must be non-empty")
    destination = sync["destination"]
    if destination.startswith("wiki/") and destination.endswith(".md"):
        destination_relative = Path(destination)
    elif FEATURE.fullmatch(destination):
        destination_relative = Path("wiki") / f"{destination}.md"
    else:
        raise ResultActionError("knowledge sync destination must be a wiki path or kebab-case slug")
    if any(part in (".", "..") for part in destination_relative.parts):
        raise ResultActionError("knowledge sync destination must not contain traversal")
    normalized_destination = _normalized_components(destination_relative)
    reserved = {
        _normalized_components(Path("wiki/index.md")),
        _normalized_components(Path("wiki/log.md")),
        _normalized_components(Path(".moondex-sdd-sync.lock")),
    }
    if normalized_destination in reserved or normalized_destination[:2] == ("raw", "projects"):
        raise ResultActionError("knowledge sync destination conflicts with a reserved output role")
    return "SYNC_APPLIED", {
        "configured": True,
        "compound_root": str(compound),
        "destination": destination_relative.as_posix(),
        "credential_source": sync["credential_source"],
        "retention_policy": sync["retention_policy"],
        "redaction_policy": "credential-key values replaced with [REDACTED]",
        "config_sha256": digest,
    }, digest


@contextmanager
def _compound_lock(compound: Path, timeout: float = 8.0):
    """Serialize one complete compound transaction; the 0600 lock is durable metadata."""
    path = compound / ".moondex-sdd-sync.lock"
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ResultActionError("compound sync lock must be a regular file")
    flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags, 0o600)
    except OSError as exc:
        raise ResultActionError("compound sync lock is unavailable") from exc
    try:
        mode = stat.S_IMODE(os.fstat(fd).st_mode)
        if mode != 0o600:
            raise ResultActionError("compound sync lock permissions must be 0600")
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise ResultActionError("compound sync lock timed out")
                time.sleep(0.05)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _action_digest(value: dict[str, Any]) -> str:
    canonical = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(b"moondex-result-action-v1\0" + canonical).hexdigest()


def _validate_output_role_identity(
    root: Path, compound: Path, feature: str, result_date: str,
    evidence: dict[str, Any], destination_relative: Path,
) -> None:
    run_id = hashlib.sha256(evidence["completion_identity"].encode("utf-8")).hexdigest()[:12]
    raw_projects = compound / "raw/projects"
    feature_root = raw_projects / feature
    run_root = feature_root / f"sdd-{result_date}-{run_id}"
    roles = {
        "destination": ("compound", compound / destination_relative, "file"),
        "index": ("compound", compound / "wiki/index.md", "file"),
        "log": ("compound", compound / "wiki/log.md", "file"),
        "lock": ("compound", compound / ".moondex-sdd-sync.lock", "file"),
        "raw-projects": ("compound", raw_projects, "directory"),
        "feature-snapshots": ("compound", feature_root, "directory"),
        "run-snapshot": ("compound", run_root, "directory"),
        "snapshot": ("compound", run_root / "snapshot.json", "file"),
        "project-result-directory": ("project", root / "docs/sdd/result", "directory"),
        "project-report": (
            "project", root / "docs/sdd/result" / f"{result_date}-{feature}-compound-sync.md", "file"
        ),
        "project-result": (
            "project", root / "docs/sdd/result" / f"{result_date}-{feature}.md", "file"
        ),
    }
    normalized: dict[tuple[str, tuple[str, ...]], str] = {}
    for name, (scope, path, _kind) in roles.items():
        base = compound if scope == "compound" else root
        key = (scope, _normalized_components(path.relative_to(base)))
        if key in normalized:
            raise ResultActionError("configured and derived output roles are not filesystem-distinct")
        normalized[key] = name
    destination = roles["destination"][1]
    if destination.parent.is_dir() and not destination.parent.is_symlink():
        normalized_name = unicodedata.normalize("NFC", destination.name).casefold()
        for sibling in destination.parent.iterdir():
            if sibling != destination and unicodedata.normalize("NFC", sibling.name).casefold() == normalized_name:
                raise ResultActionError("knowledge sync destination has a filesystem-normalized alias")
    existing: list[tuple[str, Path, os.stat_result]] = []
    for name, (_scope, path, kind) in roles.items():
        if path.is_symlink():
            raise ResultActionError("configured or derived output role must not be a symlink")
        if not path.exists():
            continue
        if (kind == "file" and not path.is_file()) or (kind == "directory" and not path.is_dir()):
            raise ResultActionError("configured or derived output role has the wrong filesystem type")
        try:
            existing.append((name, path, path.stat()))
        except OSError as exc:
            raise ResultActionError("output role identity could not be verified") from exc
    for index, (left_name, _left_path, left_stat) in enumerate(existing):
        for right_name, _right_path, right_stat in existing[index + 1:]:
            if (left_stat.st_dev, left_stat.st_ino) == (right_stat.st_dev, right_stat.st_ino):
                raise ResultActionError(
                    f"output roles {left_name} and {right_name} alias the same filesystem object"
                )


def _result_bytes(feature: str, evidence: dict[str, Any], verdict: str, sync: dict[str, Any]) -> bytes:
    rendered = json.dumps(_durable_redact(evidence), indent=2, sort_keys=True, ensure_ascii=False)
    sync_rendered = json.dumps(_durable_redact(sync), indent=2, sort_keys=True, ensure_ascii=False)
    return (
        f"# {feature} Result\n\n"
        "- Status: DONE\n"
        f"- Verdict: {verdict}\n"
        "- Controller phase: RESULT\n"
        "- Transition calls: 0\n"
        "- Worker dispatches: 0\n\n"
        "## Verified result evidence\n\n"
        f"```json\n{rendered}\n```\n\n"
        "## Organization sync report\n\n"
        f"```json\n{sync_rendered}\n```\n"
    ).encode("utf-8")


def _append_block(original: bytes, marker: str, block: str) -> bytes:
    text = original.decode("utf-8")
    if marker in text:
        if block.rstrip() not in text:
            raise ResultActionError("existing durable sync marker content is inconsistent")
        return original
    return (text.rstrip() + "\n\n" + block.rstrip() + "\n").encode("utf-8")


def _sync_outputs(
    root: Path, feature: str, result_date: str, evidence: dict[str, Any], sync: dict[str, Any],
    action_sha256: str,
) -> tuple[dict[Path, bytes], dict[str, Any]]:
    compound = Path(sync["compound_root"])
    run_id = hashlib.sha256(evidence["completion_identity"].encode("utf-8")).hexdigest()[:12]
    snapshot_relative = Path("raw/projects") / feature / f"sdd-{result_date}-{run_id}"
    artifacts: dict[str, str] = {}
    candidates = [
        *sorted((root / "docs/sdd/spec").glob(f"*-{feature}.md")),
        *sorted((root / "docs/sdd/design").rglob(f"*-{feature}.md")),
        *sorted((root / "docs/sdd/task" / feature).glob("*.md")),
    ]
    learning = root / ".harness/state/sdd" / feature
    if learning.is_dir() and not learning.is_symlink():
        candidates.extend(
            path for path in sorted(learning.rglob("*"))
            if path.is_file() and path.name in {"learning-buffer.md", "events.jsonl"}
        )
    for path in candidates:
        safe = _safe_project_file(root, str(path), label="sync source artifact")
        artifacts[safe.relative_to(root).as_posix()] = str(_durable_redact(safe.read_text(encoding="utf-8")))
    if not any(path.startswith("docs/sdd/spec/") for path in artifacts) or not any(
        path.startswith("docs/sdd/design/") for path in artifacts
    ) or not any(path.startswith(f"docs/sdd/task/{feature}/") for path in artifacts):
        raise ResultActionError("complete spec, design, and task artifacts are required for sync")
    marker = f"<!-- SDD-SYNC:{feature}:{run_id} -->"
    snapshot = compound / snapshot_relative / "snapshot.json"
    destination = compound / sync["destination"]
    index = compound / "wiki/index.md"
    log = compound / "wiki/log.md"
    page_original = destination.read_bytes() if destination.exists() else b""
    index_original = index.read_bytes()
    if not index_original.decode("utf-8").strip():
        raise ResultActionError("compound wiki index must be non-empty")
    log_original = log.read_bytes() if log.exists() else b"# Log\n"
    page_block = (
        f"{marker}\n## SDD result {result_date}\n\n"
        f"- Feature: `{feature}`\n- Completion: `{evidence['completion_identity']}`\n"
        f"- Summary: {_durable_redact(evidence['summary'])}\n- Source: `{snapshot_relative.as_posix()}`\n"
    )
    page_title = destination.stem
    index_block = f"{marker}\n- [[{page_title}]] — {feature} SDD result"
    log_block = f"{marker}\n- [SDD-SYNC] {result_date} `{feature}` `{run_id}`"
    snapshot_payload = _json_bytes({
        "schema_version": 1, "feature": feature, "run_id": run_id,
        "completion_identity": evidence["completion_identity"],
        "controller_action_digest": {"version": 1, "sha256": action_sha256},
        "artifacts": artifacts, "evidence": _durable_redact(evidence),
    })
    report_relative = Path("docs/sdd/result") / f"{result_date}-{feature}-compound-sync.md"
    report = (
        f"# {feature} Compound Sync\n\n- Status: DONE\n- Verdict: SYNC_APPLIED\n"
        f"- Run ID: `{run_id}`\n- Raw source: `{snapshot_relative.as_posix()}`\n"
        f"- Controller ACTION digest: `v1:{action_sha256}`\n"
        f"- Wiki page: `{sync['destination']}`\n- Wiki index: `wiki/index.md`\n"
        "- Log: `wiki/log.md`\n- Existing raw modified: no\n"
    ).encode("utf-8")
    sync.update({
        "run_id": run_id, "snapshot": str(snapshot),
        "snapshot_relative": snapshot_relative.as_posix(),
        "wiki_page": sync["destination"], "project_report": report_relative.as_posix(),
    })
    return {
        snapshot: snapshot_payload,
        destination: _append_block(page_original, marker, page_block),
        index: _append_block(index_original, marker, index_block),
        log: _append_block(log_original, marker, log_block),
        root / report_relative: report,
    }, sync


def _precheck_target(path: Path, content: bytes) -> bool:
    if path.is_symlink():
        raise ResultActionError("output target must not be a symlink")
    if path.exists():
        if not path.is_file() or path.read_bytes() != content:
            raise ResultActionError("conflicting output already exists")
        return False
    return True


def _create_directories(root: Path, relative: Path, created: list[Path]) -> Path:
    current = root
    for part in relative.parts:
        current = current / part
        if not current.exists():
            current.mkdir()
            created.append(current)
    return current


def _atomic_create(path: Path, content: bytes) -> bool:
    if not _precheck_target(path, content):
        return False
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    linked = False
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_path, path, follow_symlinks=False)
            linked = True
        except FileExistsError:
            if path.is_symlink() or not path.is_file() or path.read_bytes() != content:
                raise ResultActionError(f"conflicting output appeared concurrently: {path}")
            return False
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return True
    except Exception:
        if linked:
            path.unlink(missing_ok=True)
        raise
    finally:
        temporary_path.unlink(missing_ok=True)


def _atomic_replace(path: Path, content: bytes, mode: int | None = None) -> None:
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            temporary_path.chmod(mode)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def run(args: argparse.Namespace) -> dict[str, Any]:
    if FEATURE.fullmatch(args.feature) is None:
        raise ResultActionError("feature must be a lowercase kebab-case slug")
    if RESULT_DATE.fullmatch(args.result_date) is None:
        raise ResultActionError("result-date must use YYYY-MM-DD")
    try:
        date.fromisoformat(args.result_date)
    except ValueError as exc:
        raise ResultActionError("result-date must be a real calendar date") from exc
    supplied_root = Path(args.project_root)
    if supplied_root.is_symlink():
        raise ResultActionError("project root must not be a symlink")
    try:
        root = supplied_root.resolve(strict=True)
    except OSError as exc:
        raise ResultActionError(f"project root is invalid: {exc}") from exc
    if not root.is_dir():
        raise ResultActionError("project root must be a directory")

    controller_path = _safe_project_file(root, args.controller_result, label="controller result")
    evidence_path = _safe_project_file(root, args.evidence, label="verified result evidence")
    action = _load_json(controller_path)
    evidence = _validate_evidence(_load_json(evidence_path), args.feature)
    recovery = _validate_action(action, args.feature, root)
    assert isinstance(action, dict)
    action_sha256 = _action_digest(action)
    verdict, sync, _config_digest = _sync_config(root)
    sync["controller_action_digest"] = {"version": 1, "sha256": action_sha256}
    if verdict == "SYNC_APPLIED" and not getattr(args, "_compound_lock_held", False):
        with _compound_lock(Path(sync["compound_root"])):
            setattr(args, "_compound_lock_held", True)
            try:
                return run(args)
            finally:
                delattr(args, "_compound_lock_held")
    if verdict == "SYNC_APPLIED":
        _validate_output_role_identity(
            root, Path(sync["compound_root"]), args.feature, args.result_date,
            evidence, Path(sync["destination"]),
        )

    result_relative = Path("docs/sdd/result")
    _preflight_directory(root, result_relative)
    result_dir = root / result_relative
    result_path = result_dir / f"{args.result_date}-{args.feature}.md"
    sync_outputs: dict[Path, bytes] = {}
    if verdict == "SYNC_APPLIED":
        sync_outputs, sync = _sync_outputs(
            root, args.feature, args.result_date, evidence, sync, action_sha256
        )

    result_content = _result_bytes(args.feature, evidence, verdict, sync)
    if verdict == "SYNC_APPLIED":
        snapshot_path = Path(sync["snapshot"])
        snapshot_value = json.loads(sync_outputs[snapshot_path])
        snapshot_value["artifacts"][
            f"docs/sdd/result/{args.result_date}-{args.feature}.md"
        ] = result_content.decode("utf-8")
        sync_outputs[snapshot_path] = _json_bytes(snapshot_value)
        report_path = root / sync["project_report"]
        hashes = {
            path.relative_to(Path(sync["compound_root"])).as_posix(): hashlib.sha256(content).hexdigest()
            for path, content in sync_outputs.items()
            if _inside(Path(sync["compound_root"]), path)
        }
        sync_outputs[report_path] = (
            sync_outputs[report_path].decode("utf-8").rstrip()
            + "\n- Durable output SHA-256:\n"
            + "".join(f"  - `{path}`: `{digest}`\n" for path, digest in sorted(hashes.items()))
        ).encode("utf-8")
    outputs = {**sync_outputs, result_path: result_content}
    compound_root = Path(sync["compound_root"]) if verdict == "SYNC_APPLIED" else None
    immutable = {result_path}
    if verdict == "SYNC_APPLIED":
        immutable.add(Path(sync["snapshot"]))
        immutable.add(root / sync["project_report"])
    for path, content in outputs.items():
        base = root if _inside(root, path) else compound_root
        if base is None or not _inside(base, path):
            raise ResultActionError("output target escapes its configured root")
        relative_parent = path.parent.relative_to(base)
        _preflight_directory(base, relative_parent)
        if path in immutable:
            _precheck_target(path, content)
        elif path.is_symlink() or (path.exists() and not path.is_file()):
            raise ResultActionError("mutable sync target must be a regular file")
    if recovery:
        if verdict == "SYNC_APPLIED" and not (root / sync["project_report"]).is_file():
            raise ResultActionError("COMPLETE recovery requires the prior durable sync report")
        if any(not path.is_file() or path.read_bytes() != content for path, content in outputs.items()):
            raise ResultActionError("COMPLETE recovery durable outputs do not exactly match")
        return {
            "Status": "DONE", "Verdict": verdict, "feature": args.feature,
            "result_path": str(result_path), "sync": _redact(sync),
            "transition_calls": 0, "worker_dispatches": 0, "recovered": True,
        }
    created_files: list[Path] = []
    created_dirs: list[Path] = []
    modified: dict[Path, tuple[bytes, int]] = {}
    try:
        for path in outputs:
            base = root if _inside(root, path) else compound_root
            assert base is not None
            _create_directories(base, path.parent.relative_to(base), created_dirs)
        for path, content in outputs.items():
            if path in immutable:
                if _atomic_create(path, content):
                    created_files.append(path)
            elif path.exists():
                old = path.read_bytes()
                if old != content:
                    mode = stat.S_IMODE(path.stat().st_mode)
                    modified[path] = (old, mode)
                    _atomic_replace(path, content, mode)
            else:
                if _atomic_create(path, content):
                    created_files.append(path)
    except Exception:
        for path in reversed(created_files):
            path.unlink(missing_ok=True)
        for path, (content, mode) in reversed(list(modified.items())):
            _atomic_replace(path, content, mode)
        for path in reversed(created_dirs):
            try:
                path.rmdir()
            except OSError:
                pass
        raise

    return {
        "Status": "DONE",
        "Verdict": verdict,
        "feature": args.feature,
        "result_path": str(result_path),
        "sync": _redact(sync),
        "transition_calls": 0,
        "worker_dispatches": 0,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Materialize one verified controller RESULT action.")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--feature", required=True)
    parser.add_argument("--controller-result", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--result-date", default=date.today().isoformat())
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        outcome = run(build_parser().parse_args(argv))
    except ResultActionError as exc:
        print(json.dumps({"Status": "BLOCKED", "error": _redact(str(exc))}, sort_keys=True))
        return 2
    except OSError as exc:
        print(json.dumps({"Status": "BLOCKED", "error": _redact("persistence failed")}, sort_keys=True))
        return 2
    print(json.dumps(outcome, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
