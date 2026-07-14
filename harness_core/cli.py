"""Command-line entry points for deterministic harness checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .config import ConfigError, load_config
from .state import Phase, PreflightError, load_json, preflight_phase


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="harness_core")
    subparsers = parser.add_subparsers(dest="command", required=True)
    doctor = subparsers.add_parser("doctor", help="inspect project-local harness configuration")
    doctor.add_argument("--config", type=Path, default=Path(".harness/config.json"))
    preflight = subparsers.add_parser("preflight", help="run an explicit SDD preflight")
    preflight_subparsers = preflight.add_subparsers(dest="preflight_command", required=True)
    phase = preflight_subparsers.add_parser("phase", help="validate artifacts before entering a phase")
    phase.add_argument("--project-root", type=Path, default=Path("."))
    phase.add_argument("--state", type=Path, default=Path(".harness/state/pipeline.json"))
    phase.add_argument("--target-phase", choices=[phase.value for phase in Phase], required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "doctor":
        try:
            config = load_config(args.config)
        except ConfigError as exc:
            print(f"CONFIG_INVALID: {exc}")
            return 2
        print(json.dumps({"status": "OK", "config": config}, sort_keys=True))
        return 0
    if args.command == "preflight" and args.preflight_command == "phase":
        state_path = args.project_root / args.state
        state = load_json(state_path)
        if state is None:
            print(f"PREFLIGHT_FAILED: state not found or invalid JSON: {state_path}")
            return 2
        try:
            target_phase = Phase(args.target_phase)
            preflight_phase(args.project_root, state, target_phase)
        except PreflightError as exc:
            print(f"PREFLIGHT_FAILED: {exc}")
            return 2
        print(f"PREFLIGHT_OK: {target_phase.value}")
        return 0
    raise AssertionError(f"Unhandled command: {args.command}")
