from __future__ import annotations

import os
import shutil
from pathlib import Path
from subprocess import run

from harness_core.enforcement import verify_local

REPOSITORY_ROOT = Path(__file__).parents[2]


def _run(root: Path, *command: str, input: str | None = None, env: dict[str, str] | None = None):
    return run(command, cwd=root, input=input, text=True, capture_output=True, check=True, env=env)


def test_pre_push_rejects_outgoing_direct_default_branch_commit(tmp_path: Path) -> None:
    """A commit made with --no-verify must still fail the outgoing-ref pre-push gate."""

    root = tmp_path / "project"
    root.mkdir()
    shutil.copytree(REPOSITORY_ROOT / "harness_core", root / "harness_core")
    (root / "scripts").mkdir()
    for name in ("install-hooks.sh", "verify.py"):
        shutil.copy2(REPOSITORY_ROOT / "scripts" / name, root / "scripts" / name)
    _run(root, "git", "init", "-b", "main")
    _run(root, "git", "config", "user.email", "test@example.invalid")
    _run(root, "git", "config", "user.name", "Harness Test")
    (root / "README.md").write_text("initial\n", encoding="utf-8")
    _run(root, "git", "add", "README.md")
    _run(root, "git", "commit", "-m", "initial")
    remote_sha = _run(root, "git", "rev-parse", "HEAD").stdout.strip()
    _run(root, "bash", "scripts/install-hooks.sh")

    (root / "app.py").write_text("def run(): return 'changed'\n", encoding="utf-8")
    manifest = root / ".harness/state/tdd-manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        '{"red_evidence":"tests/test_app.py::test_run","green_command":"python3 -m pytest tests -q"}',
        encoding="utf-8",
    )
    _run(root, "git", "add", "app.py", ".harness/state/tdd-manifest.json")
    # Simulate a user bypassing the local pre-commit hook.
    _run(root, "git", "-c", "core.hooksPath=/dev/null", "commit", "-m", "direct main change")
    local_sha = _run(root, "git", "rev-parse", "HEAD").stdout.strip()

    environment = {**os.environ, "DEFAULT_BRANCH": "main"}
    result = run(
        [str(root / ".git/hooks/pre-push")],
        cwd=root,
        input=f"refs/heads/main {local_sha} refs/heads/main {remote_sha}\n",
        text=True,
        capture_output=True,
        env=environment,
    )

    assert result.returncode == 2
    assert "BRANCH_DEFAULT" in result.stdout


def test_pre_push_uses_remote_target_branch_not_checked_out_branch(tmp_path: Path) -> None:
    """A feature checkout must not be able to push implementation to main."""
    root = tmp_path / "project"
    root.mkdir()
    shutil.copytree(REPOSITORY_ROOT / "harness_core", root / "harness_core")
    (root / "scripts").mkdir()
    for name in ("install-hooks.sh", "verify.py"):
        shutil.copy2(REPOSITORY_ROOT / "scripts" / name, root / "scripts" / name)
    _run(root, "git", "init", "-b", "feature/t7")
    _run(root, "git", "config", "user.email", "test@example.invalid")
    _run(root, "git", "config", "user.name", "Harness Test")
    (root / "README.md").write_text("initial\n", encoding="utf-8")
    _run(root, "git", "add", "README.md")
    _run(root, "git", "commit", "-m", "initial")
    remote_sha = _run(root, "git", "rev-parse", "HEAD").stdout.strip()
    _run(root, "bash", "scripts/install-hooks.sh")

    (root / "app.py").write_text("def run(): return 'changed'\n", encoding="utf-8")
    manifest = root / ".harness/state/tdd-manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        '{"red_evidence":"tests/test_app.py::test_run","green_command":"python3 -m pytest tests -q"}',
        encoding="utf-8",
    )
    _run(root, "git", "add", "app.py", ".harness/state/tdd-manifest.json")
    _run(root, "git", "-c", "core.hooksPath=/dev/null", "commit", "-m", "implementation")
    local_sha = _run(root, "git", "rev-parse", "HEAD").stdout.strip()

    result = run(
        [str(root / ".git/hooks/pre-push")],
        cwd=root,
        input=f"refs/heads/feature/t7 {local_sha} refs/heads/main {remote_sha}\n",
        text=True,
        capture_output=True,
        env={**os.environ, "DEFAULT_BRANCH": "main"},
    )

    assert result.returncode == 2
    assert "BRANCH_DEFAULT" in result.stdout


def test_pre_push_rejects_non_branch_remote_ref(tmp_path: Path) -> None:
    """The generated hook must fail closed when a target ref is not a branch."""
    root = tmp_path / "project"
    root.mkdir()
    shutil.copytree(REPOSITORY_ROOT / "harness_core", root / "harness_core")
    (root / "scripts").mkdir()
    for name in ("install-hooks.sh", "verify.py"):
        shutil.copy2(REPOSITORY_ROOT / "scripts" / name, root / "scripts" / name)
    _run(root, "git", "init", "-b", "feature/t7")
    _run(root, "git", "config", "user.email", "test@example.invalid")
    _run(root, "git", "config", "user.name", "Harness Test")
    (root / "README.md").write_text("initial\n", encoding="utf-8")
    _run(root, "git", "add", "README.md")
    _run(root, "git", "commit", "-m", "initial")
    sha = _run(root, "git", "rev-parse", "HEAD").stdout.strip()
    _run(root, "bash", "scripts/install-hooks.sh")

    result = run(
        [str(root / ".git/hooks/pre-push")], cwd=root,
        input=f"refs/heads/feature/t7 {sha} refs/tags/v1 {sha}\n",
        text=True, capture_output=True,
    )

    assert result.returncode == 2
    assert "REMOTE_REF_UNSUPPORTED" in result.stderr


def test_pre_push_rejects_multi_ref_transaction(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    shutil.copytree(REPOSITORY_ROOT / "harness_core", root / "harness_core")
    (root / "scripts").mkdir()
    for name in ("install-hooks.sh", "verify.py"):
        shutil.copy2(REPOSITORY_ROOT / "scripts" / name, root / "scripts" / name)
    _run(root, "git", "init", "-b", "main")
    _run(root, "git", "config", "user.email", "test@example.invalid")
    _run(root, "git", "config", "user.name", "Harness Test")
    (root / "README.md").write_text("initial\n", encoding="utf-8")
    _run(root, "git", "add", "README.md")
    _run(root, "git", "commit", "-m", "initial")
    sha = _run(root, "git", "rev-parse", "HEAD").stdout.strip()
    _run(root, "bash", "scripts/install-hooks.sh")
    result = run([str(root / ".git/hooks/pre-push")], cwd=root,
                 input=f"refs/heads/a {sha} refs/heads/a {sha}\nrefs/heads/b {sha} refs/heads/b {sha}\n",
                 text=True, capture_output=True)
    assert result.returncode == 2
    assert "MULTI_REF_UNSUPPORTED" in result.stderr


def test_pre_push_checks_both_paths_of_rename_from_protected_plugin_root(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    shutil.copytree(REPOSITORY_ROOT / "harness_core", root / "harness_core")
    (root / "scripts").mkdir()
    for name in ("install-hooks.sh", "verify.py"):
        shutil.copy2(REPOSITORY_ROOT / "scripts" / name, root / "scripts" / name)
    (root / ".codex-plugin").mkdir()
    (root / ".codex-plugin/plugin.json").write_text("{}", encoding="utf-8")
    (root / "scripts/legacy.py").write_text("def legacy(): pass\n", encoding="utf-8")
    manifest = root / ".harness/state/tdd-manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text('{"red_evidence":"test","green_command":"python3 -m pytest"}', encoding="utf-8")
    _run(root, "git", "init", "-b", "feature/t7")
    _run(root, "git", "config", "user.email", "test@example.invalid")
    _run(root, "git", "config", "user.name", "Harness Test")
    _run(root, "git", "add", ".")
    _run(root, "git", "commit", "-m", "initial")
    remote_sha = _run(root, "git", "rev-parse", "HEAD").stdout.strip()
    _run(root, "bash", "scripts/install-hooks.sh")
    (root / "app").mkdir()
    _run(root, "git", "mv", "scripts/legacy.py", "app/legacy.py")
    _run(root, "git", "-c", "core.hooksPath=/dev/null", "commit", "-m", "move legacy implementation")
    local_sha = _run(root, "git", "rev-parse", "HEAD").stdout.strip()

    result = run(
        [str(root / ".git/hooks/pre-push")], cwd=root,
        input=f"refs/heads/feature/t7 {local_sha} refs/heads/feature/t7 {remote_sha}\n",
        text=True, capture_output=True, env={**os.environ, "DEFAULT_BRANCH": "main"},
    )

    assert result.returncode == 2
    assert "PROTECTED_PATH" in result.stdout
    assert "scripts/legacy.py" in result.stdout


def test_pre_commit_rejects_staged_deletion_from_protected_plugin_root(tmp_path: Path) -> None:
    """The installed hook must pass a deleted protected path to the shared verifier."""

    root = tmp_path / "project"
    root.mkdir()
    shutil.copytree(REPOSITORY_ROOT / "harness_core", root / "harness_core")
    (root / "scripts").mkdir()
    for name in ("install-hooks.sh", "verify.py"):
        shutil.copy2(REPOSITORY_ROOT / "scripts" / name, root / "scripts" / name)
    (root / ".codex-plugin").mkdir()
    (root / ".codex-plugin/plugin.json").write_text("{}", encoding="utf-8")
    protected = root / "scripts/protected.py"
    protected.write_text("def protected(): pass\n", encoding="utf-8")
    _run(root, "git", "init", "-b", "feature/t7")
    _run(root, "git", "config", "user.email", "test@example.invalid")
    _run(root, "git", "config", "user.name", "Harness Test")
    _run(root, "git", "add", ".")
    _run(root, "git", "commit", "-m", "initial")
    _run(root, "bash", "scripts/install-hooks.sh")
    _run(root, "git", "rm", "scripts/protected.py")

    result = run([str(root / ".git/hooks/pre-commit")], cwd=root, text=True, capture_output=True)

    assert result.returncode == 2
    assert "PROTECTED_PATH" in result.stdout
    assert "scripts/protected.py" in result.stdout


def test_pre_commit_scans_staged_blob_not_unstaged_worktree_content(tmp_path: Path) -> None:
    """A post-stage edit must not hide a literal secret that will be committed."""
    root = tmp_path / "project"
    root.mkdir()
    shutil.copytree(REPOSITORY_ROOT / "harness_core", root / "harness_core")
    (root / "scripts").mkdir()
    for name in ("install-hooks.sh", "verify.py"):
        shutil.copy2(REPOSITORY_ROOT / "scripts" / name, root / "scripts" / name)
    _run(root, "git", "init", "-b", "feature/t7")
    _run(root, "git", "config", "user.email", "test@example.invalid")
    _run(root, "git", "config", "user.name", "Harness Test")
    (root / "README.md").write_text("initial\n", encoding="utf-8")
    _run(root, "git", "add", ".")
    _run(root, "git", "commit", "-m", "initial")
    _run(root, "bash", "scripts/install-hooks.sh")

    candidate = root / "settings.py"
    candidate.write_text('API_KEY="literal-secret-value"\n', encoding="utf-8")
    _run(root, "git", "add", "settings.py")
    candidate.write_text('API_KEY="${API_KEY}"\n', encoding="utf-8")

    result = run([str(root / ".git/hooks/pre-commit")], cwd=root, text=True, capture_output=True)

    assert result.returncode == 2
    assert "SECRET_EXPOSED" in result.stdout


def test_pre_push_scans_local_commit_blob_not_worktree_content(tmp_path: Path) -> None:
    """A mutable worktree cannot hide a secret already present in the pushed commit."""
    root = tmp_path / "project"
    root.mkdir()
    shutil.copytree(REPOSITORY_ROOT / "harness_core", root / "harness_core")
    (root / "scripts").mkdir()
    for name in ("install-hooks.sh", "verify.py"):
        shutil.copy2(REPOSITORY_ROOT / "scripts" / name, root / "scripts" / name)
    _run(root, "git", "init", "-b", "feature/t7")
    _run(root, "git", "config", "user.email", "test@example.invalid")
    _run(root, "git", "config", "user.name", "Harness Test")
    (root / "README.md").write_text("initial\n", encoding="utf-8")
    _run(root, "git", "add", ".")
    _run(root, "git", "commit", "-m", "initial")
    remote_sha = _run(root, "git", "rev-parse", "HEAD").stdout.strip()
    _run(root, "bash", "scripts/install-hooks.sh")

    candidate = root / "settings.py"
    candidate.write_text('API_KEY="literal-secret-value"\n', encoding="utf-8")
    _run(root, "git", "add", "settings.py")
    _run(root, "git", "-c", "core.hooksPath=/dev/null", "commit", "-m", "bypassed secret")
    local_sha = _run(root, "git", "rev-parse", "HEAD").stdout.strip()
    candidate.write_text('API_KEY="${API_KEY}"\n', encoding="utf-8")

    result = run(
        [str(root / ".git/hooks/pre-push")], cwd=root,
        input=f"refs/heads/feature/t7 {local_sha} refs/heads/feature/t7 {remote_sha}\n",
        text=True, capture_output=True, env={**os.environ, "DEFAULT_BRANCH": "main"},
    )

    assert result.returncode == 2
    assert "SECRET_EXPOSED" in result.stdout


def test_pre_commit_does_not_use_unstaged_tdd_evidence_for_staged_code(tmp_path: Path) -> None:
    """All gate inputs must come from the index, not a helpful worktree file."""
    root = tmp_path / "project"
    root.mkdir()
    shutil.copytree(REPOSITORY_ROOT / "harness_core", root / "harness_core")
    (root / "scripts").mkdir()
    for name in ("install-hooks.sh", "verify.py"):
        shutil.copy2(REPOSITORY_ROOT / "scripts" / name, root / "scripts" / name)
    _run(root, "git", "init", "-b", "feature/t7")
    _run(root, "git", "config", "user.email", "test@example.invalid")
    _run(root, "git", "config", "user.name", "Harness Test")
    (root / "README.md").write_text("initial\n", encoding="utf-8")
    _run(root, "git", "add", ".")
    _run(root, "git", "commit", "-m", "initial")
    _run(root, "bash", "scripts/install-hooks.sh")

    (root / "app.py").write_text("def run(): return 1\n", encoding="utf-8")
    _run(root, "git", "add", "app.py")
    manifest = root / ".harness/state/tdd-manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text('{"red_evidence":"test","green_command":"python3 -m pytest"}', encoding="utf-8")

    result = run([str(root / ".git/hooks/pre-commit")], cwd=root, text=True, capture_output=True)

    assert result.returncode == 2
    assert "TDD_EVIDENCE_MISSING" in result.stdout


def test_pre_commit_detects_type_change_to_staged_secret(tmp_path: Path) -> None:
    """A Git T status must be collected just like ordinary content edits."""
    root = tmp_path / "project"
    root.mkdir()
    shutil.copytree(REPOSITORY_ROOT / "harness_core", root / "harness_core")
    (root / "scripts").mkdir()
    for name in ("install-hooks.sh", "verify.py"):
        shutil.copy2(REPOSITORY_ROOT / "scripts" / name, root / "scripts" / name)
    _run(root, "git", "init", "-b", "feature/t7")
    _run(root, "git", "config", "user.email", "test@example.invalid")
    _run(root, "git", "config", "user.name", "Harness Test")
    (root / "target.txt").write_text("safe\n", encoding="utf-8")
    (root / "settings.py").symlink_to("target.txt")
    _run(root, "git", "add", ".")
    _run(root, "git", "commit", "-m", "initial symlink")
    _run(root, "bash", "scripts/install-hooks.sh")
    (root / "settings.py").unlink()
    (root / "settings.py").write_text('API_KEY="literal-secret-value"\n', encoding="utf-8")
    _run(root, "git", "add", "settings.py")

    result = run([str(root / ".git/hooks/pre-commit")], cwd=root, text=True, capture_output=True)

    assert result.returncode == 2
    assert "SECRET_EXPOSED" in result.stdout


def test_index_snapshot_audit_records_revision_kind_and_redacted_input_hashes(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    _run(root, "git", "init", "-b", "feature/t7")
    _run(root, "git", "config", "user.email", "test@example.invalid")
    _run(root, "git", "config", "user.name", "Harness Test")
    (root / "README.md").write_text("initial\n", encoding="utf-8")
    _run(root, "git", "add", "README.md")
    _run(root, "git", "commit", "-m", "initial")
    (root / "app.py").write_text("def run(): return 1\n", encoding="utf-8")
    manifest = root / ".harness/state/tdd-manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text('{"red_evidence":"test","green_command":"python3 -m pytest"}', encoding="utf-8")
    _run(root, "git", "add", "app.py", ".harness/state/tdd-manifest.json")

    audit = verify_local(root, source="hook", changed_files=["app.py"], branch="feature/t7", content_source="index").audit()

    assert audit["snapshot"]["kind"] == "index"
    assert audit["snapshot"]["revision"] is None
    assert len(audit["snapshot"]["input_sha256"][".harness/state/tdd-manifest.json"]) == 64
    assert "red_evidence" not in str(audit["snapshot"])


def test_pre_push_rejects_secret_in_earlier_outgoing_commit_even_if_later_deleted(tmp_path: Path) -> None:
    """Pre-push evaluates each outgoing commit, rather than only the final tree."""
    root = tmp_path / "project"
    root.mkdir()
    shutil.copytree(REPOSITORY_ROOT / "harness_core", root / "harness_core")
    (root / "scripts").mkdir()
    for name in ("install-hooks.sh", "verify.py"):
        shutil.copy2(REPOSITORY_ROOT / "scripts" / name, root / "scripts" / name)
    _run(root, "git", "init", "-b", "feature/t7")
    _run(root, "git", "config", "user.email", "test@example.invalid")
    _run(root, "git", "config", "user.name", "Harness Test")
    manifest = root / ".harness/state/tdd-manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text('{"red_evidence":"test","green_command":"python3 -m pytest"}', encoding="utf-8")
    _run(root, "git", "add", ".")
    _run(root, "git", "commit", "-m", "initial")
    remote_sha = _run(root, "git", "rev-parse", "HEAD").stdout.strip()
    _run(root, "bash", "scripts/install-hooks.sh")
    (root / "settings.py").write_text('API_KEY="literal-secret-value"\n', encoding="utf-8")
    _run(root, "git", "add", "settings.py")
    _run(root, "git", "-c", "core.hooksPath=/dev/null", "commit", "-m", "add secret")
    _run(root, "git", "rm", "settings.py")
    _run(root, "git", "-c", "core.hooksPath=/dev/null", "commit", "-m", "remove secret")
    local_sha = _run(root, "git", "rev-parse", "HEAD").stdout.strip()

    result = run(
        [str(root / ".git/hooks/pre-push")], cwd=root,
        input=f"refs/heads/feature/t7 {local_sha} refs/heads/feature/t7 {remote_sha}\n",
        text=True, capture_output=True, env={**os.environ, "DEFAULT_BRANCH": "main"},
    )

    assert result.returncode == 2
    assert "SECRET_EXPOSED" in result.stdout
