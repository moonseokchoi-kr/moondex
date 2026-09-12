"""Execute the workflow's actual outgoing-range CLI on a disposable Git history."""
import json
import subprocess
import sys
from pathlib import Path


def test_ci_range_command_uses_supported_cli_and_writes_real_audit(tmp_path):
    def git(*args):
        return subprocess.run(["git", *args], cwd=tmp_path, capture_output=True, text=True, check=True).stdout.strip()
    git("init", "-b", "main")
    git("config", "user.name", "Fixture")
    git("config", "user.email", "fixture@example.invalid")
    (tmp_path / "README.md").write_text("base\n")
    git("add", "README.md"); git("-c", "core.hooksPath=/dev/null", "commit", "-m", "base")
    base = git("rev-parse", "HEAD")
    git("checkout", "-b", "feature/docs")
    (tmp_path / "docs").mkdir(); (tmp_path / "docs/change.md").write_text("documented behavior\n")
    git("add", "docs/change.md"); git("-c", "core.hooksPath=/dev/null", "commit", "-m", "docs")
    tip = git("rev-parse", "HEAD")
    audit = tmp_path / ".harness/reports/ci.json"
    result = subprocess.run([sys.executable, "-m", "harness_core", "preflight", "enforce", "--project-root", str(tmp_path),
                             "--source", "ci", "--target-ref", "refs/heads/feature/docs", "--tip", tip, "--remote-base", base,
                             "--policy-base", base, "--trusted-policy", "--branch", "feature/docs", "--default-branch", "main", "--audit-file", str(audit)],
                            cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(audit.read_text())
    assert report["status"] == "PASS"
