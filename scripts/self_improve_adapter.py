#!/usr/bin/env python3
"""Explicit local CLI boundary for the learning core and T-7 policy."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness_core.learning import knowledge_sync_outcome, process, route_change
from scripts.adapter_render import rendered_json


def _canonical_input(root: Path, raw: Path, label: str) -> Path:
    """Resolve explicit adapter inputs from the canonical repository root."""
    candidate = raw if raw.is_absolute() else root / raw
    try:
        canonical = candidate.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"--{label} is unavailable: {exc}") from exc
    if not canonical.is_relative_to(root) or not canonical.is_file():
        raise ValueError(f"--{label} must be a regular file inside --repository-root")
    return canonical


def _load_json(path: Path, expected: type) -> object:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-standard JSON constant: {value}")

    def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=reject_constant,
            object_pairs_hook=reject_duplicate_keys,
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON from {path}: {exc}") from exc
    if not isinstance(value, expected):
        raise ValueError(f"{path} must contain a JSON {expected.__name__}")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Process local learning entries once under the T-7 policy.")
    parser.add_argument("--entries", type=Path, required=True)
    parser.add_argument("--cursor", type=int, default=0)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--paths", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--train-improved", action="store_true")
    parser.add_argument("--held-out-regressions", type=int, default=0)
    parser.add_argument("--rollback-record", help="durable rollback record identifier")
    parser.add_argument("--run-cap", type=int)
    parser.add_argument("--applied-count", type=int, default=0)
    parser.add_argument("--recurrence-confirmed", action="store_true")
    parser.add_argument("--critic-passed", action="store_true")
    parser.add_argument("--config", type=Path, help="defaults to <repository-root>/.harness/config.json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        root = args.repository_root.resolve(strict=True)
        if not root.is_dir():
            raise ValueError("--repository-root must be a directory")
        entries_path = _canonical_input(root, args.entries, "entries")
        paths_path = _canonical_input(root, args.paths, "paths")
        entries = _load_json(entries_path, list)
        paths = _load_json(paths_path, list)
        if not all(isinstance(path, str) for path in paths):
            raise ValueError("--paths must contain only strings")
        if args.config is not None:
            config_path = _canonical_input(root, args.config, "config")
            config = _load_json(config_path, dict)
        else:
            default_config = root / ".harness" / "config.json"
            if default_config.exists() or default_config.is_symlink():
                config_path = _canonical_input(root, default_config, "config")
                config = _load_json(config_path, dict)
            else:
                config_path = None
                config = {}
        rollback = {"id": args.rollback_record} if args.rollback_record else None
        change = route_change(
            paths, root=root, train_improved=args.train_improved,
            held_out_regressions=args.held_out_regressions, rollback_record=rollback,
            run_cap=args.run_cap, applied_in_run=args.applied_count,
            recurrence_confirmed=args.recurrence_confirmed, critic_passed=args.critic_passed,
        )
        result = {
            "status": "OK", "processed": process(entries, args.cursor, args.limit), "change": change,
            "knowledge_sync": knowledge_sync_outcome(config),
            "evidence": {
                "entries": str(entries_path), "cursor": args.cursor,
                "paths": str(paths_path),
                "config": str(config_path) if config_path is not None else None,
                "repository_root": str(root),
            },
        }
    except (OSError, ValueError, TypeError) as exc:
        print(rendered_json({"status": "BLOCKED", "reason": str(exc)}))
        return 2
    print(rendered_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
