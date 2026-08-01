#!/usr/bin/env python3
"""Explicit opt-in boundary for evaluations that call an LLM or live service."""

from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a live evaluation (never part of offline pytest).")
    parser.add_argument("--confirm-live", action="store_true", help="acknowledge that this may call external services")
    args = parser.parse_args()
    if not args.confirm_live:
        parser.error("live evaluation is opt-in; rerun with --confirm-live")
    print("LIVE_EVAL_READY: provide a configured evaluator adapter to execute external checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
