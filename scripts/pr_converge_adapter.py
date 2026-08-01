#!/usr/bin/env python3
"""Local CLI boundary for deterministic review disposition and convergence."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness_core.pr import (
    convergence_state,
    load_audit,
    revision_key,
    run_local_review,
    strict_json_loads,
)
from scripts.adapter_render import redact, rendered_json, write_rendered_json


def _canonical_input(root: Path, raw: Path, label: str) -> Path:
    """Resolve one adapter input against the trusted repository root."""
    candidate = raw if raw.is_absolute() else root / raw
    try:
        canonical = candidate.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"--{label} is unavailable: {exc}") from exc
    if not canonical.is_relative_to(root) or not canonical.is_file():
        raise ValueError(f"--{label} must be a regular file inside --repository-root")
    return canonical


def _canonical_output(
    root: Path, raw: Path, label: str, required_root: Path, *, disallow_alias: Path | None = None,
) -> Path:
    """Resolve an output before any write and prove its physical containment."""
    candidate = raw if raw.is_absolute() else root / raw
    try:
        canonical = candidate.resolve(strict=False)
        canonical_required_root = required_root.resolve(strict=False)
    except OSError as exc:
        raise ValueError(f"--{label} cannot be canonicalized: {exc}") from exc
    if disallow_alias is not None and (
        canonical == disallow_alias or _same_existing_file(canonical, disallow_alias)
    ):
        raise ValueError(f"--{label} must not resolve to the same file or inode as --audit")
    if not canonical_required_root.is_relative_to(root):
        raise ValueError(f"--{label} root resolves outside --repository-root")
    if canonical_required_root != required_root.absolute():
        raise ValueError(f"--{label} root must not be a symlink alias")
    if not canonical.is_relative_to(canonical_required_root):
        raise ValueError(f"--{label} must be inside {required_root.relative_to(root).as_posix()}/")
    if canonical.exists() and not canonical.is_file():
        raise ValueError(f"--{label} must name a regular file")
    return canonical


def _same_existing_file(first: Path, second: Path) -> bool:
    try:
        return first.exists() and second.exists() and os.path.samefile(first, second)
    except OSError as exc:
        raise ValueError(f"cannot verify output path identity: {exc}") from exc


def _validate_distinct_paths(
    collection: Path, evidence: Path, resolutions: Path | None, audit: Path, report: Path | None,
) -> None:
    """Prevent an append or rendered export from aliasing raw/input evidence."""
    inputs = [(collection, "collection"), (evidence, "evidence")]
    if resolutions is not None:
        inputs.append((resolutions, "resolutions"))
    for input_path, label in inputs:
        if audit == input_path or _same_existing_file(audit, input_path):
            raise ValueError(f"--audit must not alias --{label}")
    if report is None:
        return
    if audit == report or _same_existing_file(audit, report):
        raise ValueError("--audit and --report must not resolve to the same file or inode")
    for input_path, label in inputs:
        if report == input_path or _same_existing_file(report, input_path):
            raise ValueError(f"--report must not alias --{label}")


def _json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = strict_json_loads(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read strict {label} JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _command(value: str) -> list[str]:
    try:
        command = strict_json_loads(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"command must be strict JSON: {exc}") from exc
    if not isinstance(command, list) or not command or not all(isinstance(part, str) and part for part in command):
        raise argparse.ArgumentTypeError("command must be a non-empty JSON string array")
    return command


def _render_dispositions(snapshot: dict[str, Any], audit_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Render the latest audited disposition for every revision in this pass.

    ``run_local_review`` deliberately returns only newly recorded events.  A
    resumed identical collection has no fresh events, but its terminal audit
    records are still the authoritative local result and must remain visible.
    """
    latest = {
        event.get("revision_key"): event
        for event in audit_events
        if event.get("event_type") in {"disposition", "escalation_resolution"}
    }
    rendered: list[dict[str, Any]] = []
    for comment in snapshot["comments"]:
        event = latest.get(revision_key(comment))
        if event is None:
            continue
        rendered.append({
            "source_identity": event["source_identity"],
            "revision_identity": event["revision_identity"],
            "decision": event["decision"],
            "alignment": redact(event.get("alignment", {})),
            "reason": redact(event["reason"]),
            "alternative": redact(event.get("alternative")),
            "evidence": redact(event.get("evidence", [])),
            "fix": redact(event.get("fix", {})),
        })
    return rendered


def _run_command(name: str, command: list[str] | None, root: Path) -> tuple[bool, dict[str, Any]]:
    if command is None:
        return False, {"name": name, "configured": False, "passed": False, "reason": "command is not configured"}
    try:
        completed = subprocess.run(command, cwd=root, text=True, capture_output=True, check=False)
    except OSError as exc:
        return False, {"name": name, "configured": True, "passed": False, "command": command, "error": str(exc)}
    evidence = {
        "name": name, "configured": True, "passed": completed.returncode == 0,
        "command": command, "returncode": completed.returncode,
        "stdout": completed.stdout, "stderr": completed.stderr,
    }
    return completed.returncode == 0, redact(evidence)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record one complete local review collection and evaluate convergence.")
    parser.add_argument("--collection", type=Path, required=True, help="strict complete T-4 collection JSON")
    parser.add_argument("--evidence", type=Path, required=True, help="strict JSON object keyed by revision key")
    parser.add_argument("--resolutions", type=Path, help="optional strict immutable escalation-resolution collection")
    parser.add_argument("--audit", type=Path, required=True, help="local append-only JSONL audit path")
    parser.add_argument("--report", type=Path, help="optional redacted report below .harness/reports/")
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--build-command", type=_command)
    parser.add_argument("--lint-command", type=_command)
    parser.add_argument("--test-command", type=_command)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        root = args.repository_root.resolve(strict=True)
        if not root.is_dir():
            raise ValueError("--repository-root must be a directory")
        collection_path = _canonical_input(root, args.collection, "collection")
        evidence_path = _canonical_input(root, args.evidence, "evidence")
        resolutions_path = (
            _canonical_input(root, args.resolutions, "resolutions")
            if args.resolutions is not None else None
        )
        audit_path = _canonical_output(root, args.audit, "audit", root / ".harness" / "audit")
        report_path = (
            _canonical_output(
                root, args.report, "report", root / ".harness" / "reports",
                disallow_alias=audit_path,
            )
            if args.report is not None else None
        )
        _validate_distinct_paths(collection_path, evidence_path, resolutions_path, audit_path, report_path)
        raw_collection = collection_path.read_bytes()
        evidence = _json_object(evidence_path, "evidence")
        raw_resolutions = resolutions_path.read_bytes() if resolutions_path is not None else None
        review = run_local_review(
            raw_collection, evidence, audit_path, repository_root=root,
            raw_resolutions=raw_resolutions,
        )
        if review["status"] == "BLOCKED":
            print(rendered_json({"status": "BLOCKED", "reason": review["reason"], "audit": str(audit_path), "evidence": {"collection": str(collection_path)}}))
            return 2
        commands: dict[str, bool] = {}
        command_evidence: list[dict[str, Any]] = []
        for name, command in (("build", args.build_command), ("lint", args.lint_command), ("test", args.test_command)):
            passed, item = _run_command(name, command, root)
            commands[name] = passed
            command_evidence.append(item)
        audit_events = load_audit(audit_path)
        convergence = convergence_state(review["snapshot"], audit_events, commands, repository_root=root)
        rendered = _render_dispositions(review["snapshot"], audit_events)
        payload = {
            "status": convergence["status"], "reason": convergence["reason"], "audit": str(audit_path),
            "snapshot_id": review["snapshot"]["snapshot_id"], "dispositions": rendered,
            "local_commands": command_evidence,
            "evidence": {
                "collection": str(collection_path),
                "resolutions": str(resolutions_path) if resolutions_path is not None else None,
                "repository_root": str(root),
            },
        }
        if report_path is not None:
            write_rendered_json(report_path, payload)
            payload["report"] = str(report_path)
        print(rendered_json(payload))
        return 0 if convergence["status"] == "CONVERGED" else 2 if convergence["status"] == "BLOCKED" else 0
    except (OSError, ValueError) as exc:
        print(rendered_json({"status": "BLOCKED", "reason": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
