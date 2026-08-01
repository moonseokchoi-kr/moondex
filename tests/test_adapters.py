from pathlib import Path
from subprocess import run

def test_portable_skills_exist() -> None:
    for name in ("self-improve", "pr-converge", "code-mapper"):
        assert (Path("skills") / name / "SKILL.md").is_file()

def test_verifier_rejects_secret(tmp_path: Path) -> None:
    path = tmp_path / "x.py"; path.write_text('API_KEY="abcdefghi"', encoding="utf-8")
    result = run(
        ["python3", "scripts/verify.py", "--project-root", str(tmp_path), str(path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2 and "possible secret" in result.stdout


def test_verifier_absolute_plugin_path_keeps_git_root_protection(tmp_path: Path) -> None:
    """An absolute legacy path cannot make ``scripts/`` its own project root."""
    root = tmp_path / "plugin"
    nested = root / "nested" / "invocation"
    protected = root / "scripts" / "verify.py"
    (root / ".codex-plugin").mkdir(parents=True)
    nested.mkdir(parents=True)
    protected.parent.mkdir()
    (root / ".codex-plugin" / "plugin.json").write_text("{}", encoding="utf-8")
    protected.write_text("def verify(): pass\n", encoding="utf-8")
    (root / ".harness/state").mkdir(parents=True)
    (root / ".harness/state/tdd-manifest.json").write_text(
        '{"red_evidence":"test","green_command":"python3 -m pytest"}', encoding="utf-8",
    )
    (root / ".harness/state/e2e-config.json").write_text('{"command":"npm test:e2e"}', encoding="utf-8")
    run(["git", "init", "-b", "feature/t7", str(root)], check=True, capture_output=True, text=True)

    verifier = Path(__file__).resolve().parents[1] / "scripts" / "verify.py"
    result = run(["python3", str(verifier), str(protected)], cwd=nested, capture_output=True, text=True)

    assert result.returncode == 2
    assert "PROTECTED_PATH" in result.stdout
