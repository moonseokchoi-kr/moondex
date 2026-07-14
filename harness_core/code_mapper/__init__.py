"""Code graph probing with explicit approximate grep fallback."""

from __future__ import annotations

import re
from pathlib import Path

HEALTHY = "healthy"; NOT_INITIALIZED = "not_initialized"; UNAVAILABLE = "unavailable"


def classify_probe(text: object) -> str:
    if not isinstance(text, str) or not text.strip(): return UNAVAILABLE
    if re.search(r"not\s+initiali[sz]ed|\buninitiali[sz]ed\b", text, re.I): return NOT_INITIALIZED
    if re.search(r"\bnodes?\b|\bedges?\b|\bready\b", text, re.I): return HEALTHY
    return UNAVAILABLE


def grep_fallback(root: Path, symbol: str) -> dict[str, object]:
    matches = []
    pattern = re.compile(r"\b" + re.escape(symbol) + r"\b")
    for path in root.rglob("*"):
        if path.is_file() and path.suffix in {".py", ".ts", ".tsx", ".js", ".jsx"}:
            for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if pattern.search(line): matches.append({"path": str(path.relative_to(root)), "line": number})
    return {"mode": "grep_fallback", "approximate": True, "symbol": symbol, "matches": matches}
