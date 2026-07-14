"""Command-line entry points for deterministic harness checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .config import ConfigError, load_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="harness_core")
    subparsers = parser.add_subparsers(dest="command", required=True)
    doctor = subparsers.add_parser("doctor", help="inspect project-local harness configuration")
    doctor.add_argument("--config", type=Path, default=Path(".harness/config.json"))
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
    raise AssertionError(f"Unhandled command: {args.command}")

