from __future__ import annotations

from pathlib import Path

from harness_core.cli import main
from harness_core.validation import classify_changed_files


FIXTURES = Path(__file__).parents[1] / "fixtures" / "validation"


def _copy_fixture(tmp_path: Path, name: str) -> Path:
    source = FIXTURES / name
    for path in source.rglob("*"):
        if path.is_file():
            target = tmp_path / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
    return tmp_path


def _check(root: Path, *files: str, branch: str = "feature/t7") -> int:
    command = [
        "preflight", "check", "--project-root", str(root), "--branch", branch,
        "--default-branch", "main",
    ]
    for file in files:
        command.extend(("--changed-file", file))
    return main(command)


def test_default_branch_implementation_is_rejected_with_remediation(
    tmp_path: Path, capsys
) -> None:
    root = _copy_fixture(tmp_path, "default_branch_implementation")

    assert _check(root, "src/service.py", branch="main") == 2
    output = capsys.readouterr().out
    assert "BRANCH_DEFAULT" in output
    assert "isolated feature branch/worktree" in output


def test_ui_change_without_e2e_evidence_is_rejected(tmp_path: Path, capsys) -> None:
    root = _copy_fixture(tmp_path, "ui_without_e2e")

    assert _check(root, "web/Panel.tsx") == 2
    output = capsys.readouterr().out
    assert "E2E_EVIDENCE_MISSING" in output
    assert "e2e-config.json" in output


def test_exposed_secret_is_rejected_with_remediation(tmp_path: Path, capsys) -> None:
    root = _copy_fixture(tmp_path, "exposed_secret")

    assert _check(root, "src/settings.py") == 2
    output = capsys.readouterr().out
    assert "SECRET_EXPOSED" in output
    assert "approved secret reference" in output


def test_unquoted_export_and_colon_secret_forms_are_rejected(tmp_path: Path, capsys) -> None:
    root = _copy_fixture(tmp_path, "exposed_secret_forms")

    for name in ("api_key.env", "export_api_key.env", "password.yaml"):
        assert _check(root, name) == 2
        assert "SECRET_EXPOSED" in capsys.readouterr().out


def test_secret_scanner_allows_environment_references_and_placeholders(tmp_path: Path, capsys) -> None:
    root = _copy_fixture(tmp_path, "secret_references")

    assert _check(root, "settings.env") == 0
    assert "PREFLIGHT_OK" in capsys.readouterr().out


def test_valid_evidence_allows_feature_branch_change(tmp_path: Path, capsys) -> None:
    root = _copy_fixture(tmp_path, "valid_change")

    assert _check(root, "src/service.py", "web/Panel.tsx") == 0
    assert "PREFLIGHT_OK: enforcement" in capsys.readouterr().out


def test_protected_path_requires_explicit_review_override(tmp_path: Path, capsys) -> None:
    root = _copy_fixture(tmp_path, "protected_path")

    assert _check(root, "infra/deploy.yml") == 2
    assert "PROTECTED_PATH" in capsys.readouterr().out
    assert main([
        "preflight", "check", "--project-root", str(root), "--branch", "feature/t7",
        "--default-branch", "main", "--changed-file", "infra/deploy.yml",
        "--allow-protected-path", "infra/deploy.yml",
    ]) == 0


def test_changed_file_classification_is_deterministic() -> None:
    kinds = classify_changed_files(
        [Path("docs/guide.md"), Path("web/Panel.tsx"), Path("src/service.py")], ["infra"]
    )

    assert kinds.implementation == (Path("web/Panel.tsx"), Path("src/service.py"))
    assert kinds.ui == (Path("web/Panel.tsx"),)
    assert kinds.protected == ()


def test_changed_files_list_is_supported(tmp_path: Path, capsys) -> None:
    root = _copy_fixture(tmp_path, "valid_change")
    changed = root / "changed.txt"
    changed.write_text("src/service.py\nweb/Panel.tsx\n", encoding="utf-8")

    assert main([
        "preflight", "check", "--project-root", str(root), "--branch", "feature/t7",
        "--default-branch", "main", "--changed-files-file", str(changed),
    ]) == 0
    assert "PREFLIGHT_OK" in capsys.readouterr().out
