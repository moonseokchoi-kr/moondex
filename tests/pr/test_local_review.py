from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from harness_core.pr import (
    AuditWriteError,
    AuditWriter,
    StrictInputError,
    classify_disposition,
    convergence_state,
    load_audit,
    new_revisions,
    parse_collection,
    parse_resolution_collection,
    revision_key,
    run_local_review,
    strict_json_loads,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _comment(*, revision: str = "r1", body: str = "Fix this") -> dict[str, object]:
    return {
        "schema_version": 1, "source": "conversation", "source_identity": "local/conversation/1",
        "comment_id": 1, "revision_identity": revision,
        "body_hash": hashlib.sha256(body.encode()).hexdigest(), "author": "reviewer", "body": body,
        "created_at": "2026-07-19T10:00:00Z",
    }


def _collection(comment: dict[str, object]) -> str:
    return json.dumps({"schema_version": 1, "input_identity": "fixture", "complete": True, "comments": [comment]})


def _safe_evidence() -> dict[str, object]:
    return {
        "alignment": {"spec": "ALIGNS", "design": "ALIGNS", "ownership": "OWNED", "verification": "AVAILABLE"},
        "validation_plan": ["python3 -m pytest tests/pr -q"],
        "changed_files": ["harness_core/pr/__init__.py"],
        "repository_root": str(PROJECT_ROOT),
        "validation": [{"command": "python3 -m pytest tests/pr -q", "passed": True}],
        "evidence": [{"kind": "spec", "ref": "docs/sdd/spec.md#F5"}],
    }


@pytest.mark.parametrize("raw", [
    '{"x": 1, "x": 2}', '{"x": NaN}', '{"x": Infinity}', '{"x": 1} trailing',
])
def test_strict_json_rejects_permissive_forms(raw: str) -> None:
    with pytest.raises(StrictInputError):
        strict_json_loads(raw)


def test_strict_json_accepts_rfc8259_whitespace_but_not_date_only_timestamps() -> None:
    assert strict_json_loads(" \t\r\n {\"x\": 1} \n") == {"x": 1}
    comment = _comment()
    comment["created_at"] = "2026-07-19"
    with pytest.raises(StrictInputError):
        parse_collection(_collection(comment))


@pytest.mark.parametrize("field,value", [("comment_id", 1.5), ("comment_id", True), ("line", 0), ("line", 1.5)])
def test_collection_rejects_unsafe_ids_and_lines(field: str, value: object) -> None:
    comment = _comment()
    comment[field] = value
    if field == "line": comment["path"] = "src/app.py"
    with pytest.raises(StrictInputError):
        parse_collection(_collection(comment))


def test_snapshot_lifecycle_redisposes_edited_or_reopened_comment(tmp_path: Path) -> None:
    audit = tmp_path / "audit.jsonl"
    first = parse_collection(_collection(_comment()))
    first_key = revision_key(first["comments"][0])
    assert run_local_review(_collection(_comment()), {first_key: _safe_evidence()}, audit, repository_root=PROJECT_ROOT)["status"] == "RECORDED"
    assert new_revisions(first, load_audit(audit)) == []

    edited = parse_collection(_collection(_comment(revision="r2", body="Fix this differently")))
    assert len(new_revisions(edited, load_audit(audit))) == 1


def test_revision_key_is_typed_and_collision_free() -> None:
    first = _comment()
    first.update({"source_identity": "a:b", "revision_identity": "c", "comment_id": 1})
    second = _comment()
    second.update({"source_identity": "a", "revision_identity": "b:c", "comment_id": 1})
    assert revision_key(first).startswith("rk1:")
    assert revision_key(first) != revision_key(second)

    string_id = {**first, "comment_id": "1"}
    assert revision_key(first) != revision_key(string_id)

    duplicate = json.dumps({
        "schema_version": 1, "input_identity": "fixture", "complete": True,
        "comments": [first, dict(first)],
    })
    with pytest.raises(StrictInputError, match="source_identity must occur once"):
        parse_collection(duplicate)


def test_collection_rejects_duplicate_derived_keys_even_for_distinct_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _comment()
    second = _comment()
    second["source_identity"] = "local/conversation/2"
    monkeypatch.setattr("harness_core.pr.revision_key", lambda _comment: "rk1:forced-collision")
    raw = json.dumps({
        "schema_version": 1, "input_identity": "fixture", "complete": True,
        "comments": [first, second],
    })
    with pytest.raises(StrictInputError, match="derived revision key must occur once"):
        parse_collection(raw)


def test_colon_collision_revisions_resolve_independently(tmp_path: Path) -> None:
    first = _comment()
    first.update({"source_identity": "a:b", "revision_identity": "c", "comment_id": 1})
    second = _comment()
    second.update({"source_identity": "a", "revision_identity": "b:c", "comment_id": 2})
    raw = json.dumps({
        "schema_version": 1, "input_identity": "collision-fixture", "complete": True,
        "comments": [first, second],
    })
    snapshot = parse_collection(raw)
    keys = [revision_key(comment) for comment in snapshot["comments"]]
    assert len(set(keys)) == 2
    audit = tmp_path / "audit.jsonl"
    outcome = run_local_review(
        raw, {key: {"alignment": {"spec": "UNKNOWN"}} for key in keys}, audit
    )
    assert outcome["status"] == "RECORDED"
    assert {event["revision_key"] for event in outcome["events"]} == set(keys)

    def rejected(comment: dict[str, object]) -> dict[str, object]:
        return {
            "schema_version": 1,
            "source_identity": comment["source_identity"],
            "revision_identity": comment["revision_identity"],
            "body_hash": comment["body_hash"],
            "comment_id": comment["comment_id"],
            "authority": "USER",
            "decision": "REJECTED",
            "reason": "The user rejected this exact revision.",
            "alternative": "Keep the approved behavior.",
            "evidence": [{"kind": "user_decision", "ref": comment["source_identity"]}],
        }

    one = json.dumps({
        "schema_version": 1, "complete": True, "resolutions": [rejected(first)]
    })
    assert run_local_review(raw, {}, audit, raw_resolutions=one)["status"] == "RECORDED"
    assert convergence_state(snapshot, load_audit(audit), {"test": True})["status"] == "NEEDS_HUMAN"

    two = json.dumps({
        "schema_version": 1, "complete": True, "resolutions": [rejected(second)]
    })
    assert run_local_review(raw, {}, audit, raw_resolutions=two)["status"] == "RECORDED"
    assert convergence_state(snapshot, load_audit(audit), {"test": True})["status"] == "CONVERGED"


def test_unambiguous_legacy_current_run_escalation_can_be_resolved(tmp_path: Path) -> None:
    raw = _collection(_comment())
    snapshot = parse_collection(raw)
    comment = snapshot["comments"][0]
    legacy = classify_disposition(comment, {"alignment": {"spec": "UNKNOWN"}})
    legacy["revision_key"] = ":".join((
        comment["source_identity"], comment["revision_identity"], comment["body_hash"]
    ))
    for field in ("revision_key_version", "body_hash", "comment_id"):
        legacy.pop(field, None)
    audit = tmp_path / "audit.jsonl"
    AuditWriter(audit).append(legacy)
    resolution = json.dumps({
        "schema_version": 1,
        "complete": True,
        "resolutions": [{
            "schema_version": 1,
            "source_identity": comment["source_identity"],
            "revision_identity": comment["revision_identity"],
            "body_hash": comment["body_hash"],
            "comment_id": comment["comment_id"],
            "authority": "USER",
            "decision": "REJECTED",
            "reason": "The user rejected the exact legacy-audited revision.",
            "alternative": "Keep the current behavior.",
            "evidence": [{"kind": "user_decision", "ref": "local"}],
        }],
    })
    result = run_local_review(raw, {}, audit, raw_resolutions=resolution)
    assert result["status"] == "RECORDED"
    assert result["events"][-1]["revision_key"] == revision_key(comment)
    assert convergence_state(snapshot, load_audit(audit), {"test": True})["status"] == "CONVERGED"


def test_conflicting_audit_identity_fails_before_append(tmp_path: Path) -> None:
    raw = _collection(_comment())
    snapshot = parse_collection(raw)
    comment = snapshot["comments"][0]
    escalated = classify_disposition(comment, {"alignment": {"spec": "UNKNOWN"}})
    conflicting = {**escalated, "decision": "REJECTED", "reason": "forged conflict"}
    audit = tmp_path / "audit.jsonl"
    AuditWriter(audit).write_events([escalated, conflicting])
    before = audit.read_bytes()
    result = run_local_review(raw, {}, audit)
    assert result["status"] == "BLOCKED"
    assert "duplicate disposition identity" in result["reason"]
    assert audit.read_bytes() == before


def test_complete_offline_fixture_is_strictly_valid() -> None:
    fixture = Path("tests/fixtures/pr/complete-safe-fix.json").read_text(encoding="utf-8")
    assert parse_collection(fixture)["complete"] is True


def test_disposition_is_evidence_based_and_escalates_unknown_or_llm_only() -> None:
    comment = parse_collection(_collection(_comment()))["comments"][0]
    assert classify_disposition(comment, _safe_evidence(), repository_root=PROJECT_ROOT)["decision"] == "SAFE_FIX"
    assert classify_disposition(comment, {"alignment": {"spec": "UNKNOWN"}})["decision"] == "ESCALATED"
    assert classify_disposition(comment, {**_safe_evidence(), "llm_only": True}, repository_root=PROJECT_ROOT)["decision"] == "ESCALATED"
    rejected = classify_disposition(comment, {
        "alignment": {"spec": "CONFLICTS", "design": "ALIGNS", "ownership": "OWNED", "verification": "AVAILABLE"},
        "reason": "Conflicts with F5.", "alternative": "Escalate a spec change.",
    })
    assert rejected["decision"] == "REJECTED"


def test_safe_fix_requires_trusted_root_and_existing_regular_changed_files() -> None:
    comment = parse_collection(_collection(_comment()))["comments"][0]
    # A path can be syntactically concrete while resolving to an existing
    # directory; it is never sufficient evidence of a completed file change.
    directory_evidence = {**_safe_evidence(), "changed_files": ["harness_core"]}
    assert classify_disposition(comment, directory_evidence, repository_root=PROJECT_ROOT)["decision"] == "ESCALATED"
    assert classify_disposition(comment, _safe_evidence())["decision"] == "ESCALATED"
    assert classify_disposition(
        comment, {**_safe_evidence(), "repository_root": str(PROJECT_ROOT / "different")},
        repository_root=PROJECT_ROOT,
    )["decision"] == "ESCALATED"
    # The fixture's real module file establishes the positive control.
    assert classify_disposition(comment, _safe_evidence(), repository_root=PROJECT_ROOT)["decision"] == "SAFE_FIX"


@pytest.mark.parametrize("override", [
    {"changed_files": []},
    {"validation": []},
    {"validation": [{"command": "python3 -m pytest tests/pr -q", "passed": False}]},
    {"changed_files": ["../outside.py"]},
    {"changed_files": ["."]},
    {"changed_files": [""]},
    {"changed_files": ["/outside.py"]},
    {"changed_files": ["harness_core/"]},
])
def test_safe_fix_requires_recorded_changes_and_completed_passing_validation(override: dict[str, object]) -> None:
    comment = parse_collection(_collection(_comment()))["comments"][0]
    evidence = {**_safe_evidence(), **override}
    assert classify_disposition(comment, evidence, repository_root=PROJECT_ROOT)["decision"] == "ESCALATED"


def test_atomic_audit_lock_failure_fails_closed(tmp_path: Path) -> None:
    audit = tmp_path / "audit.jsonl"
    writer = AuditWriter(audit)
    writer.lock_path.write_text("another-writer", encoding="ascii")
    with pytest.raises(AuditWriteError):
        writer.append({"event_type": "disposition"})
    result = run_local_review(_collection(_comment()), {}, audit)
    assert result == {"status": "BLOCKED", "reason": "concurrent writer or lock loss", "code": "AUDIT_WRITE_FAILED"}


def test_audit_io_failure_fails_closed(tmp_path: Path) -> None:
    not_a_directory = tmp_path / "not-a-directory"
    not_a_directory.write_text("x", encoding="utf-8")
    result = run_local_review(_collection(_comment()), {}, not_a_directory / "audit.jsonl")
    assert result["status"] == "BLOCKED"
    assert result["code"] == "AUDIT_WRITE_FAILED"


def test_run_records_snapshot_before_disposition_and_converges_locally(tmp_path: Path) -> None:
    audit = tmp_path / "audit.jsonl"
    snapshot = parse_collection(_collection(_comment()))
    key = revision_key(snapshot["comments"][0])
    outcome = run_local_review(_collection(_comment()), {key: _safe_evidence()}, audit, repository_root=PROJECT_ROOT)
    assert outcome["status"] == "RECORDED"
    events = load_audit(audit)
    assert [event["event_type"] for event in events] == ["collection_snapshot", "disposition"]
    assert convergence_state(snapshot, events, {"build": True, "lint": True, "test": True}, repository_root=PROJECT_ROOT)["status"] == "CONVERGED"
    assert convergence_state(snapshot, events, {"build": True, "lint": False, "test": True}, repository_root=PROJECT_ROOT)["status"] == "WORKING"


def test_convergence_rejects_safe_fix_without_persisted_completion_evidence(tmp_path: Path) -> None:
    audit = tmp_path / "audit.jsonl"
    snapshot = parse_collection(_collection(_comment()))
    key = revision_key(snapshot["comments"][0])
    run_local_review(_collection(_comment()), {key: _safe_evidence()}, audit, repository_root=PROJECT_ROOT)
    events = load_audit(audit)
    events[-1]["fix"] = {"changed_files": [], "validation": []}
    result = convergence_state(snapshot, events, {"build": True, "lint": True, "test": True}, repository_root=PROJECT_ROOT)
    assert result["status"] == "BLOCKED"


def test_convergence_rejects_persisted_repository_root_as_safe_fix_evidence(tmp_path: Path) -> None:
    audit = tmp_path / "audit.jsonl"
    snapshot = parse_collection(_collection(_comment()))
    key = revision_key(snapshot["comments"][0])
    run_local_review(_collection(_comment()), {key: _safe_evidence()}, audit, repository_root=PROJECT_ROOT)
    events = load_audit(audit)
    events[-1]["fix"]["changed_files"] = ["."]
    result = convergence_state(snapshot, events, {"build": True, "lint": True, "test": True}, repository_root=PROJECT_ROOT)
    assert result["status"] == "BLOCKED"


def test_convergence_rechecks_persisted_changed_file_is_not_a_directory(tmp_path: Path) -> None:
    audit = tmp_path / "audit.jsonl"
    snapshot = parse_collection(_collection(_comment()))
    key = revision_key(snapshot["comments"][0])
    run_local_review(_collection(_comment()), {key: _safe_evidence()}, audit, repository_root=PROJECT_ROOT)
    events = load_audit(audit)
    events[-1]["fix"]["changed_files"] = ["harness_core"]
    result = convergence_state(snapshot, events, {"build": True, "lint": True, "test": True}, repository_root=PROJECT_ROOT)
    assert result["status"] == "BLOCKED"


def test_convergence_does_not_trust_root_embedded_in_safe_fix_event(tmp_path: Path) -> None:
    audit = tmp_path / "audit.jsonl"
    snapshot = parse_collection(_collection(_comment()))
    key = revision_key(snapshot["comments"][0])
    run_local_review(_collection(_comment()), {key: _safe_evidence()}, audit, repository_root=PROJECT_ROOT)
    events = load_audit(audit)

    assert convergence_state(snapshot, events, {"build": True, "lint": True, "test": True})["status"] == "BLOCKED"

    events[-1]["fix"]["repository_root"] = str(tmp_path.resolve())
    forged = convergence_state(
        snapshot, events, {"build": True, "lint": True, "test": True}, repository_root=PROJECT_ROOT
    )
    assert forged["status"] == "BLOCKED"


def test_escalation_blocks_convergence_and_bad_input_never_writes(tmp_path: Path) -> None:
    audit = tmp_path / "audit.jsonl"
    snapshot = parse_collection(_collection(_comment()))
    key = revision_key(snapshot["comments"][0])
    run_local_review(_collection(_comment()), {key: {"alignment": {"spec": "UNKNOWN"}}}, audit)
    assert convergence_state(snapshot, load_audit(audit), {"test": True})["status"] == "NEEDS_HUMAN"
    result = run_local_review('{"schema_version": 1, "schema_version": 1}', {}, audit)
    assert result["status"] == "BLOCKED" and result["code"] == "INVALID_INPUT"


def test_resolution_collection_rejects_conflicting_duplicate_identity() -> None:
    comment = _comment()
    base = {
        "schema_version": 1,
        "source_identity": comment["source_identity"],
        "revision_identity": comment["revision_identity"],
        "body_hash": comment["body_hash"],
        "comment_id": comment["comment_id"],
        "authority": "USER",
        "decision": "REJECTED",
        "reason": "Conflicts with the approved requirement.",
        "alternative": "Revise the requirement first.",
        "evidence": [{"kind": "spec", "ref": "F5"}],
    }
    raw = json.dumps({
        "schema_version": 1,
        "complete": True,
        "resolutions": [base, {**base, "reason": "A conflicting second answer."}],
    })
    with pytest.raises(StrictInputError, match="duplicate conflicting resolution"):
        parse_resolution_collection(raw)


def test_matching_user_rejection_resolves_same_revision_append_only(tmp_path: Path) -> None:
    audit = tmp_path / "audit.jsonl"
    comment = _comment()
    snapshot = parse_collection(_collection(comment))
    key = revision_key(snapshot["comments"][0])
    run_local_review(_collection(comment), {key: {"alignment": {"spec": "UNKNOWN"}}}, audit)
    resolution = {
        "schema_version": 1,
        "complete": True,
        "resolutions": [{
            "schema_version": 1,
            "source_identity": comment["source_identity"],
            "revision_identity": comment["revision_identity"],
            "body_hash": comment["body_hash"],
            "comment_id": comment["comment_id"],
            "authority": "USER",
            "decision": "REJECTED",
            "reason": "The request conflicts with the approved local contract.",
            "alternative": "Propose a requirements revision.",
            "evidence": [{"kind": "spec", "ref": "F5"}],
        }],
    }
    outcome = run_local_review(
        _collection(comment), {}, audit, raw_resolutions=json.dumps(resolution)
    )
    assert outcome["status"] == "RECORDED"
    events = load_audit(audit)
    assert events[-1]["event_type"] == "escalation_resolution"
    assert events[-1]["revision_key"] == key
    assert events[-1]["decision"] == "REJECTED"
    assert convergence_state(snapshot, events, {"test": True})["status"] == "CONVERGED"


def test_mismatched_or_unjustified_resolution_fails_without_audit_append(tmp_path: Path) -> None:
    audit = tmp_path / "audit.jsonl"
    comment = _comment()
    snapshot = parse_collection(_collection(comment))
    key = revision_key(snapshot["comments"][0])
    run_local_review(_collection(comment), {key: {"alignment": {"spec": "UNKNOWN"}}}, audit)
    base = {
        "schema_version": 1,
        "source_identity": comment["source_identity"],
        "revision_identity": comment["revision_identity"],
        "body_hash": comment["body_hash"],
        "comment_id": comment["comment_id"],
        "authority": "USER",
        "decision": "SAFE_FIX",
        "reason": "User selected a fix.",
        "evidence": [{"kind": "user_decision", "ref": "local"}],
        "fix": {"repository_root": str(PROJECT_ROOT), "changed_files": [], "validation": []},
    }
    for resolution in (
        {**base, "source_identity": "wrong"},
        {**base, "comment_id": str(comment["comment_id"])},
        base,
    ):
        before = audit.read_bytes()
        result = run_local_review(
            _collection(comment), {}, audit,
            raw_resolutions=json.dumps({
                "schema_version": 1, "complete": True, "resolutions": [resolution]
            }),
            repository_root=PROJECT_ROOT,
        )
        assert result["status"] == "BLOCKED"
        assert audit.read_bytes() == before
