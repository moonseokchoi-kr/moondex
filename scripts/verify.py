#!/usr/bin/env python3
"""Run the shared local-first enforcement policy.

Remote range/CI options are intentionally not part of the baseline interface;
``harness_core preflight enforce`` retains those advisory integrations.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence

# Python executes a file with ``scripts/`` on sys.path, not the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness_core.cli import main as harness_main


def _project_root(explicit_root: Path | None) -> Path:
    """Choose a stable project root for the legacy positional-path adapter.

    Positional absolute paths are input to the verifier, never evidence of the
    repository that should be verified.  Prefer an explicitly supplied root,
    then Git's worktree root.  Outside Git, the current directory is the only
    safe fallback: deriving a root from an input path would let that path drop
    the plugin's immutable protection roots.
    """
    if explicit_root is not None:
        return explicit_root.resolve()
    try:
        result = subprocess.run(
            ("git", "rev-parse", "--show-toplevel"),
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        result = None
    if result is not None and result.returncode == 0 and result.stdout.strip():
        return Path(result.stdout.strip()).resolve()
    return Path.cwd().resolve()


def _legacy_positional_path(root: Path, raw: Path) -> Path:
    """Make one absolute legacy path repository-relative, or reject it."""
    if not raw.is_absolute():
        return raw
    try:
        return raw.resolve(strict=False).relative_to(root)
    except ValueError as exc:
        raise ValueError(f"absolute positional path is outside project root: {raw}") from exc


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--branch", default=os.environ.get("GITHUB_REF_NAME", "local"))
    parser.add_argument("--default-branch", default=os.environ.get("DEFAULT_BRANCH", "main"))
    parser.add_argument("--changed-file", action="append", default=[])
    parser.add_argument("--changed-files-file", type=Path)
    parser.add_argument("--source", choices=("explicit", "worktree", "hook"))
    parser.add_argument("--content-source", choices=("worktree", "index", "revision"), default="worktree")
    parser.add_argument("--content-revision")
    parser.add_argument("--audit-file", type=Path)
    # Positional paths preserve the original lightweight verifier interface.
    parser.add_argument("paths", nargs="*")
    args = parser.parse_args(argv)
    positional_paths = [Path(value) for value in args.paths]
    root = _project_root(args.project_root)
    command = [
        "preflight", "check", "--project-root", str(root), "--branch", args.branch,
        "--default-branch", args.default_branch,
    ]
    if args.source:
        command.extend(("--source", args.source))
    command.extend(("--content-source", args.content_source))
    if args.content_revision:
        command.extend(("--content-revision", args.content_revision))
    # Positional absolute paths are a legacy convenience interface.  Convert
    # them to the independently selected root before they reach the strict
    # changed-file API; an input path must not redefine that root.
    try:
        normalized_positional = [_legacy_positional_path(root, path) for path in positional_paths]
    except ValueError as exc:
        print(f"PREFLIGHT_FAILED: INVALID_PATH: {exc}")
        return 2
    for path in [*args.changed_file, *normalized_positional]:
        command.extend(("--changed-file", str(path)))
    if args.changed_files_file:
        command.extend(("--changed-files-file", str(args.changed_files_file)))
    if args.audit_file:
        command.extend(("--audit-file", str(args.audit_file)))
    return harness_main(command)


if __name__ == "__main__":
    raise SystemExit(main())
