"""Deterministic, local-first learning routing.

This module only decides and records dispositions.  It never writes a target
file or invokes an external knowledge service.  Repository path identity and
the protected-root policy remain owned by :mod:`harness_core.enforcement`.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from harness_core.enforcement import EnforcementError, canonical_path, local_protected_roots


def _entry_id(entry: dict[str, Any]) -> str:
    value = entry.get("id")
    if isinstance(value, str) and value.strip():
        return value
    encoded = json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


def process(
    entries: list[dict[str, Any]],
    cursor: int = 0,
    limit: int = 5,
    *,
    known_entry_ids: Iterable[str] = (),
) -> dict[str, Any]:
    """Consume an append-only slice once, recording deterministic provenance.

    Invalid entries consume a cursor position but cannot become a learning
    record.  ``known_entry_ids`` is persisted by the caller and makes restart
    processing idempotent without mutating the raw input.
    """
    if cursor < 0 or limit < 1:
        raise ValueError("cursor must be non-negative and limit must be positive")
    selected = entries[cursor : cursor + limit]
    seen = {item for item in known_entry_ids if isinstance(item, str)}
    accepted: list[dict[str, Any]] = []
    duplicates: list[str] = []
    rejected_positions: list[int] = []
    for offset, entry in enumerate(selected):
        if not isinstance(entry, dict):
            rejected_positions.append(cursor + offset)
            continue
        entry_id = _entry_id(entry)
        if entry_id in seen:
            duplicates.append(entry_id)
            continue
        seen.add(entry_id)
        item = deepcopy(entry)
        item["provenance"] = {"entry_id": entry_id, "source_cursor": cursor + offset}
        accepted.append(item)
    return {
        "entries": accepted,
        "next_cursor": cursor + len(selected),
        "duplicate_entry_ids": duplicates,
        "rejected_positions": rejected_positions,
    }


def _is_protected(path: str, protected_roots: Iterable[str]) -> bool:
    root = path.split("/", 1)[0]
    return root in set(protected_roots)


def _effective_protected_roots(root: Path, protected_roots: Iterable[str]) -> tuple[str, ...]:
    """Use T-7's current local policy, with caller roots only additive.

    The local configuration is authoritative because it is the only complete
    policy for this worktree.  A caller's list can request extra protection,
    but cannot omit owner-configured or immutable T-7 roots.
    """
    additions = {value for value in protected_roots if isinstance(value, str)}
    return tuple(sorted(set(local_protected_roots(root)) | additions))


def _legacy_tier_for(paths: list[str]) -> str:
    """Compatibility-only behavior for pre-local-policy callers.

    New callers must pass ``root`` and T-7's ``protected_roots``.  This keeps
    the original portable API usable while adapters migrate to the safe API.
    """
    protected = ("harness_core/", "skills/", "agents/", ".codex-plugin/", "hooks/")
    return "harness" if any(path.startswith(protected) for path in paths) else "project"


def tier_for(paths: list[str], *, root: Path | None = None, protected_roots: Iterable[str] = ()) -> str:
    """Classify canonical targets using T-7's protected-root result.

    A caller without a repository context receives only the historical
    compatibility classification; it must not be used to authorize edits.
    """
    if root is None:
        return _legacy_tier_for(paths)
    canonical = [canonical_path(Path(root), path) for path in paths]
    return "harness" if any(_is_protected(path, _effective_protected_roots(Path(root), protected_roots)) for path in canonical) else "project"


def benchmark_adoption_outcome(
    *, baseline_recorded: bool, train_improved: bool, held_out_regressions: int,
) -> dict[str, Any]:
    """Keep harness adoption explicitly separate from an application edit."""
    missing = []
    if not baseline_recorded:
        missing.append("baseline_recorded")
    if not train_improved:
        missing.append("train_improved")
    if held_out_regressions != 0:
        missing.append("held_out_zero_regressions")
    if missing:
        return {"action": "PROPOSAL", "reason": "Benchmark adoption gate not satisfied.", "missing_requirements": missing}
    return {"action": "ADOPT", "reason": "Recorded baseline improved with no held-out regression."}


def route_change(
    paths: list[str],
    *,
    root: Path | None = None,
    protected_roots: Iterable[str] = (),
    train_improved: bool = False,
    held_out_regressions: int = 0,
    rollback_record: dict[str, Any] | None = None,
    run_cap: int | None = None,
    applied_in_run: int = 0,
    recurrence_confirmed: bool = False,
    critic_passed: bool = False,
) -> dict[str, Any]:
    """Return a non-mutating learning disposition.

    The authoritative protected-root set is read from T-7 for ``root``.
    ``protected_roots`` may add protection but cannot waive local config or
    immutable roots. Invalid path proof is a ``BLOCKED`` outcome, while a
    proven protected target remains a human-adopted ``PROPOSAL``.
    """
    if root is None:
        # Legacy callers cannot establish canonical containment or prove that
        # their protected-root policy came from T-7.  Keep their tier hint for
        # migration diagnostics, but never turn it into an edit authorization.
        tier = _legacy_tier_for(paths)
        if tier == "harness":
            return {"tier": tier, "action": "PROPOSAL", "reason": "Harness-tier changes require human adoption.", "automatic_edit": False}
        return {
            "tier": tier,
            "action": "PROPOSAL",
            "reason": "Trusted repository root and T-7 protected-root policy evidence are required for local routing.",
            "automatic_edit": False,
            "compatibility_mode": True,
        }

    try:
        protected_roots = _effective_protected_roots(Path(root), protected_roots)
        canonical = [canonical_path(Path(root), path) for path in paths]
    except EnforcementError as exc:
        return {
            "tier": "indeterminate", "action": "BLOCKED", "reason": str(exc),
            "automatic_edit": False, "canonical_paths": [],
        }
    if not canonical:
        return {"tier": "indeterminate", "action": "BLOCKED", "reason": "No target paths supplied.", "automatic_edit": False, "canonical_paths": []}
    if any(_is_protected(path, protected_roots) for path in canonical):
        return {
            "tier": "harness", "action": "PROPOSAL", "reason": "Protected harness-tier changes require human adoption.",
            "automatic_edit": False, "canonical_paths": canonical,
        }

    missing: list[str] = []
    if not train_improved:
        missing.append("train_improved")
    if held_out_regressions != 0:
        missing.append("held_out_zero_regressions")
    if not rollback_record:
        missing.append("rollback_record")
    if not isinstance(run_cap, int) or run_cap < 1:
        missing.append("run_cap")
    elif not isinstance(applied_in_run, int) or applied_in_run < 0 or applied_in_run >= run_cap:
        missing.append("run_cap_available")
    if not recurrence_confirmed:
        missing.append("recurrence_confirmed")
    if not critic_passed:
        missing.append("critic_passed")
    if missing:
        return {
            "tier": "project", "action": "PROPOSAL", "reason": "Project apply gate not satisfied.",
            "missing_requirements": missing, "automatic_edit": False, "canonical_paths": canonical,
        }
    return {
        "tier": "project", "action": "APPLY", "rollback_required": True, "rollback_record": deepcopy(rollback_record),
        "automatic_edit": False, "canonical_paths": canonical,
    }


def knowledge_sync_outcome(config: dict[str, Any]) -> dict[str, str]:
    sync = config.get("knowledge_sync", {}) if isinstance(config, dict) else {}
    return {"status": "READY" if sync.get("enabled") else "SKIPPED", "reason": "not configured" if not sync.get("enabled") else "configured"}
