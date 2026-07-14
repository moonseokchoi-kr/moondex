#!/usr/bin/env python3
"""Project-local validation used by local hooks and CI."""
from __future__ import annotations
import argparse, re
from pathlib import Path

SECRET = re.compile(r"(?i)(api[_-]?key|secret|token)\s*[=:]\s*['\"][A-Za-z0-9_\-]{8,}")

def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("paths", nargs="*"); args = parser.parse_args()
    for name in args.paths:
        path = Path(name)
        if path.suffix in {".tsx", ".jsx", ".css"} and not Path(".harness/state/e2e-config.json").is_file():
            print("VERIFY_FAILED: UI change requires .harness/state/e2e-config.json evidence."); return 2
        if path.is_file() and SECRET.search(path.read_text(encoding="utf-8", errors="replace")):
            print(f"VERIFY_FAILED: possible secret in {path}; remove it or use an approved secret reference."); return 2
    print("VERIFY_OK"); return 0
if __name__ == "__main__": raise SystemExit(main())
