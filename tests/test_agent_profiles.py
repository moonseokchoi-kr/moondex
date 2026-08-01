"""Policy checks for controller-first active SDD instructions."""

import ast
import hashlib
import importlib.machinery
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_MANIFEST = json.loads(
    (ROOT / ".codex-plugin/plugin.json").read_text(encoding="utf-8")
)
MANIFEST_SKILL_ROOT = (ROOT / PLUGIN_MANIFEST["skills"]).resolve()
ACTIVE_MANIFEST_SKILL_FILES = sorted(MANIFEST_SKILL_ROOT.glob("*/SKILL.md"))
ACTIVE_SURFACE_CLASSIFICATION = json.loads(
    (ROOT / "skills/ACTIVE_SURFACE.json").read_text(encoding="utf-8")
)
ACTIVE_REACHABLE_FILES = [
    ROOT / relative for relative in ACTIVE_SURFACE_CLASSIFICATION["included"]
]
ACTIVE = [
    ROOT / "skills/sdd/SKILL.md",
    ROOT / "skills/sdd-orchestrator/SKILL.md",
]
PROFILE_MANIFEST = json.loads(
    (ROOT / "agents/PROFILE_MANIFEST.json").read_text(encoding="utf-8")
)
ACTIVE_PROFILES = [ROOT / "agents" / name for name in PROFILE_MANIFEST["active"]]
ACTIVE_PORTABILITY_SURFACE_FILES = [
    *ACTIVE_REACHABLE_FILES,
    *ACTIVE_PROFILES,
]


def _local_module_files(repository: Path, importer: Path, module: str, level: int) -> list[Path]:
    """Resolve one import to repo files, rejecting ambiguous local module identities."""
    relative = importer.relative_to(repository)
    if level:
        package = list(relative.parent.parts)
        if level > len(package):
            raise AssertionError(f"relative import escapes repository package: {importer}")
        base = package[: len(package) - level + 1]
        parts = [*base, *(module.split(".") if module else [])]
        raw_candidates = [
            repository.joinpath(*parts).with_suffix(".py"),
            repository.joinpath(*parts, "__init__.py"),
        ]
    else:
        parts = module.split(".")
        raw_candidates = [
            repository.joinpath(*parts).with_suffix(".py"),
            repository.joinpath(*parts, "__init__.py"),
        ]
        if len(parts) == 1:
            raw_candidates.extend(
                [importer.parent / f"{module}.py", importer.parent / module / "__init__.py"]
            )
    targets = []
    for candidate in raw_candidates:
        if candidate.is_file() and candidate not in targets:
            targets.append(candidate)
    terminal_targets = [
        path for path in targets
        if path.name != "__init__.py" or path.parent.name == parts[-1]
    ]
    terminal_identities = {path.resolve() for path in terminal_targets}
    if len(terminal_identities) > 1:
        raise AssertionError(
            f"ambiguous local module {module!r} imported by {importer}: {terminal_targets}"
        )
    if not targets:
        return []
    target = terminal_targets[0] if terminal_targets else targets[0]
    dependencies = []
    target_relative = target.relative_to(repository)
    directories = target_relative.parts[:-1]
    for index in range(1, len(directories) + 1):
        package_init = repository.joinpath(*directories[:index], "__init__.py")
        if package_init.is_file() and package_init not in dependencies:
            dependencies.append(package_init)
    if target not in dependencies:
        dependencies.append(target)
    return dependencies


def _external_module_resolves(repository: Path, importer: Path, module: str) -> bool:
    top_level = module.split(".", 1)[0]
    if importlib.machinery.BuiltinImporter.find_spec(top_level) is not None:
        return True
    if importlib.machinery.FrozenImporter.find_spec(top_level) is not None:
        return True
    search = []
    for entry in sys.path:
        candidate = Path(entry or os.getcwd()).resolve()
        if candidate == repository or repository in candidate.parents:
            continue
        if candidate == importer.parent.resolve():
            continue
        search.append(str(candidate))
    return importlib.machinery.PathFinder.find_spec(top_level, search) is not None


def _repo_import_dependencies(repository: Path, path: Path) -> list[Path]:
    dependencies = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports = [(alias.name, 0, True) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                imports = [
                    (alias.name, node.level, True)
                    for alias in node.names
                    if alias.name != "*"
                ]
            else:
                # The base is always imported. A named member may additionally be
                # a submodule (``from package import module``); include it when
                # present, but do not mistake a normal exported attribute for a
                # missing module.
                imports = [(node.module, node.level, True)]
                imports.extend(
                    (f"{node.module}.{alias.name}", node.level, False)
                    for alias in node.names
                    if alias.name != "*"
                )
        else:
            continue
        for module, level, required in imports:
            local = _local_module_files(repository, path, module, level)
            if local:
                dependencies.extend(item for item in local if item not in dependencies)
            elif required and (
                level or not _external_module_resolves(repository, path, module)
            ):
                raise AssertionError(f"missing local or external module {module!r} imported by {path}")
    return dependencies
# Retain the old local name so every existing policy assertion now scans the
# manifest-defined active universe, not a filename-prefix subset.
ACTIVE_SDD_PROFILES = ACTIVE_PROFILES
ARCHIVED_PROFILE_FILES = [
    ROOT / "agents" / name for name in PROFILE_MANIFEST["archived"]
]
ACTIVE_SDD_SOURCE_EXTENSIONS = {".md", ".py", ".sh", ".json", ".txt", ".toml", ".yaml", ".yml"}


def active_sdd_package_files() -> list[Path]:
    """Inventory executable/text policy surfaces, never runtime bytecode artifacts."""
    return sorted(
        path
        for package in (ROOT / "skills/sdd", ROOT / "skills/sdd-orchestrator")
        for path in package.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix.casefold() in ACTIVE_SDD_SOURCE_EXTENSIONS
    )


ACTIVE_SDD_PACKAGE_FILES = active_sdd_package_files()
ACTIVE_SDD_REFERENCE_FILES = sorted(
    path
    for path in ACTIVE_SDD_PACKAGE_FILES
    if "references" in path.relative_to(ROOT).parts
)
ARCHIVED_SDD_ROOT = ROOT / "archive/sdd"
ARCHIVED_SDD_FILES = sorted(
    path for path in ARCHIVED_SDD_ROOT.rglob("*") if path.is_file()
)
ARCHIVE_MARKER = "<!-- MOONDEX_ARCHIVED_NON_EXECUTABLE -->"
PROFILE_ARCHIVE_MARKER = "<!-- MOONDEX_ARCHIVED_NON_EXECUTABLE:"

DECLARED_OUTPUT_VALUES = re.compile(
    r"(?:\*\*)?\b(Status|Verdict):(?:\*\*)?[ \t]*"
    r"([A-Z][A-Z0-9_]*(?:[ \t]*\|[ \t]*[A-Z][A-Z0-9_]*)*)"
)
AUTHORITY_TRANSITION = re.compile(
    r'<!-- authority-transition (?P<expected>SPEC|DESIGN|PLAN|EXECUTE)->'
    r'(?P<target>DESIGN|PLAN|EXECUTE|RESULT) owner="(?P<owner>[^"]+)" -->'
)

LIFECYCLE_TARGETS = {
    "orchestrator state": re.compile(r"(?i)ORCHESTRATOR_STATE(?:\.md)?"),
    "generic state document": re.compile(r"(?i)(?<!ORCHESTRATOR_)\bSTATE\.md"),
    "controller state directory": re.compile(r"(?i)\.harness/state"),
    "generic English lifecycle target": re.compile(
        r"(?i)\b(?:lifecycle|controller)\s+(?:state|file)\b|\bstate\s+(?:document|file)\b"
    ),
    "generic Korean lifecycle target": re.compile(
        r"(?:lifecycle|controller)\s*상태|상태\s*(?:문서|파일)"
    ),
}


def lifecycle_targets(text: str) -> list[str]:
    """Return lifecycle target categories without interpreting grammar."""
    return [name for name, pattern in LIFECYCLE_TARGETS.items() if pattern.search(text)]


def recursive_snapshot(root: Path) -> dict[str, tuple[str, int, str]]:
    """Capture hidden and visible entries without following symlinks."""
    snapshot = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        mode = stat.S_IMODE(path.lstat().st_mode)
        if path.is_symlink():
            snapshot[relative] = ("symlink", mode, os.readlink(path))
        elif path.is_dir():
            snapshot[relative] = ("directory", mode, "")
        else:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            snapshot[relative] = ("file", mode, digest)
    return snapshot


def test_active_sdd_paths_are_host_neutral_and_explicit() -> None:
    forbidden = (
        "HARNESS_" + "HOOKS",
        "CODEX_" + "PLUGIN_ROOT",
        "pipeline-" + "utils.sh",
        "Stop " + "hook",
        "init_" + "pipeline",
    )
    combined = "\n".join(path.read_text(encoding="utf-8") for path in ACTIVE)
    assert "python3 <moondex-runtime> state" in combined
    assert "../sdd/runtime/moondex-runtime.py" in combined
    assert "state status" in combined
    assert "state resume" in combined
    assert "state transition" in combined
    assert not [token for token in forbidden if token in combined]


def test_active_python_commands_use_the_package_relative_runtime() -> None:
    """Consumer commands must not resolve code from the project working tree."""
    skill_files = (
        ROOT / "skills/sdd/SKILL.md",
        ROOT / "skills/sdd-orchestrator/SKILL.md",
        ROOT / "skills/code-mapper/SKILL.md",
        ROOT / "skills/pr-converge/SKILL.md",
        ROOT / "skills/self-improve/SKILL.md",
    )
    for path in skill_files:
        lines = path.read_text(encoding="utf-8").splitlines()
        commands = [line for line in lines if line.startswith("python3 ")]
        assert commands, f"expected an executable command in {path}"
        assert all(
            line.startswith("python3 <moondex-runtime> ") for line in commands
        ), f"consumer-cwd Python command in {path}: {commands}"
        assert "../sdd/runtime/moondex-runtime.py" in "\n".join(lines)


def test_each_controller_transition_has_one_phase_scoped_authority_owner() -> None:
    declarations = []
    for path in ACTIVE_SDD_PACKAGE_FILES:
        for match in AUTHORITY_TRANSITION.finditer(path.read_text(encoding="utf-8")):
            declarations.append(
                (match.group("expected"), match.group("target"), match.group("owner"), path)
            )

    expected = {
        ("SPEC", "DESIGN"): "SDD coordinator",
        ("DESIGN", "PLAN"): "SDD coordinator",
        ("PLAN", "EXECUTE"): "SDD coordinator",
        ("EXECUTE", "RESULT"): "execution orchestrator",
    }
    assert len(declarations) == len(expected), declarations
    actual = {}
    for source, target, owner, path in declarations:
        assert (source, target) not in actual, f"conflicting owners for {source}->{target}: {path}"
        actual[(source, target)] = owner
    assert actual == expected

    combined = "\n".join(path.read_text(encoding="utf-8") for path in ACTIVE)
    assert "authority handoff: SDD coordinator -> execution orchestrator" in combined
    assert "Workers never invoke `state transition`" in combined

    execution = (ROOT / "skills/sdd-orchestrator/SKILL.md").read_text(encoding="utf-8")
    assert execution.count(
        '<!-- authority-resume phase="RESULT" owner="execution orchestrator" '
        'transition="forbidden" action="generate-result-report" -->'
    ) == 1
    assert "must not invoke `state transition` while the controller phase is `RESULT`" in execution
    assert "<moondex-runtime> result-action" in execution
    result_action = ROOT / "skills/sdd-orchestrator/scripts/result-action.py"
    source = result_action.read_text(encoding="utf-8")
    assert "subprocess" not in source
    assert "controller_transition" not in source
    assert "worker_dispatches" in source and "transition_calls" in source


def test_active_package_scan_ignores_runtime_bytecode_after_normal_invocation(
    tmp_path: Path,
) -> None:
    env = os.environ.copy()
    env.pop("PYTHONDONTWRITEBYTECODE", None)
    env["PYTHONPYCACHEPREFIX"] = str(tmp_path / "pycache")
    result = subprocess.run(
        ["python3", str(ROOT / "skills/sdd/runtime/moondex-runtime.py"), "result-action", "--help"],
        cwd=ROOT, env=env, check=False, text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    cache = ROOT / "skills/sdd-orchestrator/scripts/__pycache__"
    artifact = cache / "result-action.runtime-test.pyc"
    cache.mkdir(exist_ok=True)
    artifact.write_bytes(b"\x00runtime-bytecode\xff")
    try:
        files = active_sdd_package_files()
        assert files and artifact not in files
        assert all("__pycache__" not in path.parts and path.suffix != ".pyc" for path in files)
        for path in files:
            path.read_text(encoding="utf-8")
    finally:
        artifact.unlink(missing_ok=True)
        for generated in cache.glob("*.pyc"):
            generated.unlink()
        try:
            cache.rmdir()
        except OSError:
            pass


def test_profile_manifest_classifies_every_agent_profile() -> None:
    """No top-level profile may escape the active/archive policy by naming."""
    active_names = set(PROFILE_MANIFEST["active"])
    assert len(active_names) == len(PROFILE_MANIFEST["active"])
    assert all("/" not in name for name in active_names)

    discovered_active = {
        path.name
        for path in (ROOT / "agents").glob("*.md")
        if path.name != "SDD_WORKER_CONTRACT.md"
    }
    assert active_names == discovered_active
    assert all(path.is_file() for path in ACTIVE_PROFILES)

    archived_names = set(PROFILE_MANIFEST["archived"])
    discovered_archived = {
        path.relative_to(ROOT / "agents").as_posix()
        for path in (ROOT / "agents/archive").glob("*.md")
    }
    assert archived_names == discovered_archived
    assert all(PROFILE_MANIFEST["archived"].values())
    assert all(
        PROFILE_ARCHIVE_MARKER in path.read_text(encoding="utf-8")
        for path in ARCHIVED_PROFILE_FILES
    )


def test_active_profile_universe_is_host_neutral_and_contract_bound() -> None:
    forbidden = {
        "host model frontmatter": re.compile(r"(?m)^model\s*:"),
        "host tools frontmatter": re.compile(r"(?m)^(?:allowed-)?tools\s*:"),
        "Claude message primitive": re.compile(r"\bSendMessage\b"),
        "Claude team primitive": re.compile(r"\b(?:TeamCreate|TaskCreate)\b"),
        "Claude MCP binding": re.compile(r"mcp__claude"),
        "legacy design path": re.compile(r"docs/spec-design"),
        "personal absolute path": re.compile(r"/Users/[^/]+/"),
        "private agents home": re.compile(r"~/.agents(?:/|\b)"),
        "legacy lifecycle path": re.compile(r"\.agents/(?:state|shared)(?:/|\b)"),
    }
    violations = {}
    for path in ACTIVE_PROFILES:
        text = path.read_text(encoding="utf-8")
        problems = [name for name, pattern in forbidden.items() if pattern.search(text)]
        if "SDD_WORKER_CONTRACT.md" not in text:
            problems.append("missing shared worker contract")
        if problems:
            violations[path.name] = problems
    assert not violations, f"active profile policy violations: {violations}"


def test_manifest_exposed_skills_and_active_profiles_share_one_portable_surface() -> None:
    """Inventory every public skill entrypoint plus manifest-declared active role."""
    assert PLUGIN_MANIFEST["skills"] == "./skills/"
    assert ACTIVE_MANIFEST_SKILL_FILES == sorted((ROOT / "skills").glob("*/SKILL.md"))
    assert set(ACTIVE_MANIFEST_SKILL_FILES) <= set(ACTIVE_REACHABLE_FILES)
    assert all(path.is_file() for path in ACTIVE_REACHABLE_FILES)
    assert len(ACTIVE_PORTABILITY_SURFACE_FILES) == len(
        set(ACTIVE_PORTABILITY_SURFACE_FILES)
    )

    forbidden = {
        "Claude dispatch syntax": re.compile(
            r"\b(?:Agent|TeamCreate|TaskCreate|SendMessage)\s*\("
        ),
        "Claude dispatch field": re.compile(r"\bsubagent_type\b"),
        "branded browser requirement": re.compile(
            r"\bclaude-in-chrome\b|\bmcp__claude\w*\b", re.IGNORECASE
        ),
        "private agents home": re.compile(r"(?:~|/Users/[^/]+)/(?:\.agents)(?:/|\b)"),
        "personal absolute path": re.compile(r"/Users/[^/]+/"),
        "host lifecycle variable": re.compile(
            r"HARNESS_HOOKS|CODEX_PLUGIN_ROOT|CLAUDE_PLUGIN_ROOT"
        ),
        "legacy pipeline source": re.compile(r"pipeline-utils\.sh"),
        "required branded tool": re.compile(
            r"\b(?:Bash|Read|Write|Edit|Agent)\s+(?:tool|도구|툴)\b",
            re.IGNORECASE,
        ),
    }
    violations = {}
    for path in ACTIVE_PORTABILITY_SURFACE_FILES:
        text = path.read_text(encoding="utf-8")
        problems = [name for name, pattern in forbidden.items() if pattern.search(text)]
        if problems:
            violations[path.relative_to(ROOT).as_posix()] = problems
    assert not violations, f"manifest active surface portability violations: {violations}"

    claude_mentions = {
        path.relative_to(ROOT).as_posix(): [
            line for line in path.read_text(encoding="utf-8").splitlines()
            if "Claude" in line or "claude" in line
        ]
        for path in ACTIVE_PORTABILITY_SURFACE_FILES
    }
    assert not {
        path: lines for path, lines in claude_mentions.items() if lines
    }, "external Claude Design names belong only in explicit Porting Notes or archives"


def test_active_surface_classifies_every_package_asset_and_reachable_reference() -> None:
    """No instruction-reachable file or executable script may escape portability scans."""
    assert ACTIVE_SURFACE_CLASSIFICATION["schema_version"] == 1
    included = {
        path.relative_to(ROOT).as_posix() for path in ACTIVE_REACHABLE_FILES
    }
    excluded = set(ACTIVE_SURFACE_CLASSIFICATION["excluded"])
    package_files = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "skills").rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.name != "ACTIVE_SURFACE.json"
    }
    concrete_exclusions = {
        path for path in excluded
        if "#" not in path and not path.endswith("/")
    }
    assert concrete_exclusions <= package_files
    assert package_files == (included & package_files) | concrete_exclusions

    reference_pattern = re.compile(
        r"(?P<path>(?:references|assets)/[A-Za-z0-9_./-]+"
        r"|scripts/[A-Za-z0-9_.-]+"
        r"|skills/[A-Za-z0-9_./-]+\.(?:py|sh))"
    )
    reached = set()
    for source in ACTIVE_REACHABLE_FILES:
        if source.suffix != ".md":
            continue
        for match in reference_pattern.finditer(source.read_text(encoding="utf-8")):
            raw = Path(match.group("path"))
            relative = source.relative_to(ROOT)
            package_root = (
                ROOT / relative.parts[0] / relative.parts[1]
                if len(relative.parts) >= 2 and relative.parts[0] == "skills"
                else source.parent
            )
            candidates = (source.parent / raw, package_root / raw, ROOT / raw)
            resolved = next((path for path in candidates if path.is_file()), None)
            assert resolved is not None, f"broken active reference {raw} in {source}"
            reached.add(resolved.relative_to(ROOT).as_posix())
    assert reached <= included

    package_scripts = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "skills").rglob("*")
        if path.is_file() and path.suffix in {".py", ".sh"}
    }
    assert package_scripts <= included
    for required in (
        "skills/handoff/assets/HANDOFF_TEMPLATE.md",
        "skills/harness/references/security-baseline.md",
        "skills/harness/references/scoring-guide.md",
        "skills/harness/references/harness-principles.md",
        "skills/sdd-taskrunner/assets/templates/task-document.md",
        "skills/sdd-orchestrator/scripts/result-action.py",
        "skills/sdd-orchestrator/scripts/on-rate-limit.sh",
    ):
        assert required in included


def test_active_python_dependency_closure_is_repo_complete_and_classified() -> None:
    """AST-resolve local imports recursively; external imports must resolve off-repo."""
    included = {path.resolve() for path in ACTIVE_REACHABLE_FILES}
    excluded = {
        (ROOT / relative).resolve()
        for relative in ACTIVE_SURFACE_CLASSIFICATION["excluded"]
        if "#" not in relative and not relative.endswith("/")
    }
    queue = [
        path for path in ACTIVE_REACHABLE_FILES
        if path.suffix == ".py"
        and path.relative_to(ROOT).parts[0] in {"skills", "scripts"}
    ]
    visited = set()
    discovered = set()
    while queue:
        path = queue.pop()
        resolved = path.resolve()
        if resolved in visited:
            continue
        visited.add(resolved)
        for dependency in _repo_import_dependencies(ROOT, path):
            dependency = dependency.resolve()
            assert dependency not in excluded, f"active import reaches excluded file: {dependency}"
            assert dependency in included, f"unclassified repo-local import: {dependency}"
            discovered.add(dependency)
            if dependency not in visited:
                queue.append(dependency)

    adapter = (ROOT / "scripts/adapter_render.py").resolve()
    result_action = ROOT / "skills/sdd-orchestrator/scripts/result-action.py"
    assert adapter in discovered
    assert adapter in {
        dependency.resolve()
        for dependency in _repo_import_dependencies(ROOT, result_action)
    }
    assert (ROOT / "harness_core/state/pipeline.py").resolve() in discovered

    code_forbidden = {
        "private path": re.compile(r"/Users/[^/]+/|~/.agents(?:/|\b)"),
        "host variable": re.compile(
            r"HARNESS_HOOKS|CODEX_PLUGIN_ROOT|CLAUDE_PLUGIN_ROOT"
        ),
        "branded tool binding": re.compile(
            r"claude-in-chrome|mcp__claude", re.IGNORECASE
        ),
    }
    violations = {}
    for path in visited:
        text = path.read_text(encoding="utf-8")
        problems = [name for name, pattern in code_forbidden.items() if pattern.search(text)]
        if problems:
            violations[path.relative_to(ROOT).as_posix()] = problems
    assert not violations, f"active code dependency policy violations: {violations}"


def test_runtime_inventory_exactly_binds_recursive_local_dependency_closure() -> None:
    """The install contract is the manifest plus all runtime-reachable local code."""
    seeds = [
        ROOT / "skills/sdd/runtime/moondex-runtime.py",
        ROOT / "scripts/verify.py",
        ROOT / "scripts/code_mapper_adapter.py",
        ROOT / "scripts/pr_converge_adapter.py",
        ROOT / "scripts/self_improve_adapter.py",
        ROOT / "skills/sdd-orchestrator/scripts/result-action.py",
    ]
    queue = list(seeds)
    closure = set()
    while queue:
        path = queue.pop().resolve()
        if path in closure:
            continue
        closure.add(path)
        queue.extend(
            dependency
            for dependency in _repo_import_dependencies(ROOT, path)
            if dependency.resolve() not in closure
        )
    expected = {
        path.relative_to(ROOT).as_posix() for path in closure
    } | {".codex-plugin/plugin.json"}
    inventory_path = ROOT / "skills/sdd/runtime/runtime-inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    entries = inventory["files"]
    paths = [entry["path"] for entry in entries]
    assert paths == sorted(paths)
    assert set(paths) == expected
    assert inventory_path.relative_to(ROOT).as_posix() not in paths
    assert inventory["schema_version"] == 1
    assert inventory["runtime_protocol"] == 1
    assert inventory["plugin"] == {
        "name": PLUGIN_MANIFEST["name"],
        "version": PLUGIN_MANIFEST["version"],
    }
    assert inventory["mode_policy"] == "regular-not-group-or-world-writable"
    included = set(ACTIVE_SURFACE_CLASSIFICATION["included"])
    assert expected | {inventory_path.relative_to(ROOT).as_posix()} <= included
    for entry in entries:
        path = ROOT / entry["path"]
        content = path.read_bytes()
        assert path.is_file() and not path.is_symlink()
        assert entry == {
            "path": entry["path"],
            "kind": "regular",
            "size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
        assert stat.S_IMODE(path.stat().st_mode) & 0o022 == 0


def test_local_module_resolver_detects_sibling_and_ambiguous_modules(tmp_path: Path) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    consumer = scripts / "consumer.py"
    consumer.write_text(
        "import local_probe\nfrom local_package import child\n",
        encoding="utf-8",
    )
    sibling = scripts / "local_probe.py"
    sibling.write_text("VALUE = 1\n", encoding="utf-8")
    assert _local_module_files(tmp_path, consumer, "local_probe", 0) == [sibling]

    package = tmp_path / "local_package"
    package.mkdir()
    package_init = package / "__init__.py"
    package_init.write_text("", encoding="utf-8")
    package_child = package / "child.py"
    package_child.write_text("VALUE = 1\n", encoding="utf-8")
    assert set(_repo_import_dependencies(tmp_path, consumer)) == {
        sibling,
        package_init,
        package_child,
    }

    competing = tmp_path / "local_probe.py"
    competing.write_text("VALUE = 2\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="ambiguous local module"):
        _local_module_files(tmp_path, consumer, "local_probe", 0)


def test_idea_research_dispatch_preserves_outcomes_without_automatic_team_assumption() -> None:
    workshop = (ROOT / "skills/idea-workshop/SKILL.md").read_text(encoding="utf-8")
    expected = {
        "idea-market-researcher": "docs/research/market-research.md",
        "idea-user-researcher": "docs/research/user-research.md",
        "idea-feasibility-checker": "docs/research/feasibility.md",
        "idea-biz-model-designer": "docs/research/business-model.md",
    }
    for role, artifact in expected.items():
        assert role in workshop and artifact in workshop
    assert "병렬로 위임할 수 있다" in workshop
    assert "| 1 | `idea-market-researcher`" in workshop
    assert "| 1 | `idea-feasibility-checker`" in workshop
    assert "| 2 | `idea-user-researcher`" in workshop
    assert "| 3 | `idea-biz-model-designer`" in workshop
    assert "| 4 | `idea-reviewer`" in workshop
    assert "market의 경쟁 앱 목록 또는 출처가 명시된 동등한 사전 계산 입력" in workshop
    assert "user 지불 의향 인용 + market 경쟁 가격 + feasibility 인프라 비용" in workshop
    assert "`market → feasibility` 또는" in workshop
    assert "`feasibility → market`" in workshop
    assert "`user → business → reviewer`" in workshop
    assert "`NEEDS_CONTEXT`가 반환되면" in workshop
    assert "팀이나 background 실행이 자동으로 생성된다고 가정하지 않는다" in workshop
    assert "docs/PRD.md" in workshop and "docs/research/review-log.md" in workshop


def test_user_research_and_taskrunner_have_portable_fallbacks_and_relative_assets() -> None:
    researcher = (ROOT / "agents/idea-user-researcher.md").read_text(encoding="utf-8")
    assert "선택적 browser/research capability" in researcher
    assert "사용자가 제공한 export" in researcher
    assert "`NEEDS_CONTEXT`" in researcher
    assert "특정 브라우저 도구나 서비스가 필수라고 가정하지 않는다" in researcher

    taskrunner_path = ROOT / "skills/sdd-taskrunner/SKILL.md"
    taskrunner = taskrunner_path.read_text(encoding="utf-8")
    relative = Path("assets/templates/task-document.md")
    assert relative.as_posix() in taskrunner
    assert (taskrunner_path.parent / relative).is_file()
    assert "개인 홈이나 전역 설치 경로를" in taskrunner


def test_active_surfaces_do_not_link_archived_profiles() -> None:
    active_files = [*ACTIVE_PROFILES, *ACTIVE, *ACTIVE_SDD_PACKAGE_FILES]
    active_text = "\n".join(path.read_text(encoding="utf-8") for path in active_files)
    linked = []
    for archived in PROFILE_MANIFEST["archived"]:
        filename = Path(archived).name
        patterns = (
            f"agents/{archived}",
            f"]({archived})",
            f"](agents/{archived})",
            f"]({filename})",
        )
        if any(pattern in active_text for pattern in patterns):
            linked.append(archived)
    assert not linked, f"active instructions link archived profiles: {linked}"


def test_workers_reference_shared_result_only_authority() -> None:
    contract = ROOT / "agents/SDD_WORKER_CONTRACT.md"
    assert contract.is_file()
    text = contract.read_text(encoding="utf-8")
    prohibition = (
        "A worker must not create, edit, write, update, persist, save, record, "
        "or overwrite `docs/sdd/ORCHESTRATOR_STATE.md`, any `STATE.md`, or "
        "anything under `.harness/state/`."
    )
    assert prohibition in text
    for field in ("Status:", "Verdict:", "Changed paths:", "Validation:", "Evidence / blocker:"):
        assert field in text
    for result in ("DONE", "DONE_WITH_CONCERNS", "NEEDS_CONTEXT", "BLOCKED"):
        assert f"`{result}`" in text
    for verdict in (
        "READY",
        "COMPLIANCE_PASS",
        "COMPLIANCE_FAIL",
        "REVIEW_PASS",
        "REVIEW_FAIL",
        "TEST_PASS",
        "TEST_FAIL",
        "SYNC_APPLIED",
        "SYNC_SKIPPED",
        "PASS",
        "REWORK",
    ):
        assert f"`{verdict}`" in text
    assert ACTIVE_SDD_PROFILES, "at least one active SDD profile must exist"
    missing = [
        path.name
        for path in ACTIVE_SDD_PROFILES
        if "SDD_WORKER_CONTRACT.md" not in path.read_text(encoding="utf-8")
    ]
    assert not missing, f"active SDD profiles must reference the common contract: {missing}"


def test_active_profiles_declare_only_contract_status_and_verdict_values() -> None:
    """Reject hidden profile-local result vocabularies across the manifest universe."""
    allowed = {
        "Status": {"DONE", "DONE_WITH_CONCERNS", "NEEDS_CONTEXT", "BLOCKED"},
        "Verdict": {
            "READY",
            "COMPLIANCE_PASS",
            "COMPLIANCE_FAIL",
            "REVIEW_PASS",
            "REVIEW_FAIL",
            "TEST_PASS",
            "TEST_FAIL",
            "SYNC_APPLIED",
            "SYNC_SKIPPED",
            "PASS",
            "REWORK",
        },
    }
    contract = (ROOT / "agents/SDD_WORKER_CONTRACT.md").read_text(encoding="utf-8")
    for field, values in allowed.items():
        vocabulary_line = next(
            line for line in contract.splitlines() if f"{field} vocabulary:" in line
        )
        # The vocabulary may wrap, so assert each value is explicitly declared in
        # the common contract as the authoritative source read by every profile.
        assert all(f"`{value}`" in contract for value in values), vocabulary_line

    violations = {}
    for path in ACTIVE_PROFILES:
        declarations = {}
        for field, raw_values in DECLARED_OUTPUT_VALUES.findall(
            path.read_text(encoding="utf-8")
        ):
            values = {value.strip() for value in raw_values.split("|")}
            unknown = sorted(values - allowed[field])
            if unknown:
                declarations.setdefault(field, set()).update(unknown)
        if declarations:
            violations[path.name] = {
                field: sorted(values) for field, values in declarations.items()
            }
    assert not violations, f"non-contract result vocabulary: {violations}"


def test_stage_profiles_use_coherent_status_and_verdict_envelope() -> None:
    expected = {
        "sdd-team-leader.md": ("READY",),
        "sdd-compliance-checker.md": ("COMPLIANCE_PASS", "COMPLIANCE_FAIL"),
        "sdd-reviewer.md": ("REVIEW_PASS", "REVIEW_FAIL"),
        "sdd-test-automator.md": ("TEST_PASS", "TEST_FAIL"),
    }
    for filename, verdicts in expected.items():
        text = (ROOT / "agents" / filename).read_text(encoding="utf-8")
        assert "Status:" in text
        assert "Verdict:" in text
        assert all(verdict in text for verdict in verdicts)

    team = (ROOT / "agents/sdd-team-leader.md").read_text(encoding="utf-8")
    assert "`Status: DONE`, `Verdict: READY`" in team
    assert "`READY`는 lifecycle status가 아니라" in team

    guide = (
        ROOT / "skills/sdd-orchestrator/references/agent-dispatch-guide.md"
    ).read_text(encoding="utf-8")
    schema = (
        ROOT / "skills/sdd-orchestrator/references/state-schema.md"
    ).read_text(encoding="utf-8")
    for verdict in ("COMPLIANCE_PASS", "REVIEW_PASS", "TEST_PASS", "READY"):
        assert verdict in guide
        assert verdict in schema
    for stage in ("`verifying`", "`reviewing`", "`testing`"):
        assert stage in guide
        assert stage in schema
    assert "RESULT:" not in guide


def test_all_active_references_use_controller_phase_and_task_stages_only() -> None:
    """References may display controller truth but cannot define a second lifecycle."""
    assert ACTIVE_SDD_REFERENCE_FILES, "active reference discovery must not be empty"
    forbidden = re.compile(
        r"\b(?:PLANNING|EXECUTING|PAUSED_AT_LIMIT|COMPLETED|"
        r"KNOWLEDGE_SYNCING|KNOWLEDGE_SYNCED|resume_at|pending|interrupted|escalated)\b"
    )
    violations = {}
    for path in ACTIVE_SDD_REFERENCE_FILES:
        matches = sorted(set(forbidden.findall(path.read_text(encoding="utf-8"))))
        if matches:
            violations[path.relative_to(ROOT).as_posix()] = matches
    assert not violations, f"active references define a second lifecycle: {violations}"

    schema = (
        ROOT / "skills/sdd-orchestrator/references/state-schema.md"
    ).read_text(encoding="utf-8")
    assert "Controller phase: SPEC | DESIGN | PLAN | EXECUTE | RESULT" in schema
    declared_stages = re.findall(r"^- `([a-z]+)` —", schema, re.MULTILINE)
    assert set(declared_stages) == {
        "implementing", "fixing", "verifying", "reviewing", "testing", "complete"
    }
    assert "`state status`" in schema and "`state resume`" in schema

    taskmaster = (ROOT / "agents/sdd-taskmaster.md").read_text(encoding="utf-8")
    assert "controller_phase: PLAN" in taskmaster
    assert "controller_evidence:" in taskmaster
    assert "task stage는 첫 디스패치 전이므로 포함하지 않는다" in taskmaster

    guide = (
        ROOT / "skills/sdd-orchestrator/references/agent-dispatch-guide.md"
    ).read_text(encoding="utf-8")
    assert "`state status`" in guide and "`state resume`" in guide
    assert "별도 pause phase" in guide


def test_worker_profiles_do_not_name_lifecycle_state_targets() -> None:
    """Worker profiles delegate authority structurally through one contract."""
    assert all(path.name != "sdd-orchestrator.md" for path in ACTIVE_SDD_PROFILES)
    violations = {}
    for path in ACTIVE_SDD_PROFILES:
        text = path.read_text(encoding="utf-8")
        matches = lifecycle_targets(text)
        if matches:
            violations[path.name] = matches
    assert not violations, f"lifecycle targets belong only in the common contract: {violations}"


def test_worker_target_policy_is_grammar_independent() -> None:
    adversarial = (
        "Never write ORCHESTRATOR_STATE.md; then save ORCHESTRATOR_STATE.md.",
        "Do not edit .harness/state/, but persist .harness/state after validation.",
        "STATE.md를 수정하지 않는다. 이후에는 STATE.md를 저장한다.",
        ".harness/state를 기록한다.",
        "ORCHESTRATOR_STATE.md를 덮어쓰기 하세요.",
        "Do not edit docs/sdd/ORCHESTRATOR_STATE.md, but update it after validation.",
        "ORCHESTRATOR_STATE.md를 수정하지 않는다. 이후에는 상태 파일을 갱신한다.",
        "Never write ORCHESTRATOR_STATE.md; update it after review.",
        "Persist docs/sdd/ORCHESTRATOR_STATE after validation.",
        "Do not write .harness/state/pipeline.json. Then update that state file.",
        "Never edit ORCHESTRATOR_STATE.md.\n\nUpdate it after validation.",
        "ORCHESTRATOR_STATE.md를 수정하지 않고 상태 파일을 저장한다.",
        "ORCHESTRATOR_STATE.md를 수정하지 말고 상태 파일을 저장하세요.",
        "Do not edit ORCHESTRATOR_STATE.md yet save the state file.",
        "Never write ORCHESTRATOR_STATE.md or .harness/state/.",
        "ORCHESTRATOR_STATE.md 작성은 금지한다.",
        "`.harness/state`를 저장해서는 안 된다.",
    )
    neutral = (
        "Return task-owned changes and validation evidence.",
        "Follow SDD_WORKER_CONTRACT.md.",
    )
    assert all(lifecycle_targets(example) for example in adversarial)
    assert not any(lifecycle_targets(example) for example in neutral)


def test_active_profiles_have_host_neutral_frontmatter_and_execution_contracts() -> None:
    unsupported_frontmatter = {"model", "tools"}
    claude_execution_syntax = re.compile(
        r"(?:\b(?:Skill|Agent|SendMessage|TeamCreate|TaskCreate)\s*\(|"
        r"\b(?:Skill|Agent|Read|Write|Edit|Bash|Glob|Grep)\s+(?:도구|툴))"
    )
    violations = {}
    for path in ACTIVE_SDD_PROFILES:
        text = path.read_text(encoding="utf-8")
        frontmatter = text.split("---", 2)[1]
        keys = {
            line.split(":", 1)[0].strip()
            for line in frontmatter.splitlines()
            if ":" in line and not line.startswith((" ", "\t"))
        }
        problems = []
        missing_contract_keys = {"name", "description", "role", "capabilities"} - keys
        if missing_contract_keys:
            problems.append(f"missing contract frontmatter: {sorted(missing_contract_keys)}")
        if keys & unsupported_frontmatter:
            problems.append(f"unsupported frontmatter: {sorted(keys & unsupported_frontmatter)}")
        matches = claude_execution_syntax.findall(text)
        if matches:
            problems.append(f"host execution syntax: {matches}")
        if problems:
            violations[path.name] = problems
    assert not violations, f"active profiles must remain host-neutral: {violations}"


def test_active_sdd_skills_have_host_neutral_frontmatter_and_instructions() -> None:
    unsupported_frontmatter = {"model", "tools", "allowed-tools"}
    host_execution_syntax = re.compile(
        r"(?:\b(?:Skill|Agent|SendMessage|TeamCreate|TaskCreate)\s*\(|"
        r"\b(?:Skill|Agent|Read|Write|Edit|Bash|Glob|Grep)\s+(?:tool|도구|툴))",
        re.IGNORECASE,
    )
    violations = {}
    for path in ACTIVE:
        text = path.read_text(encoding="utf-8")
        assert text.startswith("---\n"), f"missing frontmatter: {path}"
        frontmatter = text.split("---", 2)[1]
        keys = {
            line.split(":", 1)[0].strip()
            for line in frontmatter.splitlines()
            if ":" in line and not line.startswith((" ", "\t"))
        }
        problems = []
        missing = {"name", "description"} - keys
        if missing:
            problems.append(f"missing skill frontmatter: {sorted(missing)}")
        if keys & unsupported_frontmatter:
            problems.append(f"unsupported frontmatter: {sorted(keys & unsupported_frontmatter)}")
        matches = host_execution_syntax.findall(text)
        if matches:
            problems.append(f"host execution syntax: {matches}")
        if problems:
            violations[path.relative_to(ROOT).as_posix()] = problems
    assert not violations, f"active SDD skills must remain host-neutral: {violations}"


def test_taskmaster_returns_state_initialization_payload_to_orchestrator() -> None:
    text = (ROOT / "agents/sdd-taskmaster.md").read_text(encoding="utf-8")
    assert "DAG 실행 payload" in text
    assert "실제 구조화 DAG 실행 payload 전체" in text
    for field in ("metadata:", "teams:", "waves:", "tasks:", "ownership:", "evidence:"):
        assert field in text
    assert "DAG 실행 payload:** 준비 완료" not in text


def test_compound_sync_has_no_private_default() -> None:
    text = (ROOT / "agents/sdd-compound-syncer.md").read_text(encoding="utf-8")
    assert "compound_root" in text
    assert "SKIPPED" in text
    assert "/Users/" not in text


def test_entire_active_sdd_surface_has_no_legacy_lifecycle_targets() -> None:
    """References and optional scripts are executable guidance, not dead fixtures."""
    legacy_targets = re.compile(r"(?i)\.agents/(?:state|shared)(?:/|\b)")
    violations = {}
    for path in [*ACTIVE_SDD_PROFILES, *ACTIVE_SDD_PACKAGE_FILES]:
        matches = sorted(set(legacy_targets.findall(path.read_text(encoding="utf-8"))))
        if matches:
            violations[path.relative_to(ROOT).as_posix()] = matches
    assert not violations, f"active SDD surface contains legacy lifecycle targets: {violations}"


def test_entire_active_sdd_package_is_host_neutral() -> None:
    forbidden = {
        "Claude dispatch call": re.compile(r"\bAgent\s*\("),
        "Claude background flag": re.compile(r"\brun_in_background\b"),
        "Claude team primitive": re.compile(
            r"\b(?:SendMessage|TeamCreate|TaskCreate)\s*\("
        ),
        "legacy hook env": re.compile(r"HARNESS_HOOKS|CODEX_PLUGIN_ROOT"),
        "legacy pipeline source": re.compile(r"pipeline-utils\.sh"),
    }
    violations = {}
    for path in ACTIVE_SDD_PACKAGE_FILES:
        text = path.read_text(encoding="utf-8")
        matches = [name for name, pattern in forbidden.items() if pattern.search(text)]
        if matches:
            violations[path.relative_to(ROOT).as_posix()] = matches
    assert not violations, f"active SDD package contains host-specific execution syntax: {violations}"


def test_active_sdd_package_rejects_private_paths_and_legacy_handoff_guidance() -> None:
    """Every non-archive file under an active skill package is executable guidance."""
    forbidden = {
        "private agents home": re.compile(r"(?:~|/Users/[^/]+)/(?:\.agents)(?:/|\b)"),
        "personal absolute path": re.compile(r"/Users/[^/]+/"),
        "legacy handoff procedure": re.compile(
            r"다음 에이전트가 해야 할 일|이 파일만 읽고 바로 작업을 이어갈|"
            r"next agent must|read this file and continue",
            re.IGNORECASE,
        ),
    }
    violations = {}
    for path in ACTIVE_SDD_PACKAGE_FILES:
        text = path.read_text(encoding="utf-8")
        matches = [name for name, pattern in forbidden.items() if pattern.search(text)]
        if matches:
            violations[path.relative_to(ROOT).as_posix()] = matches
    assert not violations, (
        "active SDD packages must not expose private paths or legacy handoff commands: "
        f"{violations}"
    )


def test_archived_sdd_material_is_marked_and_unreferenced_by_active_instructions() -> None:
    """Archive exclusion is valid only for marked files outside active traversal."""
    assert ARCHIVED_SDD_FILES, "the preserved SDD history must exist in the explicit archive"
    unmarked = [
        path.relative_to(ROOT).as_posix()
        for path in ARCHIVED_SDD_FILES
        if ARCHIVE_MARKER not in path.read_text(encoding="utf-8")
    ]
    assert not unmarked, f"archived SDD files require the non-executable marker: {unmarked}"

    active_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [*ACTIVE, *ACTIVE_SDD_PROFILES, *ACTIVE_SDD_PACKAGE_FILES]
    )
    referenced = [
        path.relative_to(ROOT).as_posix()
        for path in ARCHIVED_SDD_FILES
        if path.relative_to(ROOT).as_posix() in active_text
        or path.name in active_text
    ]
    assert not referenced, f"active SDD instructions must not link archived material: {referenced}"


def test_optional_rate_limit_script_is_advisory_and_read_only(tmp_path: Path) -> None:
    path = ROOT / "skills/sdd-orchestrator/scripts/on-rate-limit.sh"
    text = path.read_text(encoding="utf-8")
    assert "no project files were changed" in text
    assert "project-local controller" in text
    mutators = re.compile(r"\bsed\b|\btee\b|>>|\bmv\b|\bcp\b|\brm\b")
    assert not mutators.search(text)
    assert not lifecycle_targets(text)

    project = tmp_path / "representative-project"
    (project / ".harness/state/sdd/demo/run-1").mkdir(parents=True)
    (project / ".hidden").mkdir()
    (project / ".harness/state/pipeline.json").write_text(
        '{"phase":"EXECUTE"}\n', encoding="utf-8"
    )
    (project / ".harness/state/sdd/demo/run-1/events.jsonl").write_text(
        '{"event":"before"}\n', encoding="utf-8"
    )
    (project / ".hidden/sentinel").write_bytes(b"preserve-me\x00")
    (project / "visible.txt").write_text("unchanged\n", encoding="utf-8")
    before = recursive_snapshot(project)

    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(project),
        "PROJECT_ROOT": str(project),
        "MOONDEX_FEATURE": "demo",
        "RETRY_AFTER": "120",
    }
    result = subprocess.run(
        ["/bin/bash", str(path), "--feature", "demo", "--retry-after", "120"],
        cwd=project,
        input='{"event":"rate_limit","attempt":2}\n',
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0
    assert result.stderr == ""
    assert "Rate-limit advisory received" in result.stdout
    assert "no project files were changed" in result.stdout
    assert "project-local controller status/resume commands" in result.stdout
    assert recursive_snapshot(project) == before


def test_active_orchestrator_references_preserve_sole_writer_contract() -> None:
    state_schema = (
        ROOT / "skills/sdd-orchestrator/references/state-schema.md"
    ).read_text(encoding="utf-8")
    dispatch_guide = (
        ROOT / "skills/sdd-orchestrator/references/agent-dispatch-guide.md"
    ).read_text(encoding="utf-8")
    assert "lifecycle의 유일한 source of truth는 프로젝트 로컬 컨트롤러" in state_schema
    assert "오케스트레이터만 이 현황 문서를 쓰며" in state_schema
    assert "taskmaster가 controller phase `PLAN`, controller evidence, Wave/DAG payload" in state_schema
    assert "UX Designer가 반환한 E2E 설정 payload" in state_schema
    assert ".harness/state/e2e-config.json" in state_schema
    assert "오케스트레이터만 lifecycle 문서" in dispatch_guide
    assert "워커는 중단 근거만 반환" in dispatch_guide
    assert "Agent(" not in dispatch_guide
    assert "run_in_background" not in dispatch_guide
