"""Command-line entry points for deterministic harness checks."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Sequence

from .config import ConfigError, load_config
from .state import (
    Phase, PreflightError, controller_doctor, controller_resume, controller_start,
    controller_status, controller_transition, load_json, preflight_phase,
)
from .enforcement import EnforcementError, local_indeterminate_audit, verify_local, verify_outgoing


def _persist_audit(path: Path, payload: dict[str, object]) -> None:
    """Persist audit evidence durably; callers turn any failure into a gate failure."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, sort_keys=True, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, path)
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except BaseException:
            try:
                Path(temporary_name).unlink()
            except FileNotFoundError:
                pass
            raise
    except (OSError, TypeError, ValueError) as exc:
        raise EnforcementError("AUDIT_WRITE_FAILED", "could not durably persist enforcement audit") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="harness_core")
    subparsers = parser.add_subparsers(dest="command", required=True)
    state = subparsers.add_parser("state", help="operate the host-independent project-local SDD state")
    state.add_argument("--project-root", type=Path, default=Path("."))
    state_subparsers = state.add_subparsers(dest="state_command", required=True)
    state_start = state_subparsers.add_parser("start", help="create state for a feature if absent")
    state_start.add_argument("feature")
    state_status = state_subparsers.add_parser("status", help="inspect state without changing it")
    state_status.add_argument("feature", nargs="?")
    state_resume = state_subparsers.add_parser("resume", help="calculate the next step without changing it")
    state_resume.add_argument("feature", nargs="?")
    state_transition = state_subparsers.add_parser("transition", help="advance one expected state as the orchestrator")
    state_transition.add_argument("--feature", required=True)
    state_transition.add_argument("--expected", choices=[phase.value for phase in Phase], required=True)
    state_transition.add_argument("--target", choices=[phase.value for phase in Phase], required=True)
    state_transition.add_argument("--approve", choices=("spec", "design", "plan"))
    state_transition.add_argument("--worktree", type=Path)
    state_transition.add_argument("--retry-task")
    state_doctor = state_subparsers.add_parser("doctor", help="report optional hook availability without requiring hooks")
    state_doctor.add_argument("feature", nargs="?")
    doctor = subparsers.add_parser("doctor", help="inspect project-local harness configuration")
    doctor.add_argument("--config", type=Path, default=Path(".harness/config.json"))
    preflight = subparsers.add_parser("preflight", help="run an explicit SDD preflight")
    preflight_subparsers = preflight.add_subparsers(dest="preflight_command", required=True)
    phase = preflight_subparsers.add_parser("phase", help="validate artifacts before entering a phase")
    phase.add_argument("--project-root", type=Path, default=Path("."))
    phase.add_argument("--state", type=Path, default=Path(".harness/state/pipeline.json"))
    phase.add_argument("--target-phase", choices=[phase.value for phase in Phase], required=True)
    check = preflight_subparsers.add_parser("check", help="validate branch, TDD, E2E, secret, and protected-path evidence")
    check.add_argument("--project-root", type=Path, default=Path("."))
    check.add_argument("--branch", help="branch being validated (defaults to the checked-out branch)")
    check.add_argument("--default-branch", default="main", help="repository default branch")
    check.add_argument("--changed-file", action="append", type=Path, default=[], help="project-relative changed path; repeatable")
    check.add_argument("--changed-files-file", type=Path, help="newline-delimited project-relative changed paths")
    check.add_argument("--tdd-manifest", type=Path, default=Path(".harness/state/tdd-manifest.json"))
    check.add_argument("--e2e-config", type=Path, default=Path(".harness/state/e2e-config.json"))
    check.add_argument("--allow-protected-path", action="append", type=Path, default=[])
    check.add_argument("--source", choices=("explicit", "worktree", "hook"), help="local changed-file evidence source")
    check.add_argument("--content-source", choices=("worktree", "index", "revision"), default="worktree", help="content snapshot used for secret scanning")
    check.add_argument("--content-revision", help="commit SHA used with --content-source revision")
    check.add_argument("--audit-file", type=Path, help="persist the versioned local report")
    enforce = preflight_subparsers.add_parser("enforce", help="resolve one outgoing Git range and apply shared enforcement")
    enforce.add_argument("--project-root", type=Path, default=Path("."))
    enforce.add_argument("--source", choices=("pre-push", "ci", "explicit"), required=True)
    enforce.add_argument("--target-ref", required=True)
    enforce.add_argument("--tip", required=True)
    enforce.add_argument("--remote-base")
    enforce.add_argument("--integration-base")
    enforce.add_argument("--branch", required=True)
    enforce.add_argument("--default-branch", required=True)
    enforce.add_argument("--trusted-policy", action="store_true")
    enforce.add_argument("--policy-base")
    enforce.add_argument("--audit-file", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "state":
        root = args.project_root.resolve()
        if args.state_command == "start":
            result = controller_start(root, args.feature)
        elif args.state_command == "status":
            result = controller_status(root, args.feature)
        elif args.state_command == "resume":
            result = controller_resume(root, args.feature)
        elif args.state_command == "doctor":
            result = controller_doctor(root, args.feature)
        else:
            worktree = args.worktree.resolve() if args.worktree else None
            result = controller_transition(root, feature=args.feature, expected=Phase(args.expected),
                                           target=Phase(args.target), approve=args.approve,
                                           worktree=worktree, retry_task=args.retry_task)
        print(json.dumps(result, sort_keys=True))
        # Controller outcomes are data for a human/skill to act on.  A blocked
        # next step is not a CLI crash; only malformed state and lock contention
        # are operational failures.
        return 2 if result["code"] in {"STATE_INVALID", "STATE_BUSY"} else 0
    if args.command == "doctor":
        try:
            config = load_config(args.config)
        except ConfigError as exc:
            print(f"CONFIG_INVALID: {exc}")
            return 2
        print(json.dumps({"status": "OK", "config": config}, sort_keys=True))
        return 0
    if args.command == "preflight" and args.preflight_command == "phase":
        state_path = args.project_root / args.state
        state = load_json(state_path)
        if state is None:
            print(f"PREFLIGHT_FAILED: state not found or invalid JSON: {state_path}")
            return 2
        try:
            target_phase = Phase(args.target_phase)
            preflight_phase(args.project_root, state, target_phase)
        except PreflightError as exc:
            print(f"PREFLIGHT_FAILED: {exc}")
            return 2
        print(f"PREFLIGHT_OK: {target_phase.value}")
        return 0
    if args.command == "preflight" and args.preflight_command == "check":
        changed_files = list(args.changed_file)
        source = args.source or ("explicit" if changed_files or args.changed_files_file else "worktree")
        try:
            if args.changed_files_file:
                changed_files.extend(
                    Path(line.strip())
                    for line in args.changed_files_file.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                )
            result = verify_local(
                args.project_root, source=source, changed_files=[str(path) for path in changed_files],
                branch=args.branch, default_branch=args.default_branch,
                allowed_protected_paths=[str(path) for path in args.allow_protected_path],
                content_source=args.content_source, content_revision=args.content_revision,
            )
            audit = result.audit()
            if args.audit_file:
                _persist_audit(args.audit_file, audit)
        except EnforcementError as exc:
            if args.audit_file:
                try:
                    _persist_audit(args.audit_file, local_indeterminate_audit(args.project_root, source, exc))
                except EnforcementError as audit_exc:
                    print(f"PREFLIGHT_FAILED: {audit_exc}")
                    return 2
            print(f"PREFLIGHT_FAILED: {exc}")
            return 2
        except (ConfigError, OSError, UnicodeDecodeError) as exc:
            error = EnforcementError("CHANGED_FILE_INDETERMINATE", "changed-file input is unavailable or unusable")
            if args.audit_file:
                try:
                    _persist_audit(args.audit_file, local_indeterminate_audit(args.project_root, source, error))
                except EnforcementError as audit_exc:
                    print(f"PREFLIGHT_FAILED: {audit_exc}")
                    return 2
            print(f"PREFLIGHT_FAILED: {error}")
            return 2
        print(json.dumps(audit, sort_keys=True))
        if result.status == "PASS":
            print("PREFLIGHT_OK: enforcement")
        return 0 if result.status == "PASS" else 2
    if args.command == "preflight" and args.preflight_command == "enforce":
        try:
            result = verify_outgoing(
                args.project_root, source=args.source, target_ref=args.target_ref, tip=args.tip,
                remote_base=args.remote_base, integration_base=args.integration_base,
                branch=args.branch, default_branch=args.default_branch,
                trusted_policy=args.trusted_policy, policy_base=args.policy_base,
            )
            audit = result.audit()
            if args.audit_file:
                _persist_audit(args.audit_file, audit)
        except EnforcementError as exc:
            if args.audit_file:
                try:
                    _persist_audit(args.audit_file, {
                        "schema_version": 1, "status": "FAIL", "outcomes": [{"rule": exc.code, "status": "FAIL", "remediation": str(exc)}],
                    })
                except EnforcementError as audit_exc:
                    print(f"PREFLIGHT_FAILED: {audit_exc}")
                    return 2
            print(f"PREFLIGHT_FAILED: {exc}")
            return 2
        print(json.dumps(audit, sort_keys=True))
        return 0 if result.status == "PASS" else 2
    raise AssertionError(f"Unhandled command: {args.command}")
