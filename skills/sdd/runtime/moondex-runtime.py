#!/usr/bin/env python3
"""Package-relative command launcher for an installed Moondex plugin."""

from __future__ import annotations

import importlib.util
import hashlib
import json
import os
from pathlib import Path
from pathlib import PurePosixPath
import stat
import sys
from typing import Callable, Sequence
import unicodedata


RUNTIME_PROTOCOL = 1
RUNTIME_FILE = Path(__file__).resolve()
PLUGIN_ROOT = RUNTIME_FILE.parents[3]
INVENTORY_FILE = RUNTIME_FILE.with_name("runtime-inventory.json")
ENTRY_POINTS = {
    "verify": "scripts/verify.py",
    "code-mapper": "scripts/code_mapper_adapter.py",
    "pr-converge": "scripts/pr_converge_adapter.py",
    "self-improve": "scripts/self_improve_adapter.py",
    "result-action": "skills/sdd-orchestrator/scripts/result-action.py",
}
USAGE = f"""usage: moondex-runtime <command> [arguments]

Package-relative Moondex runtime protocol v{RUNTIME_PROTOCOL}.

commands:
  state, preflight, doctor    project-local controller and validation CLI
  verify                      compatibility verifier
  code-mapper                 code impact adapter
  pr-converge                 PR review convergence adapter
  self-improve                learning policy adapter
  result-action               verified RESULT materializer
"""


class RuntimeLayoutError(RuntimeError):
    """The installed plugin archive does not contain its declared runtime."""


def _strict_json(path: Path, label: str) -> object:
    def pairs(values: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in values:
            if key in result:
                raise RuntimeLayoutError(f"{label} has a duplicate key")
            result[key] = value
        return result

    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(
                RuntimeLayoutError(f"{label} has a non-standard value")
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeLayoutError(f"{label} is unreadable") from exc


def _relative_path(value: object) -> PurePosixPath:
    if not isinstance(value, str) or unicodedata.normalize("NFC", value) != value:
        raise RuntimeLayoutError("runtime inventory has a non-normalized path")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or path.as_posix() != value
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
        or "\\" in value
    ):
        raise RuntimeLayoutError("runtime inventory has an invalid relative path")
    return path


def _regular_file(relative: PurePosixPath) -> tuple[Path, os.stat_result]:
    current = PLUGIN_ROOT
    for part in relative.parts:
        current = current / part
        try:
            metadata = current.lstat()
        except OSError as exc:
            raise RuntimeLayoutError(
                f"runtime inventory entry is missing: {relative.as_posix()}"
            ) from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise RuntimeLayoutError(
                f"runtime inventory entry is a symlink: {relative.as_posix()}"
            )
    if not stat.S_ISREG(metadata.st_mode):
        raise RuntimeLayoutError(
            f"runtime inventory entry is not a regular file: {relative.as_posix()}"
        )
    if stat.S_IMODE(metadata.st_mode) & 0o022:
        raise RuntimeLayoutError(
            f"runtime inventory entry is group/world writable: {relative.as_posix()}"
        )
    return current, metadata


def _validate_layout() -> None:
    try:
        inventory_metadata = INVENTORY_FILE.lstat()
    except OSError as exc:
        raise RuntimeLayoutError("runtime inventory is missing") from exc
    if stat.S_ISLNK(inventory_metadata.st_mode) or not stat.S_ISREG(
        inventory_metadata.st_mode
    ):
        raise RuntimeLayoutError("runtime inventory is not a regular file")
    if stat.S_IMODE(inventory_metadata.st_mode) & 0o022:
        raise RuntimeLayoutError("runtime inventory is group/world writable")
    inventory = _strict_json(INVENTORY_FILE, "runtime inventory")
    if not isinstance(inventory, dict) or set(inventory) != {
        "schema_version",
        "runtime_protocol",
        "plugin",
        "mode_policy",
        "files",
    }:
        raise RuntimeLayoutError("runtime inventory schema is invalid")
    plugin = inventory["plugin"]
    files = inventory["files"]
    if (
        inventory["schema_version"] != 1
        or inventory["runtime_protocol"] != RUNTIME_PROTOCOL
        or inventory["mode_policy"] != "regular-not-group-or-world-writable"
        or not isinstance(plugin, dict)
        or set(plugin) != {"name", "version"}
        or not isinstance(plugin["name"], str)
        or not isinstance(plugin["version"], str)
        or not isinstance(files, list)
        or not files
    ):
        raise RuntimeLayoutError("runtime inventory schema is invalid")
    seen: set[str] = set()
    for entry in files:
        if not isinstance(entry, dict) or set(entry) != {
            "path",
            "kind",
            "size",
            "sha256",
        }:
            raise RuntimeLayoutError("runtime inventory file entry is invalid")
        relative = _relative_path(entry["path"])
        rendered = relative.as_posix()
        if rendered in seen:
            raise RuntimeLayoutError("runtime inventory has a duplicate path")
        seen.add(rendered)
        if (
            entry["kind"] != "regular"
            or isinstance(entry["size"], bool)
            or not isinstance(entry["size"], int)
            or entry["size"] < 0
            or not isinstance(entry["sha256"], str)
            or len(entry["sha256"]) != 64
            or any(character not in "0123456789abcdef" for character in entry["sha256"])
        ):
            raise RuntimeLayoutError(
                f"runtime inventory metadata is invalid: {rendered}"
            )
        path, metadata = _regular_file(relative)
        if metadata.st_size != entry["size"]:
            raise RuntimeLayoutError(f"runtime file size mismatch: {rendered}")
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            raise RuntimeLayoutError(f"runtime file is unreadable: {rendered}") from exc
        if digest != entry["sha256"]:
            raise RuntimeLayoutError(f"runtime file hash mismatch: {rendered}")

    manifest_relative = PurePosixPath(".codex-plugin/plugin.json")
    if manifest_relative.as_posix() not in seen:
        raise RuntimeLayoutError("runtime inventory does not bind the plugin manifest")
    manifest_path, _ = _regular_file(manifest_relative)
    manifest = _strict_json(manifest_path, "plugin manifest")
    if (
        not isinstance(manifest, dict)
        or manifest.get("name") != plugin["name"]
        or manifest.get("version") != plugin["version"]
        or plugin["name"] != "moondex"
        or manifest.get("skills") != "./skills/"
    ):
        raise RuntimeLayoutError("plugin manifest identity does not match runtime inventory")


def _prepare_imports() -> None:
    # Imports are anchored to this installed launcher, never the consumer cwd,
    # PYTHONPATH, a host variable, or a private installation convention.
    for directory in (PLUGIN_ROOT, PLUGIN_ROOT / "scripts"):
        value = str(directory)
        if value not in sys.path:
            sys.path.insert(0, value)


def _load_script(relative: str) -> Callable[[Sequence[str] | None], int]:
    path = PLUGIN_ROOT / relative
    module_name = "_moondex_runtime_" + path.stem.replace("-", "_")
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeLayoutError(f"cannot load installed runtime entry point: {relative}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    main = getattr(module, "main", None)
    if not callable(main):
        raise RuntimeLayoutError(f"installed runtime entry point has no main(): {relative}")
    return main


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        _validate_layout()
        if not arguments or arguments[0] in {"-h", "--help"}:
            print(USAGE, end="")
            return 0
        command, command_arguments = arguments[0], arguments[1:]
        _prepare_imports()
        if command in {"state", "preflight", "doctor"}:
            from harness_core.cli import main as controller_main

            return controller_main([command, *command_arguments])
        relative = ENTRY_POINTS.get(command)
        if relative is None:
            print(f"moondex-runtime: unknown command: {command}", file=sys.stderr)
            print(USAGE, file=sys.stderr, end="")
            return 2
        return _load_script(relative)(command_arguments)
    except RuntimeLayoutError as exc:
        print(f"MOONDEX_RUNTIME_INCOMPLETE: {exc}", file=sys.stderr)
        return 2
    except Exception:
        # Imported modules may fail before their own CLI boundary exists.
        # Do not disclose installation, repository, or consumer paths.
        print(
            "MOONDEX_RUNTIME_INCOMPLETE: installed runtime could not load or execute",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
