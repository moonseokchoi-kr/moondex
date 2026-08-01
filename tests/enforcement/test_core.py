from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from harness_core import cli
from harness_core.enforcement import EnforcementError, canonical_path, local_protected_roots, verify_local


def write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.fixture()
def local_project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    write(root, ".harness/state/tdd-manifest.json", '{"red_evidence":"test","green_command":"python3 -m pytest"}')
    write(root, ".harness/state/e2e-config.json", '{"command":"npm test:e2e"}')
    return root


def test_explicit_report_is_versioned_redacted_and_passes(local_project: Path) -> None:
    write(local_project, "src/service.py", "def service(): pass\n")
    result = verify_local(local_project, source="explicit", changed_files=["src/service.py"], branch="feature/t7")
    report = result.audit()
    assert result.status == "PASS"
    assert report["schema_version"] == 3
    assert report["source"] == "explicit"
    assert report["changed_files"] == [{"source": "explicit", "status": "M", "paths": ["src/service.py"]}]
    assert report["worktree"]["identity"]


def test_missing_explicit_or_clean_worktree_is_indeterminate(local_project: Path) -> None:
    with pytest.raises(EnforcementError, match="CHANGED_FILE_INDETERMINATE"):
        verify_local(local_project, source="explicit", changed_files=[], branch="feature/t7")
    with pytest.raises(EnforcementError, match="CHANGED_FILE_INDETERMINATE"):
        verify_local(local_project, source="worktree", branch="feature/t7")


def test_containment_rejects_traversal_absolute_and_external_symlink(local_project: Path) -> None:
    with pytest.raises(EnforcementError, match="INDETERMINATE_PATH"):
        canonical_path(local_project, "app/../scripts/verify.py")
    with pytest.raises(EnforcementError, match="INVALID_PATH"):
        canonical_path(local_project, str(local_project / "src/service.py"))
    outside = local_project.parent / "outside"
    outside.mkdir()
    (local_project / "linked").symlink_to(outside, target_is_directory=True)
    with pytest.raises(EnforcementError, match="OUTSIDE_OR_INDETERMINATE"):
        canonical_path(local_project, "linked/secret.txt")
    (local_project / "broken").symlink_to("missing-target", target_is_directory=True)
    with pytest.raises(EnforcementError, match="OUTSIDE_OR_INDETERMINATE"):
        canonical_path(local_project, "broken/secret.txt")
    assert canonical_path(local_project, "new/path.py") == "new/path.py"


def test_in_root_symlink_alias_uses_physical_path_for_protected_matching(local_project: Path) -> None:
    """An alias to a protected root must not change the enforcement identity."""
    write(local_project, ".codex-plugin/plugin.json", "{}")
    write(local_project, "scripts/protected.py", "pass\n")
    (local_project / "linked").symlink_to("scripts", target_is_directory=True)

    result = verify_local(
        local_project, source="explicit", changed_files=["linked/protected.py"], branch="feature/t7",
    )

    assert canonical_path(local_project, "linked/protected.py") == "scripts/protected.py"
    assert result.status == "FAIL"
    protected = next(item for item in result.outcomes if item["rule"] == "PROTECTED_PATH")
    assert protected["files"] == ["scripts/protected.py"]
    assert result.audit()["changed_files"] == [
        {"source": "explicit", "status": "M", "paths": ["scripts/protected.py"]}
    ]


def test_plugin_protected_set_is_non_removable(local_project: Path) -> None:
    write(local_project, ".codex-plugin/plugin.json", "{}")
    write(local_project, ".harness/config.json", '{"security":{"protected_paths":[]}}')
    write(local_project, "scripts/verify.py", "pass\n")
    result = verify_local(local_project, source="explicit", changed_files=["scripts/verify.py"], branch="feature/t7")
    assert result.status == "FAIL"
    assert any(item["rule"] == "PROTECTED_PATH" for item in result.outcomes)


def test_local_protected_roots_combines_immutable_and_configured_roots(local_project: Path) -> None:
    write(local_project, ".codex-plugin/plugin.json", "{}")
    write(local_project, ".harness/config.json", '{"security":{"protected_paths":["infra/release.py"]}}')

    assert local_protected_roots(local_project) == (
        ".codex-plugin", ".github", "agents", "benchmarks", "evals", "harness_core",
        "hooks", "infra", "scripts", "skills", "tests",
    )


@pytest.mark.parametrize("config", [
    '{"security":{"protected_paths":"infra"}}',
    '{"security":{"protected_paths":["infra/../scripts"]}}',
])
def test_local_protected_roots_fails_closed_for_invalid_config(local_project: Path, config: str) -> None:
    write(local_project, ".harness/config.json", config)
    with pytest.raises(EnforcementError):
        local_protected_roots(local_project)


def test_local_protected_roots_rejects_non_directory_root(tmp_path: Path) -> None:
    root = tmp_path / "not-a-project"
    root.write_text("not a directory", encoding="utf-8")
    with pytest.raises(EnforcementError, match="WORKTREE_UNAVAILABLE"):
        local_protected_roots(root)


def test_plugin_immutable_protected_root_cannot_be_waived(local_project: Path) -> None:
    write(local_project, ".codex-plugin/plugin.json", "{}")
    write(local_project, ".harness/config.json", '{"security":{"protected_paths":[]}}')
    write(local_project, "scripts/verify.py", "pass\n")
    result = verify_local(
        local_project, source="explicit", changed_files=["scripts/verify.py"], branch="feature/t7",
        allowed_protected_paths=["scripts/verify.py"],
    )
    assert result.status == "FAIL"
    assert any(item["rule"] == "PROTECTED_PATH" for item in result.outcomes)


@pytest.mark.parametrize(("content", "secret_class"), [
    ("API_KEY=abcdefghijk12345\n", "assignment"),
    ('{"api_key":"abcdefghijk12345"}\n', "json-credential"),
    ("Authorization: Bearer abcdefghijk12345\n", "bearer"),
])
def test_secret_forms_fail_without_leaking_literal(local_project: Path, content: str, secret_class: str) -> None:
    write(local_project, "config.txt", content)
    result = verify_local(local_project, source="explicit", changed_files=["config.txt"], branch="feature/t7")
    assert result.status == "FAIL"
    assert any(secret_class in item.get("classes", []) for item in result.outcomes)
    assert "abcdefghijk12345" not in json.dumps(result.audit())


def test_placeholder_and_valid_allowlist_pass_with_redacted_evidence(local_project: Path) -> None:
    write(local_project, "config.txt", "API_KEY=${API_KEY}\nAuthorization: Bearer <token>\n")
    assert verify_local(local_project, source="explicit", changed_files=["config.txt"], branch="feature/t7").status == "PASS"
    write(local_project, "config.txt", "API_KEY=abcdefghijk12345\n")
    write(local_project, ".harness/secret-allowlist.json", '[{"id":"fixture","file":"config.txt","line":1,"pattern_class":"assignment","reason":"fixture","expiry":"2099-01-01","approver":"moon"}]')
    result = verify_local(local_project, source="explicit", changed_files=["config.txt"], branch="feature/t7")
    assert result.status == "PASS"
    assert any(item["rule"] == "SECRET_ALLOWLIST" for item in result.outcomes)
    assert "abcdefghijk12345" not in json.dumps(result.audit())


def test_ui_and_default_branch_fail_with_local_remediation(local_project: Path) -> None:
    write(local_project, "web/Panel.tsx", "export const Panel = () => null\n")
    (local_project / ".harness/state/e2e-config.json").unlink()
    result = verify_local(local_project, source="explicit", changed_files=["web/Panel.tsx"], branch="main")
    rules = {item["rule"] for item in result.outcomes}
    assert {"BRANCH_DEFAULT", "E2E_EVIDENCE_MISSING"} <= rules


def test_worktree_and_explicit_have_same_canonical_paths(local_project: Path) -> None:
    subprocess.run(("git", "init", "-b", "feature/t7"), cwd=local_project, check=True, capture_output=True)
    subprocess.run(("git", "config", "user.email", "test@example.invalid"), cwd=local_project, check=True)
    subprocess.run(("git", "config", "user.name", "Test"), cwd=local_project, check=True)
    subprocess.run(("git", "add", "."), cwd=local_project, check=True)
    subprocess.run(("git", "commit", "-m", "base"), cwd=local_project, check=True, capture_output=True)
    write(local_project, "src/service.py", "def changed(): pass\n")
    worktree = verify_local(local_project, source="worktree", branch="feature/t7")
    explicit = verify_local(local_project, source="explicit", changed_files=["src/service.py"], branch="feature/t7")
    hook = verify_local(local_project, source="hook", changed_files=["src/service.py"], branch="feature/t7")
    assert worktree.changed_files[0]["paths"] == explicit.changed_files[0]["paths"]
    assert worktree.outcomes == explicit.outcomes
    assert hook.changed_files[0]["paths"] == explicit.changed_files[0]["paths"]
    assert hook.outcomes == explicit.outcomes


def test_expired_or_malformed_allowlist_fails_closed(local_project: Path) -> None:
    write(local_project, "config.txt", "API_KEY=abcdefghijk12345\n")
    write(local_project, ".harness/secret-allowlist.json", "not-json")
    with pytest.raises(EnforcementError, match="ALLOWLIST_INVALID"):
        verify_local(local_project, source="explicit", changed_files=["config.txt"], branch="feature/t7")
    write(local_project, ".harness/secret-allowlist.json", '[{"id":"old","file":"config.txt","line":1,"pattern_class":"assignment","reason":"fixture","expiry":"2000-01-01","approver":"moon"}]')
    with pytest.raises(EnforcementError, match="ALLOWLIST_INVALID"):
        verify_local(local_project, source="explicit", changed_files=["config.txt"], branch="feature/t7")


def test_cli_writes_same_report_shape(local_project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write(local_project, "src/service.py", "def service(): pass\n")
    audit = local_project / ".harness/reports/local.json"
    assert cli.main(["preflight", "check", "--project-root", str(local_project), "--branch", "feature/t7", "--changed-file", "src/service.py", "--audit-file", str(audit)]) == 0
    assert json.loads(audit.read_text(encoding="utf-8"))["schema_version"] == 3
    assert "PREFLIGHT_OK" in capsys.readouterr().out


def test_cli_writes_indeterminate_audit_for_missing_changed_file_input(
    local_project: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    audit = local_project / ".harness/reports/indeterminate.json"
    assert cli.main([
        "preflight", "check", "--project-root", str(local_project), "--branch", "feature/t7",
        "--source", "explicit", "--audit-file", str(audit),
    ]) == 2
    report = json.loads(audit.read_text(encoding="utf-8"))
    assert report["schema_version"] == 3
    assert report["status"] == "INDETERMINATE"
    assert report["outcomes"] == [{
        "rule": "CHANGED_FILE_INDETERMINATE", "status": "INDETERMINATE",
        "reason": "CHANGED_FILE_INDETERMINATE: no usable changed-file input; supply --changed-file or use a Git worktree",
    }]
    assert "PREFLIGHT_FAILED: CHANGED_FILE_INDETERMINATE" in capsys.readouterr().out
