"""Acceptance tests for the package-relative installed-plugin runtime."""

from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys

import pytest

from harness_core.pr import revision_key


ROOT = Path(__file__).resolve().parents[1]
ACTIVE_SURFACE = json.loads(
    (ROOT / "skills/ACTIVE_SURFACE.json").read_text(encoding="utf-8")
)


def _install_active_archive(destination: Path) -> Path:
    """Materialize the manifest plus its complete classified runtime archive."""
    files = [".codex-plugin/plugin.json", *ACTIVE_SURFACE["included"]]
    for relative in files:
        source = ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return destination / "skills/sdd/runtime/moondex-runtime.py"


def _snapshot(root: Path) -> dict[str, tuple[str, int, bytes | str]]:
    snapshot = {}
    if not root.exists():
        return snapshot
    for path in [root, *sorted(root.rglob("*"))]:
        relative = "." if path == root else path.relative_to(root).as_posix()
        mode = stat.S_IMODE(path.lstat().st_mode)
        if path.is_symlink():
            snapshot[relative] = ("symlink", mode, os.readlink(path))
        elif path.is_dir():
            snapshot[relative] = ("directory", mode, "")
        else:
            snapshot[relative] = ("file", mode, path.read_bytes())
    return snapshot


def _invoke(runtime: Path, consumer: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    for name in (
        "PYTHONPATH",
        "HARNESS_HOOKS",
        "CODEX_PLUGIN_ROOT",
        "CLAUDE_PLUGIN_ROOT",
        "GITHUB_TOKEN",
        "GH_TOKEN",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
    ):
        environment.pop(name, None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, str(runtime), *arguments],
        cwd=consumer,
        env=environment,
        check=False,
        text=True,
        capture_output=True,
    )


def _successful(runtime: Path, consumer: Path, *arguments: str) -> str:
    result = _invoke(runtime, consumer, *arguments)
    assert result.returncode == 0, result.stderr or result.stdout
    return result.stdout + result.stderr


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _rebind_inventory(installation: Path, relative: str) -> None:
    inventory_path = installation / "skills/sdd/runtime/runtime-inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    content = (installation / relative).read_bytes()
    entry = next(item for item in inventory["files"] if item["path"] == relative)
    entry["size"] = len(content)
    entry["sha256"] = hashlib.sha256(content).hexdigest()
    inventory_path.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")


def test_installed_runtime_operates_from_unrelated_consumer_without_pythonpath(
    tmp_path: Path,
) -> None:
    installation = tmp_path / "opaque-plugin-install"
    consumer = tmp_path / "unrelated-consumer"
    consumer.mkdir()
    runtime = _install_active_archive(installation)
    installed_before = _snapshot(installation)
    consumer_before = _snapshot(consumer)
    output = []

    output.append(_successful(runtime, consumer, "--help"))
    retired = _invoke(runtime, consumer, "state", "--project-root", ".", "start", "portable-install")
    assert retired.returncode == 2
    assert json.loads(retired.stdout)["code"] == "LEGACY_WORKFLOW_RETIRED"
    bundle = json.loads((ROOT / "tests/fixtures/execution/bundle.json").read_text())
    _write_json(consumer / "bundle.json", bundle)
    prepared = json.loads(_successful(runtime, consumer, "execute", "prepare", "--file", "bundle.json"))
    _successful(runtime, consumer, "execute", "approve", "--digest", prepared["digest"], "--quote", "Implement fixture", "--source", "test user")
    assignment = json.loads(_successful(runtime, consumer, "execute", "advance"))
    (consumer / "src").mkdir()
    (consumer / "src/value.txt").write_text("42")
    submission = {k: assignment[k] for k in ("node_id", "attempt_id", "bundle", "action_key")}
    submission.update(summary="Value saved", criteria_review={"C1": "Value is 42; actual gate verifies it"})
    _write_json(consumer / "submission.json", submission)
    _successful(runtime, consumer, "execute", "submit", "--file", "submission.json")

    _write_json(
        consumer / ".harness/state/tdd-manifest.json",
        {"red_evidence": "test", "green_command": "python3 -m pytest"},
    )
    _write_json(
        consumer / ".harness/state/e2e-config.json",
        {"command": "npm test:e2e"},
    )
    (consumer / "safe.py").write_text("def safe(): return True\n", encoding="utf-8")
    output.append(
        _successful(
            runtime,
            consumer,
            "verify",
            "--project-root",
            ".",
            "--branch",
            "feature/runtime",
            "--default-branch",
            "main",
            "--source",
            "explicit",
            "--changed-file",
            "safe.py",
        )
    )

    graph_payload = {
        "status": "ready",
        "entry_points": ["safe.py"],
        "candidate_calls": ["safe"],
        "impact_scope": ["safe.py"],
    }
    graph_command = json.dumps(
        ["python3", "-c", f"import json; print(json.dumps({graph_payload!r}))"]
    )
    mapped = json.loads(
        _successful(
            runtime,
            consumer,
            "code-mapper",
            "--root",
            ".",
            "--symbol",
            "safe",
            "--graph-command",
            graph_command,
        )
    )
    assert mapped["status"] == "OK" and mapped["mode"] == "graph"

    _write_json(consumer / ".harness/learning.json", [{"lesson": "portable"}])
    _write_json(consumer / "proposed-paths.json", ["safe.py"])
    improved = json.loads(
        _successful(
            runtime,
            consumer,
            "self-improve",
            "--repository-root",
            ".",
            "--entries",
            ".harness/learning.json",
            "--paths",
            "proposed-paths.json",
        )
    )
    assert improved["status"] == "OK"

    body = "please keep the installed runtime portable"
    comment = {
        "schema_version": 1,
        "source": "inline",
        "source_identity": "installed:1",
        "comment_id": "1",
        "revision_identity": "r1",
        "body_hash": hashlib.sha256(body.encode()).hexdigest(),
        "author": "reviewer",
        "body": body,
        "created_at": "2026-07-30T00:00:00Z",
        "path": "safe.py",
        "line": 1,
    }
    _write_json(
        consumer / ".harness/review-collection.json",
        {
            "schema_version": 1,
            "input_identity": "installed-review",
            "complete": True,
            "comments": [comment],
        },
    )
    _write_json(
        consumer / ".harness/review-evidence.json",
        {
            revision_key(comment): {
                "actionability": "ACTIONABLE",
                "alignment": {
                    "spec": "ALIGNS",
                    "design": "ALIGNS",
                    "ownership": "OWNED",
                    "verification": "AVAILABLE",
                },
                "validation_plan": ["installed verification"],
                "changed_files": ["safe.py"],
                "repository_root": str(consumer.resolve()),
                "validation": [{"command": "verify", "passed": True}],
                "evidence": [{"note": "installed runtime"}],
            }
        },
    )
    passing_command = json.dumps(["python3", "-c", "raise SystemExit(0)"])
    converged = json.loads(
        _successful(
            runtime,
            consumer,
            "pr-converge",
            "--repository-root",
            ".",
            "--collection",
            ".harness/review-collection.json",
            "--evidence",
            ".harness/review-evidence.json",
            "--audit",
            ".harness/audit/review.jsonl",
            "--report",
            ".harness/reports/review.json",
            "--build-command",
            passing_command,
            "--lint-command",
            passing_command,
            "--test-command",
            passing_command,
        )
    )
    assert converged["status"] == "CONVERGED"

    import time
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        outcome = json.loads(_successful(runtime, consumer, "execute", "resume"))
        if outcome.get("kind") == "integration_review":
            _write_json(consumer / "review.json", {"kind": "integration_review", "action_key": outcome["action_key"], "summary": "Observed installed gates", "criteria_review": {"C1": "The actual value and failing off-by-one were checked"}})
            _successful(runtime, consumer, "execute", "submit", "--file", "review.json")
        if outcome["code"] == "COMPLETED":
            break
        time.sleep(.025)
    assert outcome["code"] == "COMPLETED", outcome
    assert (consumer / outcome["report"]).is_file()
    assert (consumer / ".moondex/STATE.json").is_file()
    assert not (consumer / ".harness/state/pipeline.json").exists()
    assert not (installation / ".harness").exists()
    assert _snapshot(installation) == installed_before
    consumer_after = _snapshot(consumer)
    assert consumer_before == {".": consumer_after["."]}
    assert any(kind == "directory" for kind, _, _ in consumer_after.values())
    assert any(kind == "file" for kind, _, _ in consumer_after.values())
    assert not any(kind == "symlink" for kind, _, _ in consumer_after.values())
    rendered = "\n".join(output)
    assert str(ROOT) not in rendered
    assert str(installation) not in rendered
    assert "/Users/" not in rendered


@pytest.mark.parametrize(
    "case",
    (
        "missing-pipeline",
        "missing-storage",
        "missing-redactor",
        "hash-modification",
        "wrong-type",
        "symlink",
        "manifest-name",
        "manifest-version",
        "inventory-mode-0666",
        "inventory-mode-0620",
        "manifest-mode-0666",
        "manifest-mode-0620",
        "import-error",
    ),
)
def test_installed_runtime_tamper_matrix_fails_closed_without_mutation(
    tmp_path: Path, case: str,
) -> None:
    installation = tmp_path / f"incomplete-{case}"
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    runtime = _install_active_archive(installation)
    command = ("state", "--project-root", ".", "status", "portable-install")
    if case.startswith("missing-"):
        relative = {
            "missing-pipeline": "harness_core/state/pipeline.py",
            "missing-storage": "harness_core/state/storage.py",
            "missing-redactor": "scripts/adapter_render.py",
        }[case]
        (installation / relative).unlink()
    elif case == "hash-modification":
        path = installation / "harness_core/config.py"
        path.write_bytes(path.read_bytes() + b"\n# tampered\n")
    elif case == "wrong-type":
        path = installation / "harness_core/learning/__init__.py"
        path.unlink()
        path.mkdir()
    elif case == "symlink":
        path = installation / "scripts/adapter_render.py"
        path.unlink()
        path.symlink_to("../harness_core/config.py")
    elif case in {"manifest-name", "manifest-version"}:
        manifest_path = installation / ".codex-plugin/plugin.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["name" if case == "manifest-name" else "version"] = "tampered"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        _rebind_inventory(installation, ".codex-plugin/plugin.json")
    elif case.startswith("inventory-mode-"):
        mode = 0o666 if case.endswith("0666") else 0o620
        (installation / "skills/sdd/runtime/runtime-inventory.json").chmod(mode)
    elif case.startswith("manifest-mode-"):
        mode = 0o666 if case.endswith("0666") else 0o620
        (installation / ".codex-plugin/plugin.json").chmod(mode)
    else:
        path = installation / "harness_core/code_mapper/__init__.py"
        path.write_bytes(path.read_bytes() + b"\nraise RuntimeError('injected import failure')\n")
        _rebind_inventory(installation, "harness_core/code_mapper/__init__.py")
        command = ("code-mapper", "--root", ".", "--symbol", "portable")

    install_baseline = _snapshot(installation)
    consumer_baseline = _snapshot(consumer)
    result = _invoke(runtime, consumer, *command)

    assert result.returncode == 2
    assert "MOONDEX_RUNTIME_INCOMPLETE" in result.stderr
    rendered = result.stdout + result.stderr
    assert "Traceback" not in rendered
    assert str(ROOT) not in rendered
    assert str(installation) not in rendered
    assert str(consumer) not in rendered
    assert "/Users/" not in rendered
    assert _snapshot(installation) == install_baseline
    assert _snapshot(consumer) == consumer_baseline


@pytest.mark.parametrize("mode", (0o600, 0o644))
def test_installed_runtime_accepts_safe_inventory_modes(
    tmp_path: Path, mode: int,
) -> None:
    installation = tmp_path / f"safe-mode-{mode:o}"
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    runtime = _install_active_archive(installation)
    (installation / "skills/sdd/runtime/runtime-inventory.json").chmod(mode)
    install_baseline = _snapshot(installation)
    consumer_baseline = _snapshot(consumer)

    result = _invoke(runtime, consumer, "--help")

    assert result.returncode == 0
    assert "MOONDEX_RUNTIME_INCOMPLETE" not in result.stderr
    assert _snapshot(installation) == install_baseline
    assert _snapshot(consumer) == consumer_baseline


def test_installed_runtime_preserves_adapter_blocked_exit_semantics(tmp_path: Path) -> None:
    installation = tmp_path / "adapter-exit"
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    runtime = _install_active_archive(installation)

    result = _invoke(runtime, consumer, "code-mapper", "--root", ".", "--symbol", "absent")

    assert result.returncode == 2
    assert "MOONDEX_RUNTIME_INCOMPLETE" not in result.stderr
    assert json.loads(result.stdout)["status"] == "BLOCKED"
