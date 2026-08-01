"""Offline policy checks for the Codex enforcement adapter.

The checks deliberately consume explicit paths and branch names.  This keeps the
result reproducible in local hooks, CI, and fixture tests without network calls.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from harness_core.config import load_config


SECRET_ASSIGNMENT = re.compile(
    r"(?im)^\s*(?:export\s+)?(?:api[_-]?key|[a-z0-9_-]*?(?:secret|token|password))\s*[=:]\s*(?P<value>[^#\r\n]+)"
)
UI_SUFFIXES = {".tsx", ".jsx", ".vue", ".svelte", ".css", ".scss", ".html"}
NON_IMPLEMENTATION_ROOTS = {"docs", "tests", ".github", ".harness", "benchmarks", "evals"}


class ValidationError(ValueError):
    """A policy failure with a reason and a concrete corrective action."""


@dataclass(frozen=True)
class ChangedFileKinds:
    implementation: tuple[Path, ...]
    ui: tuple[Path, ...]
    protected: tuple[Path, ...]


def classify_changed_files(paths: Iterable[Path], protected_paths: Iterable[str]) -> ChangedFileKinds:
    """Classify relative changed paths without consulting git or the network."""

    normalized = tuple(Path(str(path)) for path in paths)
    protected_roots = tuple(_normalized_relative_path(value) for value in protected_paths)
    implementation = tuple(path for path in normalized if _is_implementation(path))
    ui = tuple(path for path in normalized if path.suffix.lower() in UI_SUFFIXES)
    protected = tuple(
        path
        for path in normalized
        if any(path == root or root in path.parents for root in protected_roots)
    )
    return ChangedFileKinds(implementation=implementation, ui=ui, protected=protected)


def check_enforcement(
    project_root: Path,
    changed_files: Iterable[Path],
    *,
    branch: str,
    default_branch: str,
    tdd_manifest: Path | None = None,
    e2e_config: Path | None = None,
    allowed_protected_paths: Iterable[Path] = (),
) -> None:
    """Raise one actionable error per failed enforcement rule.

    All paths are interpreted relative to ``project_root``.  Callers may pass an
    empty change set; that is a valid no-op useful for CI bootstrap checks.
    """

    root = project_root.resolve()
    relative_paths = tuple(_relative_path(root, path) for path in changed_files)
    config = load_config(root / ".harness/config.json")
    kinds = classify_changed_files(relative_paths, config["security"]["protected_paths"])
    errors: list[str] = []

    if branch == default_branch and kinds.implementation:
        errors.append(
            "BRANCH_DEFAULT: implementation changes are on the default branch "
            f"'{default_branch}'. Create an isolated feature branch/worktree and rerun preflight."
        )
    if kinds.implementation and not _valid_tdd_manifest(root / (tdd_manifest or Path(".harness/state/tdd-manifest.json"))):
        errors.append(
            "TDD_EVIDENCE_MISSING: implementation changes require a TDD manifest with "
            "red_evidence and green_command. Create .harness/state/tdd-manifest.json before committing."
        )
    if kinds.ui and not _valid_e2e_config(root / (e2e_config or Path(".harness/state/e2e-config.json"))):
        errors.append(
            "E2E_EVIDENCE_MISSING: UI changes require e2e-config.json evidence. Add a non-empty "
            "evidence list or command under .harness/state/e2e-config.json."
        )
    if config["security"]["secret_scan"]:
        for path in relative_paths:
            absolute = root / path
            if absolute.is_file() and _contains_secret(absolute):
                errors.append(
                    f"SECRET_EXPOSED: possible secret in {path}. Remove it and use an approved secret reference."
                )
    allowed = {_relative_path(root, path) for path in allowed_protected_paths}
    for path in kinds.protected:
        if path not in allowed:
            errors.append(
                f"PROTECTED_PATH: {path} is protected. Obtain explicit review approval and pass "
                f"--allow-protected-path {path} for the approved change."
            )
    if errors:
        raise ValidationError("Enforcement preflight failed:\n- " + "\n- ".join(errors))


def _is_implementation(path: Path) -> bool:
    return bool(path.parts) and path.parts[0] not in NON_IMPLEMENTATION_ROOTS and path.suffix not in {".md", ".txt"}


def _relative_path(root: Path, path: Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        try:
            candidate = candidate.resolve().relative_to(root)
        except ValueError as exc:
            raise ValidationError(f"PATH_OUTSIDE_PROJECT: {candidate}. Pass only files under {root}.") from exc
    return _normalized_relative_path(str(candidate))


def _normalized_relative_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValidationError(f"INVALID_CHANGED_PATH: {value}. Use a project-relative path without '..'.")
    return path


def _load_json_object(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _valid_tdd_manifest(path: Path) -> bool:
    manifest = _load_json_object(path)
    return bool(
        manifest
        and isinstance(manifest.get("red_evidence"), str)
        and manifest["red_evidence"].strip()
        and isinstance(manifest.get("green_command"), str)
        and manifest["green_command"].strip()
    )


def _valid_e2e_config(path: Path) -> bool:
    evidence = _load_json_object(path)
    if not evidence:
        return False
    if isinstance(evidence.get("command"), str) and evidence["command"].strip():
        return True
    return isinstance(evidence.get("evidence"), list) and any(
        isinstance(item, str) and item.strip() for item in evidence["evidence"]
    )


def _contains_secret(path: Path) -> bool:
    try:
        return any(_looks_like_secret(match.group("value")) for match in SECRET_ASSIGNMENT.finditer(
            path.read_text(encoding="utf-8", errors="replace")
        ))
    except OSError:
        return False


def _looks_like_secret(value: str) -> bool:
    """Accept literal credential-shaped values while ignoring common references/placeholders."""

    candidate = value.strip().rstrip(",;").strip().strip("'\"")
    normalized = candidate.lower()
    if (
        len(candidate) < 8
        or any(character.isspace() for character in candidate)
        or candidate.startswith(("$", "{{", "${"))
        or normalized.startswith(("os.environ", "process.env", "getenv(", "env("))
        or normalized in {"required", "optional", "none", "null", "undefined", "changeme", "not-a-secret"}
        or normalized.startswith(("example", "your_", "your-", "replace_", "replace-"))
    ):
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9_./+=:@-]+", candidate))
