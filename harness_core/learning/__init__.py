"""Deterministic learning routing with a project/harness safety boundary."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def process(entries: list[dict[str, Any]], cursor: int = 0, limit: int = 5) -> dict[str, Any]:
    """Process each append-only learning entry once and return a new cursor."""
    if cursor < 0 or limit < 1:
        raise ValueError("cursor must be non-negative and limit must be positive")
    selected = entries[cursor : cursor + limit]
    accepted = [deepcopy(entry) for entry in selected if isinstance(entry, dict)]
    return {"entries": accepted, "next_cursor": cursor + len(selected)}


def tier_for(paths: list[str]) -> str:
    """Harness source and public workflow files require a proposal, never auto-edit."""
    protected = ("harness_core/", "skills/", "agents/", ".codex-plugin/", "hooks/")
    return "harness" if any(path.startswith(protected) for path in paths) else "project"


def route_change(paths: list[str], *, train_improved: bool = False, held_out_regressions: int = 0) -> dict[str, Any]:
    tier = tier_for(paths)
    if tier == "harness":
        return {"tier": tier, "action": "PROPOSAL", "reason": "Harness-tier changes require human adoption."}
    if train_improved and held_out_regressions == 0:
        return {"tier": tier, "action": "APPLY", "rollback_required": True}
    return {"tier": tier, "action": "PROPOSAL", "reason": "Benchmark gate not satisfied."}


def knowledge_sync_outcome(config: dict[str, Any]) -> dict[str, str]:
    sync = config.get("knowledge_sync", {}) if isinstance(config, dict) else {}
    return {"status": "READY" if sync.get("enabled") else "SKIPPED", "reason": "not configured" if not sync.get("enabled") else "configured"}
