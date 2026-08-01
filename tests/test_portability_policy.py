"""Observable portability policy for the public Moondex plugin surface."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / ".codex-plugin/plugin.json"
MARKETPLACE = ROOT / ".codex-plugin/marketplace.json"
PUBLIC_DOCS = (ROOT / "README.md", ROOT / "AGENTS.md")
ACTIVE_SURFACE = json.loads(
    (ROOT / "skills/ACTIVE_SURFACE.json").read_text(encoding="utf-8")
)


def _installed_plugin(tmp_path: Path) -> tuple[Path, Path, Path]:
    installation = tmp_path / "installed-plugin"
    consumer = tmp_path / "unrelated-consumer"
    consumer.mkdir()
    for relative in [".codex-plugin/plugin.json", *ACTIVE_SURFACE["included"]]:
        source = ROOT / relative
        target = installation / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    runtime = installation / "skills/sdd/runtime/moondex-runtime.py"
    return installation, consumer, runtime


def _state(runtime: Path, project: Path, *arguments: str) -> dict[str, object]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("HARNESS_" + "HOOKS", None)
    env.pop("CODEX_" + "PLUGIN_ROOT", None)
    env.pop("CLAUDE_" + "PLUGIN_ROOT", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [
            sys.executable,
            str(runtime),
            "state",
            "--project-root",
            ".",
            *arguments,
        ],
        cwd=project,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _marked_python_block(marker: str) -> str:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    match = re.search(
        rf"<!-- {re.escape(marker)} -->\n```python\n(?P<code>.*?)\n```",
        readme,
        re.DOTALL,
    )
    assert match is not None
    return match.group("code")


def test_manifest_is_moondex_skills_only_and_marketplace_is_aligned() -> None:
    manifest = json.loads(PLUGIN.read_text(encoding="utf-8"))
    allowed = {
        "name",
        "version",
        "description",
        "author",
        "homepage",
        "repository",
        "license",
        "keywords",
        "skills",
        "interface",
    }
    assert set(manifest) <= allowed
    assert manifest["name"] == "moondex"
    assert manifest["skills"] == "./skills/"
    assert re.fullmatch(r"\d+\.\d+\.\d+", manifest["version"])
    assert not ({"hooks", "apps", "mcpServers"} & set(manifest))
    assert all(prompt.startswith("$moondex:") for prompt in manifest["interface"]["defaultPrompt"])

    marketplace = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
    assert marketplace["name"] == "moondex"
    assert marketplace["interface"]["displayName"] == "Moondex"
    assert len(marketplace["plugins"]) == 1
    entry = marketplace["plugins"][0]
    assert entry["name"] == manifest["name"]
    assert entry["source"] == {"source": "local", "path": "../"}
    assert entry["policy"] == {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL",
    }
    assert entry["category"] == "Productivity"
    assert (MARKETPLACE.parent / entry["source"]["path"]).resolve() == ROOT.resolve()


def test_every_manifest_skill_is_discoverable_and_has_codex_frontmatter() -> None:
    manifest = json.loads(PLUGIN.read_text(encoding="utf-8"))
    skill_root = (ROOT / manifest["skills"]).resolve()
    assert skill_root == (ROOT / "skills").resolve()
    skills = sorted(skill_root.glob("*/SKILL.md"))
    assert skills
    for skill in skills:
        text = skill.read_text(encoding="utf-8")
        assert text.startswith("---\n")
        assert re.search(r"(?m)^name:\s*\S", text)
        assert re.search(r"(?m)^description:\s*.+", text)


def test_user_facing_surface_has_no_host_or_private_runtime_assumptions() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in PUBLIC_DOCS)
    forbidden = (
        "HARNESS_" + "HOOKS",
        "CODEX_" + "PLUGIN_ROOT",
        "CLAUDE_" + "PLUGIN_ROOT",
        "pipeline-" + "utils.sh",
        "/Users/",
        "~/.agents",
        "~/.claude",
        "Stop " + "hook",
        "Stop " + "훅",
    )
    # ~/.agents is the documented canonical personal marketplace, not a
    # runtime dependency or a hardcoded private installation.
    forbidden = tuple(token for token in forbidden if token != "~/.agents")
    assert not [token for token in forbidden if token in text]
    assert "모든 스킬, 에이전트, 훅이 자동 활성화" not in text
    assert "개인 경로나 조직 destination의 기본값은 없습니다." in text
    claude_lines = [line for line in text.splitlines() if "Claude" in line or "claude" in line]
    assert claude_lines
    assert all("Claude Design" in line or "claude-design" in line for line in claude_lines)


def test_readme_documents_installed_controller_first_observable_flow(tmp_path: Path) -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    consumer_docs = readme.split("## 플러그인 개발자 전용", 1)[0]
    assert "$moondex:sdd start <feature>" in consumer_docs
    assert "<moondex-runtime>" in consumer_docs
    assert "PYTHONPATH`를 직접 다루지" in consumer_docs
    assert "PYTHONPATH=" not in consumer_docs
    assert "python3 -m harness_core" not in consumer_docs
    assert not re.search(r"python3 (?:scripts/|skills/)", consumer_docs)
    assert "checkout 루트" in readme.split("## 플러그인 개발자 전용", 1)[1]
    assert "WAITING_USER" in readme
    assert "ADVISORY_UNAVAILABLE" in readme
    assert "status`와 `resume`은 읽기 전용" in readme

    installation, consumer, runtime = _installed_plugin(tmp_path)
    started = _state(runtime, consumer, "start", "portable-doc-flow")
    state_path = consumer / ".harness/state/pipeline.json"
    before = state_path.read_bytes()
    status = _state(runtime, consumer, "status", "portable-doc-flow")
    resumed = _state(runtime, consumer, "resume", "portable-doc-flow")
    assert started["state"]["feature"] == "portable-doc-flow"
    assert status == resumed
    assert state_path.read_bytes() == before
    assert not (installation / ".harness").exists()

    spec = consumer / "docs/sdd/spec/2026-07-24-portable-doc-flow.md"
    spec.parent.mkdir(parents=True)
    spec.write_text("# Portable spec\n", encoding="utf-8")
    waiting = _state(runtime, consumer, "resume", "portable-doc-flow")
    assert waiting["code"] == "WAITING_USER"
    waiting_bytes = state_path.read_bytes()
    denied = _state(
        runtime,
        consumer,
        "transition",
        "--feature",
        "portable-doc-flow",
        "--expected",
        "SPEC",
        "--target",
        "DESIGN",
    )
    assert denied["code"] == "BLOCKED_APPROVAL"
    assert state_path.read_bytes() == waiting_bytes
    approved = _state(
        runtime,
        consumer,
        "transition",
        "--feature",
        "portable-doc-flow",
        "--expected",
        "SPEC",
        "--target",
        "DESIGN",
        "--approve",
        "spec",
    )
    assert approved["code"] == "ACTION"
    assert approved["state"]["phase"] == "DESIGN"

    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    agent_user_map = agents.split("## Plugin-development Validation", 1)[0]
    assert "$moondex:sdd" in agent_user_map
    assert not re.search(r"(?m)^python3 -m harness_core", agent_user_map)
    assert "checkout cwd" in agent_user_map and "`PYTHONPATH`" in agent_user_map


def test_documented_repo_marketplace_deeplink_uses_current_clone_absolute_path(
    tmp_path: Path,
) -> None:
    clone = tmp_path / "clone %2F anywhere"
    (clone / ".codex-plugin").mkdir(parents=True)
    shutil.copy2(MARKETPLACE, clone / ".codex-plugin/marketplace.json")
    result = subprocess.run(
        [sys.executable, "-c", _marked_python_block("repo-marketplace-deeplink")],
        cwd=clone,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    links = [line.split(": ", 1)[1] for line in result.stdout.splitlines()]
    assert len(links) == 2
    view = urlparse(links[0])
    share = urlparse(links[1])
    expected = str((clone / ".codex-plugin/marketplace.json").resolve())
    assert view.scheme == "codex" and view.netloc == "plugins" and view.path == "/moondex"
    assert parse_qs(view.query)["marketplacePath"] == [expected]
    assert parse_qs(share.query)["mode"] == ["share"]
    assert parse_qs(share.query)["marketplacePath"] == [expected]
    assert str(ROOT) not in result.stdout


def test_documented_personal_marketplace_setup_is_canonical_in_fixture(
    tmp_path: Path,
) -> None:
    clone = tmp_path / "clone"
    clone.mkdir()
    home = tmp_path / "home %2F with space"
    home.mkdir()
    environment = os.environ.copy()
    environment["HOME"] = str(home)
    marketplace = home / ".agents/plugins/marketplace.json"
    marketplace.parent.mkdir(parents=True)
    unrelated = {
        "name": "unrelated-tool",
        "source": {"source": "local", "path": "./plugins/unrelated-tool"},
        "policy": {
            "installation": "INSTALLED_BY_DEFAULT",
            "authentication": "ON_USE",
        },
        "category": "Developer Tools",
        "opaque": {"order": [3, 1, 2], "literal": "%2F keep this"},
    }
    seeded_metadata = {
        "name": "moon-personal",
        "interface": {
            "displayName": "Moon Personal",
            "customTheme": "night",
        },
        "catalogMetadata": {
            "owner": "moon",
            "notes": "preserve semantic content and %2F literals",
        },
    }
    stale_moondex = {
        "name": "moondex",
        "source": {"source": "local", "path": "./obsolete/moondex"},
        "policy": {
            "installation": "NOT_AVAILABLE",
            "authentication": "ON_USE",
        },
        "category": "Obsolete",
        "stale": True,
    }
    seeded_document = {
        **seeded_metadata,
        "plugins": [unrelated, stale_moondex],
    }
    marketplace.write_text(
        json.dumps(seeded_document, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-c", _marked_python_block("personal-marketplace-setup")],
        cwd=clone,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    plugin = home / "plugins/moondex"
    assert plugin.is_symlink() and plugin.resolve() == clone.resolve()
    document = json.loads(marketplace.read_text(encoding="utf-8"))
    assert {key: document[key] for key in seeded_metadata} == seeded_metadata
    assert document["plugins"][0] == unrelated
    moondex_entries = [
        item for item in document["plugins"] if item["name"] == "moondex"
    ]
    assert len(moondex_entries) == 1
    assert moondex_entries[0] == {
        "name": "moondex",
        "source": {"source": "local", "path": "./plugins/moondex"},
        "policy": {
            "installation": "AVAILABLE",
            "authentication": "ON_INSTALL",
        },
        "category": "Productivity",
    }
    assert document["plugins"] == [unrelated, moondex_entries[0]]
    assert moondex_entries[0]["policy"] == {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL",
    }
    links = [line.split(": ", 1)[1] for line in result.stdout.splitlines()]
    assert len(links) == 2
    expected = str(marketplace.resolve())
    view = urlparse(links[0])
    share = urlparse(links[1])
    assert parse_qs(view.query)["marketplacePath"] == [expected]
    assert parse_qs(share.query)["marketplacePath"] == [expected]
    assert parse_qs(share.query)["mode"] == ["share"]

    before = marketplace.read_bytes()
    repeated = subprocess.run(
        [sys.executable, "-c", _marked_python_block("personal-marketplace-setup")],
        cwd=clone,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert repeated.returncode == 0
    assert marketplace.read_bytes() == before
    assert plugin.is_symlink() and plugin.resolve() == clone.resolve()

    conflict_home = tmp_path / "conflict-home"
    conflict = conflict_home / "plugins/moondex"
    conflict.mkdir(parents=True)
    conflict_marketplace = conflict_home / ".agents/plugins/marketplace.json"
    conflict_marketplace.parent.mkdir(parents=True)
    conflict_seed = b'{"name":"existing","plugins":[{"name":"keep"}]}\n'
    conflict_marketplace.write_bytes(conflict_seed)
    conflict_environment = environment.copy()
    conflict_environment["HOME"] = str(conflict_home)
    rejected = subprocess.run(
        [sys.executable, "-c", _marked_python_block("personal-marketplace-setup")],
        cwd=clone,
        env=conflict_environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert rejected.returncode != 0
    assert "refusing to replace existing destination" in rejected.stderr
    assert conflict_marketplace.read_bytes() == conflict_seed

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    handoff = readme.split("<!-- personal-marketplace-setup -->", 1)[1].split(
        "## 사용자 실행", 1
    )[0]
    assert "AVAILABLE" in handoff
    assert "View moondex" in handoff
    assert "Codex 앱" in handoff
    assert "Install/Enable" in handoff
    assert "완료" in handoff


def test_docs_describe_real_profiles_data_boundaries_and_optional_extensions() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in PUBLIC_DOCS)
    required = (
        "agents/`는",
        ".harness/state/",
        ".harness/audit/",
        ".harness/reports/",
        "SAFE_FIX",
        "REJECTED",
        "ESCALATED",
        "SYNC_SKIPPED",
        "SYNC_APPLIED",
        "result-action.py",
        "scripts/install-hooks.sh",
        "moondex-verify",
    )
    assert not [term for term in required if term not in text]
    assert "원격 CI나 게시 기능은 로컬 baseline의 전제조건이 아닙니다." in text
    assert "개인 경로나 조직 destination의 기본값은 없습니다." in text
