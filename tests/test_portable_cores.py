from pathlib import Path

from harness_core.code_mapper import HEALTHY, NOT_INITIALIZED, UNAVAILABLE, classify_probe, grep_fallback
from harness_core.learning import knowledge_sync_outcome, process, route_change
from harness_core.pr import normalize_comments, transition


def test_learning_cursor_and_tier_safety() -> None:
    assert process([{"a": 1}, {"b": 2}], 1)["next_cursor"] == 2
    assert route_change(["harness_core/state/pipeline.py"], train_improved=True)["action"] == "PROPOSAL"
    # Without a trusted repository root, compatibility routing cannot prove
    # canonical containment or the current protected-root policy.
    assert route_change(["app.py"], train_improved=True)["action"] == "PROPOSAL"
    assert knowledge_sync_outcome({})["status"] == "SKIPPED"


def test_pr_dedup_convergence_and_escalation() -> None:
    comments = normalize_comments({"conversation": [{"id": 1}], "inline": [{"id": 1}], "review": [{"id": 2}]})
    assert len(comments) == 2
    assert transition({}, [])["status"] == "CONVERGED"
    assert transition({}, [{"kind": "comment_escalate"}])["status"] == "NEEDS_HUMAN"


def test_mapper_three_states_and_explicit_fallback(tmp_path: Path) -> None:
    assert [classify_probe(value) for value in ("nodes: 4", "not initialized", "")] == [HEALTHY, NOT_INITIALIZED, UNAVAILABLE]
    (tmp_path / "app.py").write_text("def target(): pass\ntarget()\n", encoding="utf-8")
    report = grep_fallback(tmp_path, "target")
    assert report["approximate"] is True and len(report["matches"]) == 2
