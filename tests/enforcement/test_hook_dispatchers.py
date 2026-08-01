from __future__ import annotations

import json
import os
import re
import signal
import shutil
import subprocess
import time
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
HOOKS_MANIFEST = REPOSITORY_ROOT / "hooks" / "hooks.json"

DISPATCH_CHAINS = {
    "Bash": (
        "hooks/dangerous-command.sh",
        "hooks/secret-detect.sh",
        "hooks/enforcement/branch-gate.sh",
        "hooks/enforcement/e2e-gate.sh",
    ),
    "Edit|Write": (
        "hooks/sensitive-file.sh",
        "hooks/file-ownership.sh",
        "hooks/enforcement/role-gate.sh",
        "hooks/enforcement/tdd-gate.sh",
    ),
}


def _pre_tool_use_registration(matcher: str) -> dict[str, object]:
    manifest = json.loads(HOOKS_MANIFEST.read_text(encoding="utf-8"))
    registrations = [
        registration
        for registration in manifest["hooks"]["PreToolUse"]
        if registration.get("matcher") == matcher
    ]
    assert len(registrations) == 1, f"expected exactly one {matcher!r} PreToolUse registration"
    return registrations[0]


def _dispatcher_source(matcher: str) -> Path:
    registration = _pre_tool_use_registration(matcher)
    commands = registration["hooks"]
    assert isinstance(commands, list)
    assert len(commands) == 1, f"{matcher!r} must expose one dispatcher command, not child hooks"
    hook = commands[0]
    assert hook.get("type") == "command"
    command = hook.get("command")
    assert isinstance(command, str)
    prefix = "${CODEX_PLUGIN_ROOT}/"
    assert command.startswith(prefix)
    relative = command.removeprefix(prefix)
    assert command == f"{prefix}{relative}", "dispatcher registration must not append shell arguments"
    assert "dispatcher" in Path(relative).name
    source = REPOSITORY_ROOT / relative
    assert source.is_file(), f"registered dispatcher does not exist: {relative}"
    return source


def _fake_child(relative: str) -> str:
    return rf"""#!/bin/bash
set -u
child={relative!r}
printf '%s\n' "$child" >> "$HOOK_TEST_LOG"
cat > "$HOOK_TEST_CAPTURE_DIR/${{child//\//_}}.stdin"
if [ "${{HOOK_TEST_FAIL_CHILD:-}}" = "$child" ]; then
  printf 'ACTIONABLE stdout: %s\n' "$child"
  printf 'ACTIONABLE stderr: %s\n' "$child" >&2
  exit "${{HOOK_TEST_FAIL_CODE:-2}}"
fi
printf 'successful stdout chatter: %s\n' "$child"
printf 'successful stderr chatter: %s\n' "$child" >&2
exit 0
"""


def _installed_dispatcher_fixture(tmp_path: Path, matcher: str) -> tuple[Path, dict[str, str], Path, Path]:
    source = _dispatcher_source(matcher)
    plugin_root = tmp_path / "opaque plugin root with spaces"
    dispatcher = plugin_root / source.relative_to(REPOSITORY_ROOT)
    dispatcher.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dispatcher)
    dispatcher.chmod(0o755)

    for relative in DISPATCH_CHAINS[matcher]:
        child = plugin_root / relative
        child.parent.mkdir(parents=True, exist_ok=True)
        child.write_text(_fake_child(relative), encoding="utf-8")
        child.chmod(0o755)

    invocation_log = tmp_path / "invocations.log"
    capture_dir = tmp_path / "captured stdin"
    capture_dir.mkdir()
    environment = os.environ.copy()
    environment.update({
        "CODEX_PLUGIN_ROOT": str(plugin_root),
        "HOOK_TEST_LOG": str(invocation_log),
        "HOOK_TEST_CAPTURE_DIR": str(capture_dir),
    })
    return dispatcher, environment, invocation_log, capture_dir


def _captured_stdin(capture_dir: Path, relative: str) -> bytes:
    return (capture_dir / f"{relative.replace('/', '_')}.stdin").read_bytes()


def _invocations(invocation_log: Path) -> list[str]:
    if not invocation_log.exists():
        return []
    return invocation_log.read_text(encoding="utf-8").splitlines()


def _wait_for_pid(pid_file: Path, timeout: float = 3.0) -> int:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pid_file.exists():
            value = pid_file.read_text(encoding="utf-8").strip()
            if value:
                return int(value)
        time.sleep(0.01)
    raise AssertionError("long-running dispatcher child did not record its PID")


def _pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait_for_pid_exit(pid: int, timeout: float = 1.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _pid_exists(pid):
            return True
        time.sleep(0.01)
    return not _pid_exists(pid)


def _long_running_child(pid_file: Path) -> str:
    return rf"""#!/bin/bash
set -u
printf '%s\n' "$$" > {str(pid_file)!r}
trap 'exit 143' TERM
trap 'exit 130' INT
while :; do
  :
done
"""


def _long_running_child_with_descendant(child_pid_file: Path, descendant_pid_file: Path) -> str:
    return rf"""#!/bin/bash
set -u
printf '%s\n' "$$" > {str(child_pid_file)!r}
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
sleep 300 &
descendant_pid=$!
printf '%s\n' "$descendant_pid" > {str(descendant_pid_file)!r}
wait "$descendant_pid"
"""


def _signal_ignoring_child_with_descendant(child_pid_file: Path, descendant_pid_file: Path) -> str:
    return rf"""#!/bin/bash
set -u
trap '' HUP INT TERM
printf '%s\n' "$$" > {str(child_pid_file)!r}
sleep 300 &
descendant_pid=$!
printf '%s\n' "$descendant_pid" > {str(descendant_pid_file)!r}
wait "$descendant_pid"
"""


def _terminate_process_group(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass


def _force_kill_process_group(process_group_id: int) -> None:
    if process_group_id <= 0:
        return
    try:
        os.killpg(process_group_id, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _force_kill_pid(pid: int) -> None:
    if pid <= 0:
        return
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def test_manifest_registers_one_dispatcher_per_pre_tool_use_matcher() -> None:
    manifest = json.loads(HOOKS_MANIFEST.read_text(encoding="utf-8"))
    registrations = manifest["hooks"]["PreToolUse"]

    assert [registration.get("matcher") for registration in registrations] == ["Bash", "Edit|Write"]
    dispatchers = [_dispatcher_source(matcher) for matcher in DISPATCH_CHAINS]
    assert dispatchers[0] != dispatchers[1]


@pytest.mark.parametrize("matcher", DISPATCH_CHAINS)
def test_dispatcher_runs_each_child_once_in_order_with_identical_stdin_and_silent_success(
    tmp_path: Path, matcher: str,
) -> None:
    dispatcher, environment, invocation_log, capture_dir = _installed_dispatcher_fixture(tmp_path, matcher)
    payload = b'  {\n  "tool_name": "Bash",\n  "tool_input": {"command": "printf \\"a b\\"\\nnext"}\n}\n\n'

    result = subprocess.run(
        (str(dispatcher),),
        cwd=tmp_path,
        env=environment,
        input=payload,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout == b""
    assert result.stderr == b""
    assert _invocations(invocation_log) == list(DISPATCH_CHAINS[matcher])
    for relative in DISPATCH_CHAINS[matcher]:
        assert _captured_stdin(capture_dir, relative) == payload


@pytest.mark.parametrize("matcher", DISPATCH_CHAINS)
@pytest.mark.parametrize("failure_code", (1, 2, 23))
def test_dispatcher_preserves_first_failure_diagnostic_and_exact_status_then_stops(
    tmp_path: Path, matcher: str, failure_code: int,
) -> None:
    dispatcher, environment, invocation_log, capture_dir = _installed_dispatcher_fixture(tmp_path, matcher)
    chain = DISPATCH_CHAINS[matcher]
    failing_child = chain[1]
    environment.update({
        "HOOK_TEST_FAIL_CHILD": failing_child,
        "HOOK_TEST_FAIL_CODE": str(failure_code),
    })
    payload = b'{"message":"spaces stay here", "multiline":"one\\ntwo"}\n'

    result = subprocess.run(
        (str(dispatcher),),
        cwd=tmp_path,
        env=environment,
        input=payload,
        capture_output=True,
        check=False,
    )

    assert result.returncode == failure_code
    assert result.stdout == f"ACTIONABLE stdout: {failing_child}\n".encode()
    assert result.stderr == f"ACTIONABLE stderr: {failing_child}\n".encode()
    assert _invocations(invocation_log) == list(chain[:2])
    assert _captured_stdin(capture_dir, chain[0]) == payload
    assert _captured_stdin(capture_dir, failing_child) == payload
    for later_child in chain[2:]:
        assert not (capture_dir / f"{later_child.replace('/', '_')}.stdin").exists()


@pytest.mark.parametrize("matcher", DISPATCH_CHAINS)
@pytest.mark.parametrize("defect", ("missing", "not-executable"))
def test_dispatcher_fails_closed_before_running_later_children(
    tmp_path: Path, matcher: str, defect: str,
) -> None:
    dispatcher, environment, invocation_log, capture_dir = _installed_dispatcher_fixture(tmp_path, matcher)
    chain = DISPATCH_CHAINS[matcher]
    defective_child = Path(environment["CODEX_PLUGIN_ROOT"]) / chain[1]
    if defect == "missing":
        defective_child.unlink()
    else:
        defective_child.chmod(0o644)

    result = subprocess.run(
        (str(dispatcher),),
        cwd=tmp_path,
        env=environment,
        input=b'{"tool_input":{"file_path":"path with spaces/file.txt"}}\n',
        capture_output=True,
        check=False,
    )

    diagnostic = (result.stdout + result.stderr).decode("utf-8", errors="replace")
    assert result.returncode == 2
    assert Path(chain[1]).name in diagnostic
    assert _invocations(invocation_log) == []
    assert list(capture_dir.iterdir()) == []


def test_bash_dispatcher_keeps_dangerous_command_inside_product_chain() -> None:
    assert DISPATCH_CHAINS["Bash"][0] == "hooks/dangerous-command.sh"


@pytest.mark.parametrize("matcher", DISPATCH_CHAINS)
@pytest.mark.parametrize("defect", ("missing", "not-executable"))
def test_dispatcher_validates_every_expected_asset_before_running_any_child(
    tmp_path: Path, matcher: str, defect: str,
) -> None:
    dispatcher, environment, invocation_log, capture_dir = _installed_dispatcher_fixture(tmp_path, matcher)
    chain = DISPATCH_CHAINS[matcher]
    defective_child = Path(environment["CODEX_PLUGIN_ROOT"]) / chain[-1]
    if defect == "missing":
        defective_child.unlink()
    else:
        defective_child.chmod(0o644)

    result = subprocess.run(
        (str(dispatcher),),
        cwd=tmp_path,
        env=environment,
        input=b'{"asset_preflight":"must happen before execution"}\n',
        capture_output=True,
        check=False,
    )

    diagnostic = (result.stdout + result.stderr).decode("utf-8", errors="replace")
    assert result.returncode == 2
    assert Path(chain[-1]).name in diagnostic
    assert _invocations(invocation_log) == []
    assert list(capture_dir.iterdir()) == []


@pytest.mark.parametrize("matcher", DISPATCH_CHAINS)
@pytest.mark.parametrize("target_kind", ("inside-alias", "outside-escape"))
def test_dispatcher_rejects_direct_child_symlink_without_executing_or_leaking_canonical_paths(
    tmp_path: Path, matcher: str, target_kind: str,
) -> None:
    dispatcher, environment, invocation_log, capture_dir = _installed_dispatcher_fixture(tmp_path, matcher)
    plugin_root = Path(environment["CODEX_PLUGIN_ROOT"])
    chain = DISPATCH_CHAINS[matcher]
    expected_child = plugin_root / chain[-1]
    expected_child.unlink()
    escape_marker = tmp_path / "escaped-child-ran.marker"

    if target_kind == "inside-alias":
        target = plugin_root / chain[0]
    else:
        target = tmp_path / "private canonical escape" / "do-not-run.sh"
        target.parent.mkdir()
        target.write_text(
            rf"""#!/bin/bash
printf 'executed\n' > {str(escape_marker)!r}
cat >/dev/null
exit 0
""",
            encoding="utf-8",
        )
        target.chmod(0o755)
    expected_child.symlink_to(os.path.relpath(target, start=expected_child.parent))

    result = subprocess.run(
        (str(dispatcher),),
        cwd=tmp_path,
        env=environment,
        input=b'{"symlink":"must not be followed"}\n',
        capture_output=True,
        check=False,
    )

    diagnostic = (result.stdout + result.stderr).decode("utf-8", errors="replace")
    assert result.returncode == 2
    assert Path(chain[-1]).name in diagnostic
    assert _invocations(invocation_log) == []
    assert list(capture_dir.iterdir()) == []
    assert not escape_marker.exists()
    assert str(plugin_root.resolve()) not in diagnostic
    assert str(target.resolve()) not in diagnostic
    assert str(tmp_path.resolve()) not in diagnostic


@pytest.mark.parametrize("matcher", DISPATCH_CHAINS)
def test_dispatcher_rejects_symlinked_parent_directory_before_any_child_runs(
    tmp_path: Path, matcher: str,
) -> None:
    dispatcher, environment, invocation_log, capture_dir = _installed_dispatcher_fixture(tmp_path, matcher)
    plugin_root = Path(environment["CODEX_PLUGIN_ROOT"])
    enforcement_parent = plugin_root / "hooks" / "enforcement"
    escaped_parent = tmp_path / "private escaped enforcement assets"
    enforcement_parent.rename(escaped_parent)
    enforcement_parent.symlink_to(os.path.relpath(escaped_parent, start=enforcement_parent.parent), target_is_directory=True)

    result = subprocess.run(
        (str(dispatcher),),
        cwd=tmp_path,
        env=environment,
        input=b'{"parent_symlink":"must fail closed"}\n',
        capture_output=True,
        check=False,
    )

    diagnostic = (result.stdout + result.stderr).decode("utf-8", errors="replace")
    expected = next(relative for relative in DISPATCH_CHAINS[matcher] if relative.startswith("hooks/enforcement/"))
    assert result.returncode == 2
    assert Path(expected).name in diagnostic
    assert _invocations(invocation_log) == []
    assert list(capture_dir.iterdir()) == []
    assert str(plugin_root.resolve()) not in diagnostic
    assert str(escaped_parent.resolve()) not in diagnostic
    assert str(tmp_path.resolve()) not in diagnostic


def _exercise_term_cleanup(
    tmp_path: Path,
    matcher: str,
    *,
    process_group: bool,
    signal_number: signal.Signals = signal.SIGTERM,
) -> dict[str, object]:
    dispatcher, environment, _, _ = _installed_dispatcher_fixture(tmp_path, matcher)
    plugin_root = Path(environment["CODEX_PLUGIN_ROOT"])
    pid_file = tmp_path / "long-running-child.pid"
    first_child = plugin_root / DISPATCH_CHAINS[matcher][0]
    first_child.write_text(_long_running_child(pid_file), encoding="utf-8")
    first_child.chmod(0o755)
    private_tmp = tmp_path / "dispatcher-private-tmp"
    private_tmp.mkdir()
    environment["TMPDIR"] = str(private_tmp)

    process = subprocess.Popen(
        (str(dispatcher),),
        cwd=tmp_path,
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    child_pid = -1
    timed_out = False
    returncode: int | None = None
    stdout = b""
    stderr = b""
    child_exited = False
    leaked_temp_paths: list[str] = []
    try:
        assert process.stdin is not None
        process.stdin.write(
            f'{{"signal":"{signal_number.name}", "payload":"captured before child"}}\n'.encode()
        )
        process.stdin.close()
        child_pid = _wait_for_pid(pid_file)
        if process_group:
            os.killpg(process.pid, signal_number)
        else:
            os.kill(process.pid, signal_number)
        try:
            returncode = process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            timed_out = True
        child_exited = _wait_for_pid_exit(child_pid)
        leaked_temp_paths = [path.name for path in private_tmp.iterdir()]
    finally:
        _terminate_process_group(process)
    if process.stdout is not None:
        stdout = process.stdout.read()
    if process.stderr is not None:
        stderr = process.stderr.read()

    return {
        "timed_out": timed_out,
        "returncode": returncode,
        "child_exited": child_exited,
        "leaked_temp_paths": leaked_temp_paths,
        "stdout": stdout,
        "stderr": stderr,
    }


@pytest.mark.parametrize("matcher", DISPATCH_CHAINS)
def test_term_to_dispatcher_promptly_terminates_and_reaps_child_with_conventional_status(
    tmp_path: Path, matcher: str,
) -> None:
    observation = _exercise_term_cleanup(tmp_path, matcher, process_group=False)

    assert observation["timed_out"] is False
    assert observation["returncode"] == 143
    assert observation["child_exited"] is True
    assert observation["leaked_temp_paths"] == []
    combined = observation["stdout"] + observation["stderr"]
    assert b"No such file" not in combined
    assert b"cat:" not in combined


@pytest.mark.parametrize("matcher", DISPATCH_CHAINS)
def test_term_to_dispatcher_process_group_cleans_child_and_capture_without_internal_errors(
    tmp_path: Path, matcher: str,
) -> None:
    observation = _exercise_term_cleanup(tmp_path, matcher, process_group=True)

    assert observation["timed_out"] is False
    assert observation["returncode"] == 143
    assert observation["child_exited"] is True
    assert observation["leaked_temp_paths"] == []
    combined = observation["stdout"] + observation["stderr"]
    assert b"No such file" not in combined
    assert b"cat:" not in combined


@pytest.mark.parametrize("matcher", DISPATCH_CHAINS)
def test_int_to_dispatcher_promptly_terminates_and_reaps_child_with_conventional_status(
    tmp_path: Path, matcher: str,
) -> None:
    observation = _exercise_term_cleanup(
        tmp_path,
        matcher,
        process_group=False,
        signal_number=signal.SIGINT,
    )

    assert observation["timed_out"] is False
    assert observation["returncode"] == 130
    assert observation["child_exited"] is True
    assert observation["leaked_temp_paths"] == []
    combined = observation["stdout"] + observation["stderr"]
    assert b"No such file" not in combined
    assert b"cat:" not in combined


DESCENDANT_SIGNAL_CASES = (
    pytest.param(signal.SIGHUP, 129, id="HUP-129"),
    pytest.param(signal.SIGINT, 130, id="INT-130"),
    pytest.param(signal.SIGTERM, 143, id="TERM-143"),
)


def _exercise_descendant_cleanup(
    tmp_path: Path,
    matcher: str,
    *,
    signal_number: signal.Signals,
    process_group: bool,
    ignore_requested_signal: bool = False,
    wait_timeout: float = 3.0,
    exit_observation_timeout: float = 0.5,
) -> dict[str, object]:
    dispatcher, environment, _, _ = _installed_dispatcher_fixture(tmp_path, matcher)
    plugin_root = Path(environment["CODEX_PLUGIN_ROOT"])
    child_pid_file = tmp_path / "direct-child.pid"
    descendant_pid_file = tmp_path / "descendant.pid"
    first_child = plugin_root / DISPATCH_CHAINS[matcher][0]
    child_source = (
        _signal_ignoring_child_with_descendant(child_pid_file, descendant_pid_file)
        if ignore_requested_signal
        else _long_running_child_with_descendant(child_pid_file, descendant_pid_file)
    )
    first_child.write_text(child_source, encoding="utf-8")
    first_child.chmod(0o755)
    private_tmp = tmp_path / "dispatcher-private-tmp"
    private_tmp.mkdir()
    environment["TMPDIR"] = str(private_tmp)

    process = subprocess.Popen(
        (str(dispatcher),),
        cwd=tmp_path,
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    direct_child_pid = -1
    descendant_pid = -1
    timed_out = False
    returncode: int | None = None
    direct_child_exited = False
    descendant_exited = False
    leaked_temp_paths: list[str] = []
    stdout = b""
    stderr = b""
    try:
        assert process.stdin is not None
        process.stdin.write(
            f'{{"signal":"{signal_number.name}", "descendant":"sleep"}}\n'.encode()
        )
        process.stdin.close()
        direct_child_pid = _wait_for_pid(child_pid_file)
        descendant_pid = _wait_for_pid(descendant_pid_file)
        if process_group:
            os.killpg(process.pid, signal_number)
        else:
            os.kill(process.pid, signal_number)
        try:
            returncode = process.wait(timeout=wait_timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
        direct_child_exited = _wait_for_pid_exit(direct_child_pid, timeout=exit_observation_timeout)
        descendant_exited = _wait_for_pid_exit(descendant_pid, timeout=exit_observation_timeout)
        leaked_temp_paths = [path.name for path in private_tmp.iterdir()]
    finally:
        # The dispatcher briefly enables job control, making the direct child
        # the leader of a distinct process group. Its descendants remain in
        # that group even after the leader exits, so clean that recorded group
        # independently from the dispatcher session.
        _force_kill_process_group(direct_child_pid)
        _terminate_process_group(process)
        if not _wait_for_pid_exit(direct_child_pid, timeout=0.1):
            _force_kill_pid(direct_child_pid)
        if not _wait_for_pid_exit(descendant_pid, timeout=0.1):
            _force_kill_pid(descendant_pid)
        _wait_for_pid_exit(direct_child_pid, timeout=0.1)
        _wait_for_pid_exit(descendant_pid, timeout=0.1)
    if process.stdout is not None:
        stdout = process.stdout.read()
    if process.stderr is not None:
        stderr = process.stderr.read()

    return {
        "timed_out": timed_out,
        "returncode": returncode,
        "direct_child_exited": direct_child_exited,
        "descendant_exited": descendant_exited,
        "leaked_temp_paths": leaked_temp_paths,
        "stdout": stdout,
        "stderr": stderr,
    }


@pytest.mark.parametrize("matcher", DISPATCH_CHAINS)
@pytest.mark.parametrize(("signal_number", "expected_status"), DESCENDANT_SIGNAL_CASES)
def test_signal_to_dispatcher_pid_cleans_real_child_descendant_and_capture(
    tmp_path: Path,
    matcher: str,
    signal_number: signal.Signals,
    expected_status: int,
) -> None:
    observation = _exercise_descendant_cleanup(
        tmp_path,
        matcher,
        signal_number=signal_number,
        process_group=False,
    )

    assert observation["timed_out"] is False
    assert observation["returncode"] == expected_status
    assert observation["direct_child_exited"] is True
    assert observation["descendant_exited"] is True
    assert observation["leaked_temp_paths"] == []
    assert observation["stdout"] == b""
    assert observation["stderr"] == b""


@pytest.mark.parametrize("matcher", DISPATCH_CHAINS)
@pytest.mark.parametrize(("signal_number", "expected_status"), DESCENDANT_SIGNAL_CASES)
def test_signal_to_dispatcher_process_group_cleans_real_child_descendant_and_capture(
    tmp_path: Path,
    matcher: str,
    signal_number: signal.Signals,
    expected_status: int,
) -> None:
    observation = _exercise_descendant_cleanup(
        tmp_path,
        matcher,
        signal_number=signal_number,
        process_group=True,
    )

    assert observation["timed_out"] is False
    assert observation["returncode"] == expected_status
    assert observation["direct_child_exited"] is True
    assert observation["descendant_exited"] is True
    assert observation["leaked_temp_paths"] == []
    assert observation["stdout"] == b""
    assert observation["stderr"] == b""


@pytest.mark.parametrize("matcher", DISPATCH_CHAINS)
@pytest.mark.parametrize(("signal_number", "expected_status"), DESCENDANT_SIGNAL_CASES)
def test_signal_to_dispatcher_pid_force_cleans_anchored_group_before_waiting_for_ignoring_child(
    tmp_path: Path,
    matcher: str,
    signal_number: signal.Signals,
    expected_status: int,
) -> None:
    observation = _exercise_descendant_cleanup(
        tmp_path,
        matcher,
        signal_number=signal_number,
        process_group=False,
        ignore_requested_signal=True,
        wait_timeout=0.75,
        exit_observation_timeout=0.1,
    )

    assert observation["timed_out"] is False
    assert observation["returncode"] == expected_status
    assert observation["direct_child_exited"] is True
    assert observation["descendant_exited"] is True
    assert observation["leaked_temp_paths"] == []
    assert observation["stdout"] == b""
    assert observation["stderr"] == b""


@pytest.mark.parametrize("matcher", DISPATCH_CHAINS)
@pytest.mark.parametrize(("signal_number", "expected_status"), DESCENDANT_SIGNAL_CASES)
def test_signal_to_dispatcher_process_group_force_cleans_anchored_group_before_waiting_for_ignoring_child(
    tmp_path: Path,
    matcher: str,
    signal_number: signal.Signals,
    expected_status: int,
) -> None:
    observation = _exercise_descendant_cleanup(
        tmp_path,
        matcher,
        signal_number=signal_number,
        process_group=True,
        ignore_requested_signal=True,
        wait_timeout=0.75,
        exit_observation_timeout=0.1,
    )

    assert observation["timed_out"] is False
    assert observation["returncode"] == expected_status
    assert observation["direct_child_exited"] is True
    assert observation["descendant_exited"] is True
    assert observation["leaked_temp_paths"] == []
    assert observation["stdout"] == b""
    assert observation["stderr"] == b""


def _instrument_dispatcher_after_wait(dispatcher: Path) -> None:
    source = dispatcher.read_text(encoding="utf-8")
    needle = '  wait "$ACTIVE_CHILD_PID"\n  status=$?\n'
    pause = r'''  wait "$ACTIVE_CHILD_PID"
  printf '%s\n' "$ACTIVE_CHILD_PID" > "$HOOK_TEST_AFTER_WAIT_MARKER"
  while [ ! -e "$HOOK_TEST_AFTER_WAIT_RELEASE" ]; do
    :
  done
  status=$?
'''
    assert source.count(needle) == 1
    dispatcher.write_text(source.replace(needle, pause), encoding="utf-8")
    dispatcher.chmod(0o755)


def _sentinel_program(ready_file: Path, signal_file: Path) -> str:
    return f"""import os
import signal
from pathlib import Path

ready = Path({str(ready_file)!r})
observed = Path({str(signal_file)!r})

def handle(signum, _frame):
    observed.write_text(str(signum), encoding="utf-8")
    os._exit(0)

for candidate in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM):
    signal.signal(candidate, handle)
ready.write_text(str(os.getpid()), encoding="utf-8")
while True:
    signal.pause()
"""


def _child_that_leaves_sentinel_group(
    child_pid_file: Path,
    sentinel_pid_file: Path,
    sentinel_program: Path,
    sentinel_ready: Path,
) -> str:
    return rf"""#!/bin/bash
set -u
printf '%s\n' "$$" > {str(child_pid_file)!r}
python3 {str(sentinel_program)!r} &
sentinel_pid=$!
printf '%s\n' "$sentinel_pid" > {str(sentinel_pid_file)!r}
while [ ! -e {str(sentinel_ready)!r} ]; do
  :
done
exit 0
"""


def _exercise_after_wait_signal(
    tmp_path: Path,
    matcher: str,
    signal_number: signal.Signals,
) -> dict[str, object]:
    dispatcher, environment, _, _ = _installed_dispatcher_fixture(tmp_path, matcher)
    _instrument_dispatcher_after_wait(dispatcher)
    plugin_root = Path(environment["CODEX_PLUGIN_ROOT"])
    child_pid_file = tmp_path / "completed-direct-child.pid"
    sentinel_pid_file = tmp_path / "unrelated-sentinel.pid"
    sentinel_ready = tmp_path / "unrelated-sentinel.ready"
    sentinel_signal = tmp_path / "unrelated-sentinel.signal"
    sentinel_program = tmp_path / "unrelated-sentinel.py"
    sentinel_program.write_text(
        _sentinel_program(sentinel_ready, sentinel_signal),
        encoding="utf-8",
    )
    first_child = plugin_root / DISPATCH_CHAINS[matcher][0]
    first_child.write_text(
        _child_that_leaves_sentinel_group(
            child_pid_file,
            sentinel_pid_file,
            sentinel_program,
            sentinel_ready,
        ),
        encoding="utf-8",
    )
    first_child.chmod(0o755)

    pause_marker = tmp_path / "dispatcher-after-wait.marker"
    release_marker = tmp_path / "dispatcher-after-wait.release"
    private_tmp = tmp_path / "dispatcher-private-tmp"
    private_tmp.mkdir()
    environment.update({
        "HOOK_TEST_AFTER_WAIT_MARKER": str(pause_marker),
        "HOOK_TEST_AFTER_WAIT_RELEASE": str(release_marker),
        "TMPDIR": str(private_tmp),
    })

    process = subprocess.Popen(
        (str(dispatcher),),
        cwd=tmp_path,
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    direct_child_pid = -1
    sentinel_pid = -1
    timed_out = False
    returncode: int | None = None
    leaked_temp_paths: list[str] = []
    stdout = b""
    stderr = b""
    sentinel_survived = False
    observed_sentinel_signal: str | None = None
    try:
        assert process.stdin is not None
        process.stdin.write(b'{"after_wait":"signal race"}\n')
        process.stdin.close()
        direct_child_pid = _wait_for_pid(child_pid_file)
        sentinel_pid = _wait_for_pid(sentinel_pid_file)
        paused_child_pid = _wait_for_pid(pause_marker)
        assert paused_child_pid == direct_child_pid
        assert _wait_for_pid_exit(direct_child_pid, timeout=0.5)
        os.kill(process.pid, signal_number)
        time.sleep(0.05)
        release_marker.touch()
        try:
            returncode = process.wait(timeout=1.5)
        except subprocess.TimeoutExpired:
            timed_out = True
        sentinel_survived = not _wait_for_pid_exit(sentinel_pid, timeout=0.2)
        if sentinel_signal.exists():
            observed_sentinel_signal = sentinel_signal.read_text(encoding="utf-8").strip()
        leaked_temp_paths = [path.name for path in private_tmp.iterdir()]
    finally:
        _force_kill_process_group(direct_child_pid)
        if process.poll() is None:
            _terminate_process_group(process)
        if not _wait_for_pid_exit(sentinel_pid, timeout=0.1):
            _force_kill_pid(sentinel_pid)
        _wait_for_pid_exit(sentinel_pid, timeout=0.2)
    if process.stdout is not None:
        stdout = process.stdout.read()
    if process.stderr is not None:
        stderr = process.stderr.read()

    return {
        "timed_out": timed_out,
        "returncode": returncode,
        "sentinel_survived": sentinel_survived,
        "sentinel_signal": observed_sentinel_signal,
        "leaked_temp_paths": leaked_temp_paths,
        "stdout": stdout,
        "stderr": stderr,
    }


@pytest.mark.parametrize("matcher", DISPATCH_CHAINS)
@pytest.mark.parametrize(("signal_number", "expected_status"), DESCENDANT_SIGNAL_CASES)
def test_signal_after_wait_does_not_target_stale_child_group(
    tmp_path: Path,
    matcher: str,
    signal_number: signal.Signals,
    expected_status: int,
) -> None:
    observation = _exercise_after_wait_signal(tmp_path, matcher, signal_number)

    assert observation["timed_out"] is False
    assert observation["returncode"] == expected_status
    assert observation["sentinel_signal"] is None
    assert observation["sentinel_survived"] is True
    assert observation["leaked_temp_paths"] == []
    assert observation["stdout"] == b""
    assert observation["stderr"] == b""


@pytest.mark.parametrize("matcher", DISPATCH_CHAINS)
def test_relay_verifies_active_child_is_exact_current_job_before_signalling_group(matcher: str) -> None:
    source = _dispatcher_source(matcher).read_text(encoding="utf-8")
    relay = source.split("relay_signal() {", 1)[1].split("\n}", 1)[0]
    group_kill = relay.index('kill -s "$signal_name" -- "-$ACTIVE_CHILD_PID"')

    jobs_query = relay.index("jobs -pr")
    exact_membership = re.search(
        r'(?:"\$job_pid"\s*=\s*"\$ACTIVE_CHILD_PID"|"\$ACTIVE_CHILD_PID"\s*=\s*"\$job_pid")',
        relay,
    )
    assert exact_membership is not None
    assert jobs_query < exact_membership.start() < group_kill
