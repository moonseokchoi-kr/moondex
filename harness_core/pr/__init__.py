"""Pure PR signal normalization, convergence, and circuit-breaker decisions."""

from __future__ import annotations

from typing import Any

MAX_ITERATIONS = 15
MAX_ATTEMPTS = 3


def normalize_comments(groups: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    seen: set[str] = set(); result = []
    for kind in ("conversation", "inline", "review"):
        for comment in groups.get(kind, []):
            key = str(comment.get("id", ""))
            if key and key not in seen:
                seen.add(key); result.append({**comment, "source": kind})
    return result


def transition(state: dict[str, Any], signals: list[dict[str, Any]]) -> dict[str, Any]:
    attempts = state.get("fix_attempts", {})
    if state.get("iterations", 0) >= MAX_ITERATIONS or any(count >= MAX_ATTEMPTS for count in attempts.values()):
        return {"status": "BLOCKED", "reason": "Circuit breaker limit reached."}
    kinds = {signal.get("kind") for signal in signals if isinstance(signal, dict)}
    if "comment_escalate" in kinds or state.get("escalations"):
        return {"status": "NEEDS_HUMAN", "reason": "Unresolved design/question signal."}
    if kinds & {"ci_fail", "lint_fail", "build_fail", "comment_actionable"}:
        return {"status": "WORKING", "reason": "Actionable signal remains."}
    if "ci_pending" in kinds:
        return {"status": "WAITING", "reason": "CI is pending."}
    return {"status": "CONVERGED", "reason": "CI green and no actionable or escalated signal."}
