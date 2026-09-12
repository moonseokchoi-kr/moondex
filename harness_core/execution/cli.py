"""Installed and development entry point for delegated execution."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    __package__ = "harness_core.execution"

from .contracts import ExecutionError, read_json
from .engine import Engine
from scripts.adapter_render import redact


def main(argv=None):
    p = argparse.ArgumentParser(prog="moondex execute")
    p.add_argument("--root", type=Path, default=Path("."))
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("prepare", "submit"):
        sub.add_parser(name).add_argument("--file", type=Path, required=True)
    a = sub.add_parser("approve")
    for key in ("digest", "quote", "source"):
        a.add_argument("--" + key, required=True)
    for name in ("status", "advance", "resume", "report"):
        sub.add_parser(name)
    f = sub.add_parser("feedback")
    f.add_argument("--kind", required=True, choices=("implementation", "verification", "plan", "baseline", "ambiguous"))
    f.add_argument("--nodes", nargs="*", default=[])
    f.add_argument("--reason", required=True)
    f.add_argument("--replacement", type=Path)
    a = sub.add_parser("answer")
    for key in ("question", "digest", "text", "source", "decision"):
        a.add_argument("--" + key, required=True)
    sub.add_parser("cancel").add_argument("--reason", required=True)
    args = p.parse_args(argv)
    engine = Engine(args.root)
    try:
        if args.command == "prepare":
            result = engine.prepare(read_json(args.file))
        elif args.command == "approve":
            result = engine.approve(args.digest, args.quote, args.source)
        elif args.command == "submit":
            result = engine.submit(read_json(args.file))
        elif args.command in {"advance", "resume"}:
            result = engine.advance()
        elif args.command in {"status", "report"}:
            state = engine.store.status()
            result = redact({"code": state.get("status", state.get("code")), "state": state})
        elif args.command == "feedback":
            result = engine.feedback(args.kind, args.nodes, args.reason, read_json(args.replacement) if args.replacement else None)
        elif args.command == "answer":
            result = engine.answer(args.question, args.digest, args.text, args.source, args.decision)
        else:
            result = engine.cancel(args.reason)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except ExecutionError as exc:
        print(json.dumps({"code": exc.code, "message": str(exc)}, ensure_ascii=False))
        return 2
    except (OSError, KeyError, TypeError) as exc:
        print(json.dumps({"code": "RECOVERY_REQUIRED", "message": type(exc).__name__}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
