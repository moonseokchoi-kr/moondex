#!/usr/bin/env python3
"""Explicit graph-command adapter with an honest local grep fallback."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness_core.code_mapper import HEALTHY, classify_probe, grep_fallback
from scripts.adapter_render import rendered_json


def _command(value: str) -> list[str]:
    command = json.loads(value)
    if not isinstance(command, list) or not command or not all(isinstance(part, str) for part in command):
        raise argparse.ArgumentTypeError("--graph-command must be a non-empty JSON string array")
    return command


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Map an impact using an explicit graph probe or grep fallback.")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--graph-command", type=_command, help="JSON command array; stdout is graph probe output")
    return parser


def _graph_impact(probe: str) -> tuple[dict[str, object], list[str]]:
    """Preserve only structured graph facts; never infer missing relationships."""
    try:
        payload = json.loads(probe)
    except json.JSONDecodeError:
        return (
            {"entry_points": [], "candidate_calls": [], "impact_scope": []},
            ["Graph probe was healthy but did not return structured impact JSON."],
        )
    if not isinstance(payload, dict):
        return (
            {"entry_points": [], "candidate_calls": [], "impact_scope": []},
            ["Graph probe JSON was not an object; no relationships were inferred."],
        )
    impact: dict[str, object] = {}
    limitations: list[str] = []
    for field in ("entry_points", "candidate_calls", "impact_scope"):
        value = payload.get(field, [])
        if isinstance(value, list):
            impact[field] = value
        else:
            impact[field] = []
            limitations.append(f"Graph field {field!r} was not a list and was omitted.")
    return impact, limitations


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    evidence: dict[str, object] = {}
    probe = ""
    if args.graph_command:
        try:
            completed = subprocess.run(args.graph_command, text=True, capture_output=True, check=False)
        except OSError as exc:
            evidence = {"command": args.graph_command, "error_type": type(exc).__name__, "error": str(exc)}
        else:
            evidence = {"command": args.graph_command, "returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}
            probe = completed.stdout if completed.returncode == 0 else ""
    state = classify_probe(probe)
    if state == HEALTHY:
        impact, limitations = _graph_impact(probe)
        print(rendered_json({"status": "OK", "mode": "graph", "graph_state": state, "symbol": args.symbol, "impact": impact, "limitations": limitations, "evidence": evidence}))
        return 0
    try:
        report = grep_fallback(args.root, args.symbol)
    except OSError as exc:
        print(rendered_json({"status": "BLOCKED", "reason": "graph unavailable and grep fallback could not run", "graph_state": state, "evidence": {**evidence, "fallback_error": str(exc)}}))
        return 2
    command_failed = args.graph_command and (evidence.get("returncode") or evidence.get("error_type"))
    reason = "graph command failed; approximate grep fallback cannot establish graph facts" if command_failed else "graph unavailable or not initialized; approximate grep fallback cannot establish graph facts"
    limitations = ["Grep matches are lexical candidates, not proven call relationships.", "No entry-point or call graph was available."]
    print(rendered_json({"status": "BLOCKED", "reason": reason, "graph_state": state, "fallback": report, "limitations": limitations, "evidence": evidence}))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
