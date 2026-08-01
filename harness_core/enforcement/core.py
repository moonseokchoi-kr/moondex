"""Offline Git enforcement primitives.

All errors carry a stable rule code so a hook, CI job, and an audit artifact
report the same reason rather than reconstructing a potentially different
diff.  No network or hosting-provider API is used here.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from datetime import date
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from harness_core.config import ConfigError, default_config, load_config, validate_config

SHA = re.compile(r"^[0-9a-f]{40}$")
PARSER_VERSION = "enforcement-v2"
UI_SUFFIXES = {".tsx", ".jsx", ".vue", ".svelte", ".css", ".scss", ".html"}
NON_IMPLEMENTATION_ROOTS = {"docs", "tests", ".github", ".harness", "benchmarks", "evals"}
PLUGIN_PROTECTED = ("skills", "agents", ".codex-plugin", "harness_core", "scripts", ".github", "hooks", "tests", "benchmarks", "evals")
PROJECT_IMMUTABLE = (".harness", "scripts", ".github")
SECRET_KEY = r"(?:api[_-]?key|[a-z0-9_-]*(?:secret|token|password))"
ASSIGNMENT = re.compile(rf"(?im)^\s*(?:export\s+)?(?P<key>{SECRET_KEY})\s*[=:]\s*(?P<value>[^#\r\n]+)")
JSON_SECRET = re.compile(rf'(?i)"(?P<key>{SECRET_KEY})"\s*:\s*"(?P<value>[^"]*)"')
BEARER = re.compile(r"(?im)(?:authorization\s*[:=]\s*[\"']?bearer\s+|bearer\s+)(?P<value>[A-Za-z0-9._~+/=-]+)")


class EnforcementError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True)
    if result.returncode:
        raise EnforcementError("GIT_EVIDENCE_UNAVAILABLE", result.stderr.strip() or "git command failed")
    return result.stdout


def _commit(root: Path, value: str, code: str = "RANGE_UNRESOLVED") -> str:
    if not SHA.fullmatch(value or ""):
        raise EnforcementError(code, "expected a 40-hex commit SHA")
    try:
        kind = _git(root, "cat-file", "-t", value).strip()
    except EnforcementError as exc:
        raise EnforcementError(code, f"commit object {value} is unavailable") from exc
    if kind != "commit":
        raise EnforcementError(code, f"object {value} is not a commit")
    return value


def _ancestor(root: Path, base: str, tip: str) -> bool:
    return subprocess.run(["git", "merge-base", "--is-ancestor", base, tip], cwd=root).returncode == 0


def _commits(root: Path, base: str, tip: str) -> tuple[str, ...]:
    commits = tuple(line for line in _git(root, "rev-list", "--reverse", f"{base}..{tip}").splitlines() if line)
    if not commits:
        raise EnforcementError("RANGE_UNRESOLVED", "outgoing range is empty or cannot be proven")
    return commits


def resolve_outgoing_range(
    root: Path,
    *,
    source: str,
    target_ref: str,
    tip: str,
    remote_base: str | None = None,
    integration_base: str | None = None,
) -> dict[str, Any]:
    """Resolve one complete ref update; force/multi-ref callers must invoke per ref.

    An all-zero remote base is an initial push and requires an explicit trusted
    integration base.  This intentionally never falls back to ``HEAD~1``.
    """
    root = Path(_git(root, "rev-parse", "--show-toplevel").strip()).resolve()
    tip = _commit(root, tip)
    zero = remote_base is None or set(remote_base) == {"0"}
    if zero:
        if not integration_base:
            raise EnforcementError("RANGE_UNRESOLVED", "initial push requires an explicit integration base")
        # A ref is allowed only when it resolves to a commit locally; record its SHA.
        base_candidate = integration_base
        if not SHA.fullmatch(base_candidate):
            base_candidate = _git(root, "rev-parse", "--verify", f"{integration_base}^{{commit}}").strip()
        base_candidate = _commit(root, base_candidate)
        merge = _git(root, "merge-base", base_candidate, tip).strip()
        if not merge:
            raise EnforcementError("RANGE_UNRESOLVED", "integration base has no provable merge base")
        base = _commit(root, merge)
        resolution = "initial-push"
    else:
        base = _commit(root, remote_base)
        if not _ancestor(root, base, tip):
            raise EnforcementError("RANGE_UNRESOLVED", "force push or non-ancestor remote base is not supported")
        resolution = "explicit-base" if source == "ci" else "existing-remote-base"
    return {
        "schema_version": 1, "source": source, "target_ref": target_ref,
        "base": base, "tip": tip, "commit_ids": list(_commits(root, base, tip)),
        "resolution": resolution,
        "proof": ["git cat-file -t", "git merge-base", "git rev-list --reverse"],
    }


def canonical_path(root: Path, raw: str) -> str:
    """Return a physical repository-relative path or fail closed.

    Git name-status paths are paths, not shell input: reject NUL, absolute and
    traversal before resolving, then prove physical containment including an
    existing symlink chain.
    """
    if "\0" in raw or os.path.isabs(raw):
        raise EnforcementError("INVALID_PATH", "absolute or NUL-containing changed path")
    parts = [p for p in raw.replace("\\", "/").split("/") if p not in ("", ".")]
    if ".." in parts:
        raise EnforcementError("INDETERMINATE_PATH", "traversal path cannot be classified")
    if not parts:
        raise EnforcementError("INVALID_PATH", "empty changed path")
    physical_root = root.resolve()
    candidate = root.joinpath(*parts)
    # Existing ancestors must resolve inside root; resolve(strict=False) covers
    # nonexistent leaves without accidentally treating a broken link as safe.
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink():
            try:
                resolved = current.resolve(strict=True)
            except OSError as exc:
                raise EnforcementError("OUTSIDE_OR_INDETERMINATE", "broken symlink changed path") from exc
            if os.path.commonpath((str(physical_root), str(resolved))) != str(physical_root):
                raise EnforcementError("OUTSIDE_OR_INDETERMINATE", "symlink leaves repository root")
    try:
        resolved = candidate.resolve(strict=False)
    except OSError as exc:
        raise EnforcementError("OUTSIDE_OR_INDETERMINATE", "cannot resolve changed path") from exc
    if os.path.commonpath((str(physical_root), str(resolved))) != str(physical_root):
        raise EnforcementError("OUTSIDE_OR_INDETERMINATE", "changed path leaves repository root")
    # Policy is expressed against the physical repository tree.  Returning the
    # lexical input here would let an in-root alias such as ``linked ->
    # scripts`` evade the immutable ``scripts/**`` protection.  ``resolved``
    # retains a non-existent final component while resolving every extant
    # symlink ancestor, so ordinary new paths remain valid.
    try:
        return resolved.relative_to(physical_root).as_posix()
    except ValueError as exc:
        # Keep this fail-closed even if a platform-specific path comparison
        # above produced an unexpected result.
        raise EnforcementError("OUTSIDE_OR_INDETERMINATE", "changed path leaves repository root") from exc


def changed_file_events(root: Path, record: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for commit in record["commit_ids"]:
        output = _git(root, "diff-tree", "--no-commit-id", "--name-status", "-r", "-M", "-C", commit)
        for line in output.splitlines():
            fields = line.split("\t")
            if len(fields) < 2:
                raise EnforcementError("CHANGED_FILE_INDETERMINATE", "invalid git name-status output")
            status = fields[0]
            raw_paths = fields[1:] if status.startswith(("R", "C")) else fields[1:2]
            if status.startswith(("R", "C")) and len(raw_paths) != 2:
                raise EnforcementError("CHANGED_FILE_INDETERMINATE", "rename/copy lacks both paths")
            events.append({"commit": commit, "status": status, "paths": [canonical_path(root, path) for path in raw_paths]})
    return events


def _protected(path: str, roots: Iterable[str]) -> bool:
    first = path.split("/", 1)[0]
    return first in set(roots)


def _is_placeholder(value: str) -> bool:
    value = value.strip().strip("'\"").rstrip(",;")
    low = value.lower()
    return (not value or len(value) < 8 or any(c.isspace() for c in value) or value.startswith(("$", "{{", "${", "<"))
            or low.startswith(("os.environ", "process.env", "getenv(", "env(", "your_", "your-", "replace_", "replace-", "example"))
            or low in {"required", "optional", "none", "null", "undefined", "changeme", "not-a-secret"})


def _secret_matches(text: str) -> list[tuple[str, int]]:
    hits: list[tuple[str, int]] = []
    for label, pattern in (("assignment", ASSIGNMENT), ("json-credential", JSON_SECRET), ("bearer", BEARER)):
        for match in pattern.finditer(text):
            if not _is_placeholder(match.group("value")):
                hits.append((label, text.count("\n", 0, match.start()) + 1))
    return hits


def _base_file(root: Path, base: str | None, name: str, trusted: bool) -> bytes | None:
    if trusted:
        assert base
        result = subprocess.run(["git", "show", f"{base}:{name}"], cwd=root, capture_output=True)
        return result.stdout if result.returncode == 0 else None
    path = root / name
    return path.read_bytes() if path.exists() else None


def _policy_snapshot(root: Path, base: str | None, trusted: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    raw = _base_file(root, base, ".harness/config.json", trusted)
    try:
        payload = json.loads(raw.decode("utf-8")) if raw else default_config()
        config = validate_config(payload, Path(".harness/config.json"))
    except (UnicodeDecodeError, json.JSONDecodeError, ConfigError) as exc:
        raise EnforcementError("POLICY_INVALID", "trusted policy cannot be parsed") from exc
    plugin = (_base_file(root, base, ".codex-plugin/plugin.json", trusted) is not None)
    roots = list(PLUGIN_PROTECTED if plugin else PROJECT_IMMUTABLE)
    for item in config["security"]["protected_paths"]:
        try:
            canonical_path(root, item)
        except EnforcementError as exc:
            raise EnforcementError("POLICY_INVALID", "protected_paths contains invalid path") from exc
        roots.append(item.split("/", 1)[0])
    allowlist_raw = _base_file(root, base, ".harness/secret-allowlist.json", trusted)
    return config, {
        "schema_version": 1, "parser_version": PARSER_VERSION,
        "policy_source": "trusted-base" if trusted else "untrusted-head",
        "policy_commit_sha": base if trusted else None,
        "config_blob_sha256": hashlib.sha256(raw or b"{}").hexdigest(),
        "allowlist_blob_sha256": hashlib.sha256(allowlist_raw or b"[]").hexdigest(),
        "repository_mode": "plugin" if plugin else "project", "protected_roots": sorted(set(roots)),
    }


def _content_at(root: Path, commit: str, path: str) -> str | None:
    result = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=root, capture_output=True)
    if result.returncode:
        return None  # deletion/rename source has no new content
    try:
        return result.stdout.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise EnforcementError("SECRET_SCAN_INDETERMINATE", f"non-UTF8 content in {path}") from exc


def _allowlist(root: Path, base: str | None, trusted: bool) -> list[dict[str, Any]]:
    raw = _base_file(root, base, ".harness/secret-allowlist.json", trusted)
    if raw is None:
        return []
    try:
        records = json.loads(raw.decode("utf-8"))
        if not isinstance(records, list):
            raise ValueError
        for record in records:
            if not isinstance(record, dict) or not all(isinstance(record.get(key), str) and record[key] for key in ("id", "file", "pattern_class", "reason", "expiry", "approver")) or not isinstance(record.get("line"), int):
                raise ValueError
            if date.fromisoformat(record["expiry"]) < date.today():
                raise EnforcementError("ALLOWLIST_INVALID", "secret allowlist record is expired")
        return records
    except EnforcementError:
        raise
    except Exception as exc:
        raise EnforcementError("ALLOWLIST_INVALID", "secret allowlist must be a valid scoped, approved record list") from exc


def _approved_allowlist(records: Iterable[dict[str, Any]], path: str, kind: str, line: int) -> str | None:
    for record in records:
        if record["file"] == path and record["pattern_class"] == kind and record["line"] == line:
            return record["id"]
    return None


def _evidence_valid(path: Path, *, tdd: bool) -> bool:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(value, dict):
        return False
    if tdd:
        return all(isinstance(value.get(key), str) and value[key].strip() for key in ("red_evidence", "green_command"))
    return (isinstance(value.get("command"), str) and bool(value["command"].strip())) or (
        isinstance(value.get("evidence"), list) and any(isinstance(item, str) and item.strip() for item in value["evidence"])
    )


@dataclass(frozen=True)
class VerificationResult:
    status: str
    range: dict[str, Any]
    changed_files: list[dict[str, Any]]
    policy_snapshot: dict[str, Any]
    outcomes: list[dict[str, Any]]

    def audit(self) -> dict[str, Any]:
        return {"schema_version": 1, "status": self.status, "range": self.range, "changed_files": self.changed_files,
                "policy_snapshot": self.policy_snapshot, "outcomes": self.outcomes}


def verify_outgoing(root: Path, *, source: str, target_ref: str, tip: str, remote_base: str | None,
                    integration_base: str | None, branch: str, default_branch: str, trusted_policy: bool = False,
                    policy_base: str | None = None) -> VerificationResult:
    root = Path(root).resolve()
    # A first push must use the configured integration ref.  The caller may
    # supply a SHA only after resolving that ref, never an arbitrary fallback.
    if remote_base is None or set(remote_base) == {"0"}:
        local_config = load_config(root / ".harness/config.json")
        configured_ref = local_config["ci"]["integration_base_ref"]
        if integration_base is None:
            integration_base = configured_ref
        try:
            resolved_configured = _git(root, "rev-parse", "--verify", f"{configured_ref}^{{commit}}").strip()
            resolved_requested = _git(root, "rev-parse", "--verify", f"{integration_base}^{{commit}}").strip()
        except EnforcementError as exc:
            raise EnforcementError(
                "INTEGRATION_BASE_UNRESOLVED",
                "configured integration_base_ref cannot be resolved to a local commit",
            ) from exc
        if resolved_requested != resolved_configured:
            raise EnforcementError("INTEGRATION_BASE_UNTRUSTED", "initial-push base must equal configured integration_base_ref")
        integration_base = resolved_configured
    record = resolve_outgoing_range(root, source=source, target_ref=target_ref, tip=tip, remote_base=remote_base, integration_base=integration_base)
    if trusted_policy and not policy_base:
        raise EnforcementError("POLICY_BASE_UNRESOLVED", "CI approval requires an explicit immutable base SHA")
    if trusted_policy:
        policy_base = _commit(root, policy_base, "POLICY_BASE_UNRESOLVED")
        if source != "ci" or remote_base is None or set(remote_base) == {"0"} or policy_base != _commit(root, remote_base, "POLICY_BASE_UNRESOLVED"):
            raise EnforcementError("POLICY_BASE_UNTRUSTED", "trusted policy must be the verified CI range base SHA")
    config, snapshot = _policy_snapshot(root, policy_base, trusted_policy)
    events = changed_file_events(root, record)
    allowlist = _allowlist(root, policy_base, trusted_policy)
    paths = sorted({path for event in events for path in event["paths"]})
    outcomes: list[dict[str, Any]] = []
    implementation = [p for p in paths if p.split("/", 1)[0] not in NON_IMPLEMENTATION_ROOTS and not p.endswith((".md", ".txt"))]
    ui = [p for p in paths if Path(p).suffix.lower() in UI_SUFFIXES]
    protected = [p for p in paths if _protected(p, snapshot["protected_roots"])]
    if branch == default_branch and implementation:
        outcomes.append({"rule": "BRANCH_DEFAULT", "status": "FAIL", "files": implementation, "remediation": "use an isolated feature branch"})
    # Evidence intentionally comes from a state file and is checked only after full range classification.
    if implementation and not _evidence_valid(root / ".harness/state/tdd-manifest.json", tdd=True):
        outcomes.append({"rule": "TDD_EVIDENCE_MISSING", "status": "FAIL", "files": implementation, "remediation": "add TDD manifest evidence"})
    if ui and not _evidence_valid(root / ".harness/state/e2e-config.json", tdd=False):
        outcomes.append({"rule": "E2E_EVIDENCE_MISSING", "status": "FAIL", "files": ui, "remediation": "add E2E evidence"})
    if protected:
        outcomes.append({"rule": "PROTECTED_PATH", "status": "FAIL", "files": protected, "remediation": "obtain governance review"})
    if config["security"]["secret_scan"]:
        for event in events:
            for path in event["paths"]:
                text = _content_at(root, event["commit"], path)
                if text is None:
                    continue
                matches = _secret_matches(text)
                blocked = sorted({kind for kind, line in matches if not _approved_allowlist(allowlist, path, kind, line)})
                approved = sorted({record_id for kind, line in matches if (record_id := _approved_allowlist(allowlist, path, kind, line))})
                if approved:
                    outcomes.append({"rule": "SECRET_ALLOWLIST", "status": "PASS", "file": path, "record_ids": approved})
                if blocked:
                    outcomes.append({"rule": "SECRET_EXPOSED", "status": "FAIL", "file": path, "classes": blocked,
                                     "remediation": "remove literal and use an approved reference"})
    if not outcomes:
        outcomes.append({"rule": "ENFORCEMENT", "status": "PASS", "files": paths})
    return VerificationResult("FAIL" if any(o["status"] == "FAIL" for o in outcomes) else "PASS", record, events, snapshot, outcomes)

# Local-first enforcement.  The outgoing-range functions above are retained as
# an advisory extension; baseline Codex verification deliberately consumes only
# current-worktree or explicitly supplied local changed-file evidence.
LOCAL_REPORT_VERSION = 3


def _local_root(root: Path) -> Path:
    try:
        return Path(root).resolve(strict=True)
    except OSError as exc:
        raise EnforcementError("WORKTREE_UNAVAILABLE", "project root cannot be resolved") from exc


def _local_mode(root: Path) -> str:
    return "plugin" if (root / ".codex-plugin" / "plugin.json").is_file() else "project"


def _local_protected_roots(root: Path, config: dict[str, Any]) -> tuple[str, ...]:
    roots = set(_local_immutable_protected_roots(root))
    for item in config["security"]["protected_paths"]:
        canonical = canonical_path(root, item)
        roots.add(canonical.split("/", 1)[0])
    return tuple(sorted(roots))


def local_protected_roots(root: Path) -> tuple[str, ...]:
    """Return the complete current local protected-root policy.

    Consumers which decide whether an automated change is eligible must use
    this function instead of accepting a partial caller-supplied list.  It
    resolves the local project root and reads the same worktree configuration
    and immutable roots as :func:`verify_local`; an unusable root or invalid
    configuration therefore fails closed with :class:`EnforcementError`.
    """
    root = _local_root(root)
    if not root.is_dir():
        raise EnforcementError("WORKTREE_UNAVAILABLE", "project root is not a directory")
    config = _snapshot_config(_local_snapshot(root, "worktree", None))
    return _local_protected_roots(root, config)


def _local_immutable_protected_roots(root: Path) -> tuple[str, ...]:
    """Return built-in roots which a local config may not waive.

    ``--allow-protected-path`` is only a convenience for an owner-added local
    protection.  It must never turn the plugin's own delivery/verification
    assets into ordinary project files.
    """
    return PLUGIN_PROTECTED if _local_mode(root) == "plugin" else (".harness",)


@dataclass(frozen=True)
class _LocalSnapshot:
    """One coherent source for every local enforcement input.

    Hooks must never mix an index/commit's implementation with mutable
    worktree policy or evidence.  Missing files are represented as ``None``;
    callers decide whether that is a secure default (config) or failed
    evidence (TDD/E2E).
    """

    root: Path
    kind: str
    revision: str | None = None

    def read(self, path: str) -> bytes | None:
        if self.kind == "worktree":
            candidate = self.root / path
            try:
                if not candidate.exists():
                    return None
                if not candidate.is_file():
                    raise EnforcementError("SNAPSHOT_INPUT_UNREADABLE", f"snapshot path is not a regular file: {path}")
                return candidate.read_bytes()
            except OSError as exc:
                raise EnforcementError("SNAPSHOT_INPUT_UNREADABLE", f"cannot read snapshot path: {path}") from exc
        spec = f":{path}" if self.kind == "index" else f"{self.revision}:{path}"
        exists = subprocess.run(["git", "cat-file", "-e", spec], cwd=self.root, capture_output=True)
        if exists.returncode:
            return None
        result = subprocess.run(["git", "show", spec], cwd=self.root, capture_output=True)
        if result.returncode:
            raise EnforcementError("SNAPSHOT_INPUT_UNREADABLE", f"cannot read {self.kind} snapshot blob for {path}")
        return result.stdout

    def audit(self) -> dict[str, Any]:
        files = (".harness/config.json", ".harness/secret-allowlist.json",
                 ".harness/state/tdd-manifest.json", ".harness/state/e2e-config.json")
        hashes: dict[str, str | None] = {}
        for path in files:
            raw = self.read(path)
            hashes[path] = hashlib.sha256(raw).hexdigest() if raw is not None else None
        return {"kind": self.kind, "revision": self.revision, "input_sha256": hashes}


def _local_snapshot(root: Path, kind: str, revision: str | None) -> _LocalSnapshot:
    if kind not in {"worktree", "index", "revision"}:
        raise EnforcementError("CONTENT_SOURCE_INVALID", "content source must be worktree, index, or revision")
    if kind == "revision":
        if not revision:
            raise EnforcementError("CONTENT_REVISION_UNRESOLVED", "revision content source requires a commit SHA")
        revision = _commit(root, revision, "CONTENT_REVISION_UNRESOLVED")
    elif revision is not None:
        raise EnforcementError("CONTENT_REVISION_UNEXPECTED", "content revision is valid only with revision content source")
    return _LocalSnapshot(root, kind, revision)


def _snapshot_config(snapshot: _LocalSnapshot) -> dict[str, Any]:
    raw = snapshot.read(".harness/config.json")
    if raw is None:
        return default_config()
    try:
        return validate_config(json.loads(raw.decode("utf-8")), Path(".harness/config.json"))
    except (UnicodeDecodeError, json.JSONDecodeError, ConfigError) as exc:
        raise EnforcementError("POLICY_INVALID", "snapshot configuration cannot be parsed") from exc


def _snapshot_allowlist(snapshot: _LocalSnapshot) -> list[dict[str, Any]]:
    raw = snapshot.read(".harness/secret-allowlist.json")
    if raw is None:
        return []
    try:
        records = json.loads(raw.decode("utf-8"))
        if not isinstance(records, list):
            raise ValueError
        for record in records:
            if not isinstance(record, dict) or not all(isinstance(record.get(key), str) and record[key] for key in ("id", "file", "pattern_class", "reason", "expiry", "approver")) or not isinstance(record.get("line"), int):
                raise ValueError
            if date.fromisoformat(record["expiry"]) < date.today():
                raise EnforcementError("ALLOWLIST_INVALID", "secret allowlist record is expired")
        return records
    except EnforcementError:
        raise
    except Exception as exc:
        raise EnforcementError("ALLOWLIST_INVALID", "snapshot secret allowlist is invalid") from exc


def _event(source: str, raw_paths: Iterable[str]) -> list[dict[str, Any]]:
    paths = [path for path in raw_paths if path]
    if not paths:
        raise EnforcementError("CHANGED_FILE_INDETERMINATE", "no usable changed-file input; supply --changed-file or use a Git worktree")
    return [{"source": source, "status": "M", "paths": paths}]


def worktree_changed_events(root: Path) -> list[dict[str, Any]]:
    """Collect staged/unstaged current-worktree paths; untracked files too.

    ``--name-status -z`` keeps spaces and rename/copy pairs unambiguous.  A
    clean worktree is indeterminate for a gate, rather than proof of success.
    """
    try:
        output = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    except EnforcementError:
        raise EnforcementError("CHANGED_FILE_INDETERMINATE", "Git worktree changed-file evidence is unavailable")
    entries: list[dict[str, Any]] = []
    fields = output.split("\0")
    index = 0
    while index < len(fields):
        field = fields[index]
        index += 1
        if not field:
            continue
        if len(field) < 4:
            raise EnforcementError("CHANGED_FILE_INDETERMINATE", "invalid Git worktree status")
        status, path = field[:2], field[3:]
        paths = [path]
        # porcelain rename/copy emits destination then original as the next NUL field.
        if "R" in status or "C" in status:
            if index >= len(fields) or not fields[index]:
                raise EnforcementError("CHANGED_FILE_INDETERMINATE", "rename/copy lacks both changed paths")
            paths.append(fields[index])
            index += 1
        entries.append({"source": "worktree", "status": status, "paths": paths})
    if not entries:
        raise EnforcementError("CHANGED_FILE_INDETERMINATE", "worktree has no changed files")
    return entries


def _canonical_local_events(root: Path, events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    canonical: list[dict[str, Any]] = []
    for event in events:
        paths = event.get("paths")
        if not isinstance(paths, list) or not paths:
            raise EnforcementError("CHANGED_FILE_INDETERMINATE", "changed-file event has no paths")
        # Keep the Git spelling separately for snapshot reads.  Policy and
        # reports use the canonical physical spelling, but an index/tree blob
        # is addressed by its lexical Git path (which may pass through an
        # in-repository symlink).
        canonical.append({
            "source": event.get("source", "explicit"),
            "status": event.get("status", "M"),
            "paths": [canonical_path(root, str(path)) for path in paths],
            "_content_paths": [str(path) for path in paths],
        })
    return canonical


def _public_local_events(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove internal content-addressing details from the durable report."""
    return [{key: value for key, value in event.items() if key != "_content_paths"} for event in events]


def _decode_snapshot(path: str, raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise EnforcementError("SECRET_SCAN_INDETERMINATE", f"non-UTF8 content in {path}") from exc


def _local_content(snapshot: _LocalSnapshot, path: str) -> str | None:
    """Read exactly the content represented by the local verification event.

    A pre-commit hook must inspect index blobs, not files that may have been
    edited after staging.  Pre-push uses the supplied local commit tree for
    the same reason.  A missing blob is a normal deletion/rename source;
    failures after a blob is known to exist are indeterminate and fail closed.
    """
    raw = snapshot.read(path)
    return _decode_snapshot(path, raw) if raw is not None else None


def _snapshot_evidence_valid(snapshot: _LocalSnapshot, path: str, *, tdd: bool) -> bool:
    raw = snapshot.read(path)
    if raw is None:
        return False
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(value, dict):
        return False
    if tdd:
        return all(isinstance(value.get(key), str) and value[key].strip() for key in ("red_evidence", "green_command"))
    return (isinstance(value.get("command"), str) and bool(value["command"].strip())) or (
        isinstance(value.get("evidence"), list) and any(isinstance(item, str) and item.strip() for item in value["evidence"])
    )


def local_indeterminate_audit(root: Path, source: str, error: EnforcementError) -> dict[str, Any]:
    """Create the redacted, versioned artifact required for unusable input."""
    identity = hashlib.sha256(str(Path(root).resolve(strict=False)).encode("utf-8")).hexdigest()[:16]
    return {
        "schema_version": LOCAL_REPORT_VERSION,
        "status": "INDETERMINATE",
        "source": source,
        "worktree": {"identity": identity, "mode": _local_mode(Path(root))},
        "changed_files": [],
        "rules": ["branch", "tdd", "e2e", "protected-path", "secret"],
        "outcomes": [{"rule": error.code, "status": "INDETERMINATE", "reason": str(error)}],
    }


def verify_local(
    root: Path,
    *,
    source: str,
    changed_files: Iterable[str] | None = None,
    branch: str | None = None,
    default_branch: str = "main",
    allowed_protected_paths: Iterable[str] = (),
    content_source: str = "worktree",
    content_revision: str | None = None,
) -> "LocalVerificationResult":
    """Run the baseline deterministic local gate and return a redacted report."""
    root = _local_root(root)
    if source not in {"explicit", "worktree", "hook"}:
        raise EnforcementError("SOURCE_INVALID", "local enforcement source must be explicit, worktree, or hook")
    snapshot = _local_snapshot(root, content_source, content_revision)
    if source == "worktree":
        events = worktree_changed_events(root)
    else:
        events = _event(source, changed_files or ())
    events = _canonical_local_events(root, events)
    config = _snapshot_config(snapshot)
    protected_roots = _local_protected_roots(root, config)
    allowlist = _snapshot_allowlist(snapshot)
    paths = sorted({path for event in events for path in event["paths"]})
    if not paths:
        raise EnforcementError("CHANGED_FILE_INDETERMINATE", "no canonical changed paths")
    if branch is None:
        try:
            branch = _git(root, "symbolic-ref", "--quiet", "--short", "HEAD").strip() or None
        except EnforcementError:
            branch = None
    if not branch:
        raise EnforcementError("BRANCH_INDETERMINATE", "branch is unavailable; pass --branch")
    outcomes: list[dict[str, Any]] = []
    implementation = [p for p in paths if p.split("/", 1)[0] not in NON_IMPLEMENTATION_ROOTS and not p.endswith((".md", ".txt"))]
    ui = [p for p in paths if Path(p).suffix.lower() in UI_SUFFIXES]
    allowed = {canonical_path(root, value) for value in allowed_protected_paths}
    immutable_roots = _local_immutable_protected_roots(root)
    protected = [
        path for path in paths
        if _protected(path, protected_roots)
        and (path not in allowed or _protected(path, immutable_roots))
    ]
    if branch == default_branch and implementation:
        outcomes.append({"rule": "BRANCH_DEFAULT", "status": "FAIL", "files": implementation,
                         "remediation": "use an isolated feature branch/worktree"})
    if implementation and not _snapshot_evidence_valid(snapshot, ".harness/state/tdd-manifest.json", tdd=True):
        outcomes.append({"rule": "TDD_EVIDENCE_MISSING", "status": "FAIL", "files": implementation,
                         "remediation": "add .harness/state/tdd-manifest.json with red_evidence and green_command"})
    if ui and not _snapshot_evidence_valid(snapshot, ".harness/state/e2e-config.json", tdd=False):
        outcomes.append({"rule": "E2E_EVIDENCE_MISSING", "status": "FAIL", "files": ui,
                         "remediation": "add .harness/state/e2e-config.json evidence"})
    if protected:
        outcomes.append({"rule": "PROTECTED_PATH", "status": "FAIL", "files": protected,
                         "remediation": "request review before changing protected local harness assets"})
    if config["security"]["secret_scan"]:
        for event in events:
            for path, content_path in zip(event["paths"], event["_content_paths"], strict=True):
                text = _local_content(snapshot, content_path)
                if text is None:
                    continue
                matches = _secret_matches(text)
                approved = sorted({record_id for kind, line in matches if (record_id := _approved_allowlist(allowlist, path, kind, line))})
                blocked = sorted({kind for kind, line in matches if not _approved_allowlist(allowlist, path, kind, line)})
                if approved:
                    outcomes.append({"rule": "SECRET_ALLOWLIST", "status": "PASS", "file": path, "record_ids": approved})
                if blocked:
                    outcomes.append({"rule": "SECRET_EXPOSED", "status": "FAIL", "file": path, "classes": blocked,
                                     "remediation": "remove possible secret literal and use an approved secret reference"})
    if not outcomes:
        outcomes.append({"rule": "ENFORCEMENT", "status": "PASS", "files": paths})
    return LocalVerificationResult(
        status="FAIL" if any(item["status"] == "FAIL" for item in outcomes) else "PASS",
        source=source, root=root, branch=branch, default_branch=default_branch, changed_files=_public_local_events(events),
        protected_roots=protected_roots, snapshot=snapshot.audit(), outcomes=outcomes,
    )


@dataclass(frozen=True)
class LocalVerificationResult:
    status: str
    source: str
    root: Path
    branch: str
    default_branch: str
    changed_files: list[dict[str, Any]]
    protected_roots: tuple[str, ...]
    snapshot: dict[str, Any]
    outcomes: list[dict[str, Any]]

    def audit(self) -> dict[str, Any]:
        identity = hashlib.sha256(str(self.root).encode("utf-8")).hexdigest()[:16]
        return {
            "schema_version": LOCAL_REPORT_VERSION,
            "status": self.status,
            "source": self.source,
            "worktree": {"identity": identity, "mode": _local_mode(self.root)},
            "branch": self.branch,
            "default_branch": self.default_branch,
            "changed_files": self.changed_files,
            "rules": ["branch", "tdd", "e2e", "protected-path", "secret"],
            "snapshot": self.snapshot,
            "policy": {"parser_version": PARSER_VERSION,
                       "protected_roots": list(self.protected_roots)},
            "outcomes": self.outcomes,
        }
