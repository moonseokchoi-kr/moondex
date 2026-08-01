import hashlib
import json
import sys
from pathlib import Path
from subprocess import run

from harness_core.pr import revision_key


ROOT = Path(__file__).parents[1]


def invoke(script: str, *args: str):
    return run([sys.executable, str(ROOT / "scripts" / script), *args], cwd=ROOT, capture_output=True, text=True)


def _collection_and_evidence(root: Path, *, actionability: str = "ACTIONABLE") -> tuple[dict, dict]:
    body = "please fix this"
    body_hash = hashlib.sha256(body.encode()).hexdigest()
    comment = {
        "schema_version": 1, "source": "inline", "source_identity": "local:1", "comment_id": "1",
        "revision_identity": "r1", "body_hash": body_hash, "author": "reviewer", "body": body,
        "created_at": "2026-07-19T10:00:00Z", "path": "changed.py", "line": 1,
    }
    collection = {"schema_version": 1, "input_identity": "local-review-1", "complete": True, "comments": [comment]}
    key = revision_key(comment)
    evidence = {key: {
        "actionability": actionability, "alignment": {"spec": "ALIGNS", "design": "ALIGNS", "ownership": "OWNED", "verification": "AVAILABLE"},
        "validation_plan": ["run local checks"], "changed_files": ["changed.py"], "repository_root": str(root.resolve()),
        "validation": [{"command": "python -m pytest", "passed": True}], "evidence": [{"token": "must-not-print", "note": "local"}],
    }}
    return collection, evidence


def test_self_improve_passes_root_policy_and_never_allows_rootless_compatibility(tmp_path: Path) -> None:
    entries = tmp_path / "entries.json"; entries.write_text('[{"lesson":"x"}]', encoding="utf-8")
    paths = tmp_path / "paths.json"; paths.write_text('["app.py"]', encoding="utf-8")
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    missing = invoke("self_improve_adapter.py", "--repository-root", str(tmp_path), "--entries", str(entries), "--paths", str(paths), "--train-improved")
    assert json.loads(missing.stdout)["change"]["action"] == "PROPOSAL"
    allowed = invoke("self_improve_adapter.py", "--repository-root", str(tmp_path), "--entries", str(entries), "--paths", str(paths), "--train-improved", "--rollback-record", "r1", "--run-cap", "1", "--recurrence-confirmed", "--critic-passed")
    assert json.loads(allowed.stdout)["change"]["action"] == "APPLY"
    paths.write_text('["app/../scripts/evil.py"]', encoding="utf-8")
    protected = invoke("self_improve_adapter.py", "--repository-root", str(tmp_path), "--entries", str(entries), "--paths", str(paths), "--train-improved", "--rollback-record", "r1", "--run-cap", "1", "--recurrence-confirmed", "--critic-passed")
    assert json.loads(protected.stdout)["change"]["action"] in {"PROPOSAL", "BLOCKED"}


def test_pr_adapter_records_strict_snapshot_redacts_evidence_and_converges(tmp_path: Path) -> None:
    (tmp_path / "changed.py").write_text("x = 1\n", encoding="utf-8")
    collection, evidence = _collection_and_evidence(tmp_path)
    collection_path = tmp_path / "collection.json"; collection_path.write_text(json.dumps(collection), encoding="utf-8")
    evidence_path = tmp_path / "evidence.json"; evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    command = json.dumps([sys.executable, "-c", "raise SystemExit(0)"])
    audit = tmp_path / ".harness" / "audit" / "review.jsonl"
    report = tmp_path / ".harness" / "reports" / "review.json"
    result = invoke("pr_converge_adapter.py", "--repository-root", str(tmp_path), "--collection", str(collection_path), "--evidence", str(evidence_path), "--audit", str(audit), "--report", str(report), "--build-command", command, "--lint-command", command, "--test-command", command)
    payload = json.loads(result.stdout)
    assert result.returncode == 0 and payload["status"] == "CONVERGED"
    assert payload["dispositions"][0]["decision"] == "SAFE_FIX"
    assert payload["dispositions"][0]["alignment"]["spec"] == "ALIGNS"
    assert payload["dispositions"][0]["fix"]["changed_files"] == ["changed.py"]
    assert payload["dispositions"][0]["evidence"][0]["token"] == "[REDACTED]"
    raw_audit = audit.read_text(encoding="utf-8")
    assert "must-not-print" in raw_audit
    assert "must-not-print" not in result.stdout
    assert "must-not-print" not in report.read_text(encoding="utf-8")
    assert len(raw_audit.splitlines()) == 2


def test_pr_adapter_resume_renders_audited_disposition_and_redacts_textual_secrets(tmp_path: Path) -> None:
    (tmp_path / "changed.py").write_text("x = 1\n", encoding="utf-8")
    collection, evidence = _collection_and_evidence(tmp_path)
    key = next(iter(evidence))
    evidence[key]["evidence"] = [{"note": "secret-literal must not be printed"}]
    collection_path = tmp_path / "collection.json"; collection_path.write_text(json.dumps(collection), encoding="utf-8")
    evidence_path = tmp_path / "evidence.json"; evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    command = json.dumps([sys.executable, "-c", "print('token=secret-literal')"])
    arguments = ("--repository-root", str(tmp_path), "--collection", str(collection_path), "--evidence", str(evidence_path), "--audit", str(tmp_path / ".harness" / "audit" / "review.jsonl"), "--build-command", command, "--lint-command", command, "--test-command", command)

    first = invoke("pr_converge_adapter.py", *arguments)
    resumed = invoke("pr_converge_adapter.py", *arguments)
    payload = json.loads(resumed.stdout)

    assert first.returncode == resumed.returncode == 0
    assert payload["status"] == "CONVERGED"
    assert payload["dispositions"][0]["source_identity"] == "local:1"
    assert payload["dispositions"][0]["revision_identity"] == "r1"
    assert payload["dispositions"][0]["decision"] == "SAFE_FIX"
    assert payload["dispositions"][0]["reason"] == "aligned local rule, owned scope, changed files, and passing validation"
    assert payload["dispositions"][0]["evidence"] == [{"note": "[REDACTED]"}]
    rendered = json.dumps(payload)
    assert "secret-literal" not in rendered
    assert payload["local_commands"][0]["stdout"] == "[REDACTED]"
    history = tmp_path / ".harness" / "audit" / "review.jsonl"
    assert len(history.read_text(encoding="utf-8").splitlines()) == 3
    assert "secret-literal" in history.read_text(encoding="utf-8")


def test_pr_adapter_redacts_opaque_credential_and_api_key_values_at_any_depth(tmp_path: Path) -> None:
    """Keyed opaque values are secret values even when their text has no marker."""
    (tmp_path / "changed.py").write_text("x = 1\n", encoding="utf-8")
    collection, evidence = _collection_and_evidence(tmp_path)
    key = next(iter(evidence))
    credential = "unmarked-credential-value-123"
    api_key = "unmarked-api-key-value-456"
    evidence[key]["evidence"] = [{
        "credential": credential,
        "nested": {"api-key": api_key, "Api Key": api_key},
    }]
    collection_path = tmp_path / "collection.json"; collection_path.write_text(json.dumps(collection), encoding="utf-8")
    evidence_path = tmp_path / "evidence.json"; evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    command = json.dumps([sys.executable, "-c", "raise SystemExit(0)"])

    result = invoke(
        "pr_converge_adapter.py", "--repository-root", str(tmp_path),
        "--collection", str(collection_path), "--evidence", str(evidence_path),
        "--audit", str(tmp_path / ".harness" / "audit" / "review.jsonl"), "--build-command", command,
        "--lint-command", command, "--test-command", command,
    )
    payload = json.loads(result.stdout)

    assert result.returncode == 0
    assert payload["dispositions"][0]["evidence"] == [{
        "credential": "[REDACTED]",
        "nested": {"api-key": "[REDACTED]", "Api Key": "[REDACTED]"},
    }]
    rendered = json.dumps(payload)
    assert credential not in rendered
    assert api_key not in rendered


def test_pr_adapter_redacts_split_and_joined_argv_secrets_without_hiding_harmless_values(tmp_path: Path) -> None:
    (tmp_path / "changed.py").write_text("x = 1\n", encoding="utf-8")
    collection, evidence = _collection_and_evidence(tmp_path)
    key = next(iter(evidence))
    evidence[key]["evidence"] = [{
        "argv": ["tool", "--password", "opaque-one", "--password=opaque-two", "tokenizer"],
        "nested": [
            {"argv": ["tool", "--api-key", "opaque-three"]},
            {"header": "Authorization: Bearer opaque-four", "message": "password reset completed"},
        ],
    }]
    collection_path = tmp_path / "collection.json"; collection_path.write_text(json.dumps(collection), encoding="utf-8")
    evidence_path = tmp_path / "evidence.json"; evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    command = json.dumps([sys.executable, "-c", "raise SystemExit(0)", "--password", "opaque-five", "--password=opaque-six", "tokenizer"])

    result = invoke(
        "pr_converge_adapter.py", "--repository-root", str(tmp_path),
        "--collection", str(collection_path), "--evidence", str(evidence_path),
        "--audit", str(tmp_path / ".harness" / "audit" / "review.jsonl"),
        "--build-command", command, "--lint-command", command, "--test-command", command,
    )
    payload = json.loads(result.stdout)
    rendered = json.dumps(payload)

    assert result.returncode == 0
    assert not any(secret in rendered for secret in ("opaque-one", "opaque-two", "opaque-three", "opaque-four", "opaque-five", "opaque-six"))
    assert payload["local_commands"][0]["command"][-1] == "tokenizer"
    assert payload["dispositions"][0]["evidence"][0]["nested"][1]["message"] == "password reset completed"
    raw_audit = (tmp_path / ".harness" / "audit" / "review.jsonl").read_text(encoding="utf-8")
    assert "opaque-one" in raw_audit and "opaque-four" in raw_audit


def test_pr_adapter_rejects_audit_in_report_tree_and_same_path_before_writing(tmp_path: Path) -> None:
    (tmp_path / "changed.py").write_text("x = 1\n", encoding="utf-8")
    collection, evidence = _collection_and_evidence(tmp_path)
    collection_path = tmp_path / "collection.json"; collection_path.write_text(json.dumps(collection), encoding="utf-8")
    evidence_path = tmp_path / "evidence.json"; evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    invalid_audit = tmp_path / ".harness" / "reports" / "raw.jsonl"
    result = invoke(
        "pr_converge_adapter.py", "--repository-root", str(tmp_path),
        "--collection", str(collection_path), "--evidence", str(evidence_path),
        "--audit", str(invalid_audit),
    )
    assert result.returncode == 2
    assert "must be inside .harness/audit/" in json.loads(result.stdout)["reason"]
    assert not invalid_audit.exists()

    shared = tmp_path / ".harness" / "audit" / "shared.jsonl"
    same = invoke(
        "pr_converge_adapter.py", "--repository-root", str(tmp_path),
        "--collection", str(collection_path), "--evidence", str(evidence_path),
        "--audit", str(shared), "--report", str(shared),
    )
    assert same.returncode == 2
    assert "same file or inode" in json.loads(same.stdout)["reason"]
    assert not shared.exists()


def test_pr_adapter_rejects_outside_and_symlink_escape_without_raw_leak(tmp_path: Path) -> None:
    (tmp_path / "changed.py").write_text("x = 1\n", encoding="utf-8")
    collection, evidence = _collection_and_evidence(tmp_path)
    collection_path = tmp_path / "collection.json"; collection_path.write_text(json.dumps(collection), encoding="utf-8")
    evidence_path = tmp_path / "evidence.json"; evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    escaped = outside / "raw.jsonl"
    direct = invoke(
        "pr_converge_adapter.py", "--repository-root", str(tmp_path),
        "--collection", str(collection_path), "--evidence", str(evidence_path),
        "--audit", str(escaped),
    )
    assert direct.returncode == 2 and not escaped.exists()
    assert "must-not-print" not in direct.stdout

    (tmp_path / ".harness").mkdir(exist_ok=True)
    (tmp_path / ".harness" / "audit").symlink_to(outside, target_is_directory=True)
    linked = invoke(
        "pr_converge_adapter.py", "--repository-root", str(tmp_path),
        "--collection", str(collection_path), "--evidence", str(evidence_path),
        "--audit", str(tmp_path / ".harness" / "audit" / "escaped.jsonl"),
    )
    assert linked.returncode == 2 and not (outside / "escaped.jsonl").exists()
    assert "must-not-print" not in linked.stdout


def test_pr_adapter_rejects_existing_hardlink_audit_report_alias_before_append(tmp_path: Path) -> None:
    (tmp_path / "changed.py").write_text("x = 1\n", encoding="utf-8")
    collection, evidence = _collection_and_evidence(tmp_path)
    collection_path = tmp_path / "collection.json"; collection_path.write_text(json.dumps(collection), encoding="utf-8")
    evidence_path = tmp_path / "evidence.json"; evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    audit = tmp_path / ".harness" / "audit" / "review.jsonl"
    report = tmp_path / ".harness" / "reports" / "review.json"
    audit.parent.mkdir(parents=True); report.parent.mkdir(parents=True)
    audit.write_text('{"existing":"history"}\n', encoding="utf-8")
    report.hardlink_to(audit)

    result = invoke(
        "pr_converge_adapter.py", "--repository-root", str(tmp_path),
        "--collection", str(collection_path), "--evidence", str(evidence_path),
        "--audit", str(audit), "--report", str(report),
    )
    assert result.returncode == 2
    assert "same file or inode" in json.loads(result.stdout)["reason"]
    assert audit.read_text(encoding="utf-8") == '{"existing":"history"}\n'


def test_pr_adapter_blocks_malformed_input_and_does_not_claim_convergence_without_commands(tmp_path: Path) -> None:
    malformed = tmp_path / "bad.json"; malformed.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
    evidence = tmp_path / "evidence.json"; evidence.write_text("{}", encoding="utf-8")
    blocked = invoke("pr_converge_adapter.py", "--repository-root", str(tmp_path), "--collection", str(malformed), "--evidence", str(evidence), "--audit", str(tmp_path / ".harness" / "audit" / "review.jsonl"))
    assert blocked.returncode == 2 and json.loads(blocked.stdout)["status"] == "BLOCKED"
    (tmp_path / "changed.py").write_text("x = 1\n", encoding="utf-8")
    collection, entries = _collection_and_evidence(tmp_path, actionability="NON_ACTIONABLE")
    entries[next(iter(entries))] = {"actionability": "NON_ACTIONABLE", "reason": "not actionable"}
    cp = tmp_path / "complete.json"; cp.write_text(json.dumps(collection), encoding="utf-8")
    ep = tmp_path / "complete-evidence.json"; ep.write_text(json.dumps(entries), encoding="utf-8")
    waiting = invoke("pr_converge_adapter.py", "--repository-root", str(tmp_path), "--collection", str(cp), "--evidence", str(ep), "--audit", str(tmp_path / ".harness" / "audit" / "review2.jsonl"))
    assert waiting.returncode == 0 and json.loads(waiting.stdout)["status"] == "WORKING"


def test_pr_adapter_explains_justified_rejection_and_escalates_unknown_alignment(tmp_path: Path) -> None:
    (tmp_path / "changed.py").write_text("x = 1\n", encoding="utf-8")
    collection, evidence = _collection_and_evidence(tmp_path)
    key = next(iter(evidence))
    evidence[key] = {
        "actionability": "ACTIONABLE",
        "alignment": {"spec": "CONFLICTS", "design": "ALIGNS", "ownership": "OWNED", "verification": "AVAILABLE"},
        "reason": "The request contradicts the approved local-only requirement.",
        "alternative": "Propose a spec change before adding a provider dependency.",
        "evidence": [{"kind": "spec", "ref": "F5 local convergence"}],
    }
    collection_path = tmp_path / "collection.json"; collection_path.write_text(json.dumps(collection), encoding="utf-8")
    evidence_path = tmp_path / "rejection.json"; evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    command = json.dumps([sys.executable, "-c", "raise SystemExit(0)"])
    rejected = invoke(
        "pr_converge_adapter.py", "--repository-root", str(tmp_path), "--collection", str(collection_path),
        "--evidence", str(evidence_path), "--audit", str(tmp_path / ".harness" / "audit" / "rejected.jsonl"),
        "--build-command", command, "--lint-command", command, "--test-command", command,
    )
    payload = json.loads(rejected.stdout)
    assert rejected.returncode == 0 and payload["status"] == "CONVERGED"
    assert payload["dispositions"][0]["decision"] == "REJECTED"
    assert payload["dispositions"][0]["alignment"]["spec"] == "CONFLICTS"
    assert "contradicts" in payload["dispositions"][0]["reason"]
    assert "spec change" in payload["dispositions"][0]["alternative"]

    evidence[key] = {"actionability": "ACTIONABLE", "alignment": {"spec": "UNKNOWN"}}
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    escalated = invoke(
        "pr_converge_adapter.py", "--repository-root", str(tmp_path), "--collection", str(collection_path),
        "--evidence", str(evidence_path), "--audit", str(tmp_path / ".harness" / "audit" / "escalated.jsonl"),
        "--build-command", command, "--lint-command", command, "--test-command", command,
    )
    escalated_payload = json.loads(escalated.stdout)
    assert escalated.returncode == 0 and escalated_payload["status"] == "NEEDS_HUMAN"
    assert escalated_payload["dispositions"][0]["decision"] == "ESCALATED"


def test_pr_adapter_resolves_escalation_without_new_review_revision(tmp_path: Path) -> None:
    (tmp_path / "changed.py").write_text("x = 1\n", encoding="utf-8")
    collection, evidence = _collection_and_evidence(tmp_path)
    key = next(iter(evidence))
    evidence[key] = {"alignment": {"spec": "UNKNOWN"}}
    collection_path = tmp_path / "collection.json"
    evidence_path = tmp_path / "evidence.json"
    resolution_path = tmp_path / "resolution.json"
    collection_path.write_text(json.dumps(collection), encoding="utf-8")
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    audit = tmp_path / ".harness/audit/review.jsonl"
    command = json.dumps([sys.executable, "-c", "raise SystemExit(0)"])
    common = (
        "--repository-root", str(tmp_path), "--collection", str(collection_path),
        "--evidence", str(evidence_path), "--audit", str(audit),
        "--build-command", command, "--lint-command", command, "--test-command", command,
    )

    first = invoke("pr_converge_adapter.py", *common)
    first_payload = json.loads(first.stdout)
    assert first_payload["status"] == "NEEDS_HUMAN"
    assert first_payload["dispositions"][0]["decision"] == "ESCALATED"

    comment = collection["comments"][0]
    secret = "resolution-private-literal"
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
            "decision": "SAFE_FIX",
            "reason": "The user confirmed the request aligns with the approved local requirement.",
            "evidence": [{"kind": "user_decision", "credential": secret}],
            "fix": {
                "repository_root": str(tmp_path.resolve()),
                "changed_files": ["changed.py"],
                "validation": [{"command": "python -m pytest", "passed": True}],
            },
        }],
    }
    resolution_path.write_text(json.dumps(resolution), encoding="utf-8")
    resolved = invoke("pr_converge_adapter.py", *common, "--resolutions", str(resolution_path))
    payload = json.loads(resolved.stdout)
    assert resolved.returncode == 0 and payload["status"] == "CONVERGED"
    assert payload["dispositions"][0]["revision_identity"] == "r1"
    assert payload["dispositions"][0]["decision"] == "SAFE_FIX"
    assert payload["dispositions"][0]["reason"].startswith("The user confirmed")
    assert payload["dispositions"][0]["evidence"] == [
        {"kind": "user_decision", "credential": "[REDACTED]"}
    ]
    assert payload["dispositions"][0]["fix"]["changed_files"] == ["changed.py"]
    assert secret not in resolved.stdout and secret in audit.read_text(encoding="utf-8")
    assert [event["event_type"] for event in map(json.loads, audit.read_text().splitlines())] == [
        "collection_snapshot", "disposition", "collection_snapshot", "escalation_resolution"
    ]

    resumed = invoke("pr_converge_adapter.py", *common, "--resolutions", str(resolution_path))
    assert json.loads(resumed.stdout)["status"] == "CONVERGED"
    assert len(audit.read_text(encoding="utf-8").splitlines()) == 5

    resumed_from_audit = invoke("pr_converge_adapter.py", *common)
    assert json.loads(resumed_from_audit.stdout)["status"] == "CONVERGED"
    assert len(audit.read_text(encoding="utf-8").splitlines()) == 6

    resolution["resolutions"][0]["decision"] = "REJECTED"
    resolution["resolutions"][0]["alternative"] = "Do not apply the change."
    resolution_path.write_text(json.dumps(resolution), encoding="utf-8")
    before = audit.read_bytes()
    conflicting = invoke("pr_converge_adapter.py", *common, "--resolutions", str(resolution_path))
    assert conflicting.returncode == 2
    assert "duplicate conflicting resolution" in json.loads(conflicting.stdout)["reason"]
    assert audit.read_bytes() == before


def test_all_adapter_presentation_surfaces_redact_raw_credentials(tmp_path: Path) -> None:
    credential = "sk-live-literal-123456789"
    entries = tmp_path / "entries.json"
    entries.write_text(json.dumps([{"lesson": f"Authorization: Bearer {credential}"}]), encoding="utf-8")
    paths = tmp_path / "paths.json"; paths.write_text('["app.py"]', encoding="utf-8")
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    learning = invoke(
        "self_improve_adapter.py", "--repository-root", str(tmp_path), "--entries", str(entries), "--paths", str(paths),
    )
    assert learning.returncode == 0
    assert credential in entries.read_text(encoding="utf-8")
    assert credential not in learning.stdout

    graph = invoke(
        "code_mapper_adapter.py", "--root", str(tmp_path), "--symbol", "app",
        "--graph-command", json.dumps([sys.executable, "-c", f"print('Authorization: Bearer {credential}'); raise SystemExit(7)"]),
    )
    assert graph.returncode == 2
    assert credential not in graph.stdout


def test_code_mapper_failure_redacts_complete_authorization_header_values(tmp_path: Path) -> None:
    cases = (
        ("Authorization", "Basic b3BhcXVlLWNyZWRlbnRpYWw="),
        ("Authorization", "Bearer opaque-bearer-credential"),
        ("Authorization", 'Digest username="moon", realm="local", response="opaque-digest"'),
        ("Authorization", "Token opaque-token-credential"),
        ("Proxy-Authorization", "Custom opaque-custom-credential extra=opaque-suffix"),
    )
    for separator in ("\n", "\r\n", r"\n", r"\r\n"):
        command_separator = repr(separator)[1:-1]
        output_separator = "\n" if separator == "\r\n" else separator
        for header, field_value in cases:
            diagnostic = (
                f"before context{separator}{header}: {field_value}{separator}"
                f"X-Authorization: approved{separator}"
                f"X-Proxy-Authorization: approved{separator}"
                f"authorization: approved{separator}"
                "harmless diagnostic"
            )
            graph = invoke(
                "code_mapper_adapter.py", "--root", str(tmp_path), "--symbol", "app",
                "--graph-command", json.dumps([
                    sys.executable, "-c", f"print({diagnostic!r}); raise SystemExit(7)",
                ]),
            )
            payload = json.loads(graph.stdout)
            rendered = json.dumps(payload)

            assert graph.returncode == 2
            assert field_value not in rendered
            assert "opaque-digest" not in rendered
            assert 'username=\\"moon\\"' not in rendered
            assert 'realm=\\"local\\"' not in rendered
            assert f"before context{output_separator}" in payload["evidence"]["stdout"]
            assert f"{header}: [REDACTED]{output_separator}" in payload["evidence"]["stdout"]
            assert f"X-Authorization: approved{output_separator}" in payload["evidence"]["stdout"]
            assert f"X-Proxy-Authorization: approved{output_separator}" in payload["evidence"]["stdout"]
            assert f"authorization: approved{output_separator}" in payload["evidence"]["stdout"]
            assert "harmless diagnostic" in payload["evidence"]["stdout"]

            command = payload["evidence"]["command"]
            command_rendered = json.dumps(command)
            assert field_value not in command_rendered
            assert "opaque-digest" not in command_rendered
            assert f"before context{command_separator}" in command[-1]
            assert f"{header}: [REDACTED]{command_separator}" in command[-1]
            assert f"X-Authorization: approved{command_separator}" in command[-1]
            assert f"X-Proxy-Authorization: approved{command_separator}" in command[-1]
            assert f"authorization: approved{command_separator}" in command[-1]
            assert "harmless diagnostic" in command[-1]


def test_self_improve_uses_repository_config_and_rejects_nonstandard_json(tmp_path: Path) -> None:
    entries = tmp_path / "entries.json"; entries.write_text('[{"lesson":"x"}]', encoding="utf-8")
    paths = tmp_path / "paths.json"; paths.write_text('["app.py"]', encoding="utf-8")
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / ".harness").mkdir()
    (tmp_path / ".harness" / "config.json").write_text('{"knowledge_sync":{"enabled":true}}', encoding="utf-8")
    configured = invoke("self_improve_adapter.py", "--repository-root", str(tmp_path), "--entries", str(entries), "--paths", str(paths))
    assert json.loads(configured.stdout)["knowledge_sync"]["status"] == "READY"

    entries.write_text('[{"lesson":NaN}]', encoding="utf-8")
    blocked = invoke("self_improve_adapter.py", "--repository-root", str(tmp_path), "--entries", str(entries), "--paths", str(paths))
    assert blocked.returncode == 2 and json.loads(blocked.stdout)["status"] == "BLOCKED"


def test_self_improve_resolves_explicit_relative_inputs_from_repository_root(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    (inputs / "entries.json").write_text('[{"lesson":"x"}]', encoding="utf-8")
    (inputs / "paths.json").write_text('["app.py"]', encoding="utf-8")
    (inputs / "config.json").write_text(
        '{"knowledge_sync":{"enabled":true}}', encoding="utf-8"
    )
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")

    result = invoke(
        "self_improve_adapter.py", "--repository-root", str(tmp_path),
        "--entries", "inputs/entries.json", "--paths", "inputs/paths.json",
        "--config", "inputs/config.json",
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["knowledge_sync"]["status"] == "READY"
    assert payload["evidence"]["entries"] == str((inputs / "entries.json").resolve())
    assert payload["evidence"]["config"] == str((inputs / "config.json").resolve())

    outside_values = {
        "entries": '[{"lesson":"outside"}]',
        "paths": '["outside.py"]',
        "config": "{}",
    }
    for label, value in outside_values.items():
        outside = tmp_path.parent / f"{tmp_path.name}-outside-{label}.json"
        outside.write_text(value, encoding="utf-8")
        arguments = {
            "entries": "inputs/entries.json",
            "paths": "inputs/paths.json",
            "config": "inputs/config.json",
        }
        arguments[label] = str(outside)
        blocked = invoke(
            "self_improve_adapter.py", "--repository-root", str(tmp_path),
            "--entries", arguments["entries"], "--paths", arguments["paths"],
            "--config", arguments["config"],
        )
        assert blocked.returncode == 2
        assert "inside --repository-root" in json.loads(blocked.stdout)["reason"]


def test_code_mapper_reports_blocked_approximate_fallback(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def target(): pass\ntarget()\n", encoding="utf-8")
    result = invoke("code_mapper_adapter.py", "--root", str(tmp_path), "--symbol", "target", "--graph-command", json.dumps([sys.executable, "-c", "import sys; sys.exit(7)"]))
    payload = json.loads(result.stdout)
    assert result.returncode == 2 and payload["status"] == "BLOCKED"
    assert payload["fallback"]["approximate"] is True and payload["evidence"]["returncode"] == 7


def test_portable_skill_documentation_has_no_active_personal_or_host_syntax() -> None:
    forbidden = ("/Users/", ".claude/", "CLAUDE_PLUGIN_ROOT", "CODEX_PLUGIN_ROOT", "HARNESS_HOOKS", "Agent(", "TeamCreate")
    for name in ("self-improve", "pr-converge", "code-mapper"):
        content = (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        assert not any(token in content for token in forbidden)
        assert "explicit" in content.lower()
