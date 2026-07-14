from pathlib import Path
from subprocess import run

def test_portable_skills_exist() -> None:
    for name in ("self-improve", "pr-converge", "code-mapper"):
        assert (Path("skills") / name / "SKILL.md").is_file()

def test_verifier_rejects_secret(tmp_path: Path) -> None:
    path = tmp_path / "x.py"; path.write_text('API_KEY="abcdefghi"', encoding="utf-8")
    result = run(["python3", "scripts/verify.py", str(path)], capture_output=True, text=True)
    assert result.returncode == 2 and "possible secret" in result.stdout
