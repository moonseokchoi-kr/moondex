#!/bin/bash
# Run the Bash PreToolUse policy chain behind one registered hook.

set -u

ACTIVE_CHILD_PID=""
SIGNAL_STATUS=0
TEMP_DIR=""
CLEANED_UP=0

cleanup() {
  [ "$CLEANED_UP" -eq 0 ] || return
  CLEANED_UP=1
  if [ -n "$TEMP_DIR" ] && [ -d "$TEMP_DIR" ]; then
    rm -rf "$TEMP_DIR" 2>/dev/null
  fi
}

relay_signal() {
  local signal_name="$1"
  local job_pid jobs_file
  local active_job=false
  SIGNAL_STATUS="$2"

  if [ -n "$ACTIVE_CHILD_PID" ]; then
    # Validate the anchor against this shell's live job table. A completed
    # child can leave unrelated processes under the old numeric PGID, so an
    # ACTIVE_CHILD_PID value alone is not authority to signal that group.
    jobs_file="$TEMP_DIR/running-jobs"
    jobs -pr > "$jobs_file" 2>/dev/null || true
    while IFS= read -r job_pid; do
      if [ "$job_pid" = "$ACTIVE_CHILD_PID" ]; then
        active_job=true
        break
      fi
    done < "$jobs_file"
    if [ "$active_job" != true ]; then
      return
    fi

    # Monitor mode makes the direct child the leader of its own process group.
    # Signal the negative group id so helpers spawned by a gate cannot survive
    # the dispatcher. `--` keeps the negative operand from option parsing.
    builtin kill -s "$signal_name" -- "-$ACTIVE_CHILD_PID" 2>/dev/null || true
    # Immediately force-clean that still-anchored group. A gate or descendant
    # may explicitly ignore the requested signal; doing this in the trap keeps
    # the group identity live and avoids a post-wait stale numeric PGID.
    builtin kill -s KILL -- "-$ACTIVE_CHILD_PID" 2>/dev/null || true
    return
  fi
  exit "$SIGNAL_STATUS"
}

trap cleanup EXIT
trap 'relay_signal HUP 129' HUP
trap 'relay_signal INT 130' INT
trap 'relay_signal TERM 143' TERM

resolve_script_dir() {
  local source="${BASH_SOURCE[0]}"
  local directory target

  while [ -L "$source" ]; do
    directory=$(cd -P "$(dirname "$source")" 2>/dev/null && pwd) || return 1
    target=$(readlink "$source") || return 1
    case "$target" in
      /*) source="$target" ;;
      *) source="$directory/$target" ;;
    esac
  done

  cd -P "$(dirname "$source")" 2>/dev/null && pwd
}

SCRIPT_DIR=$(resolve_script_dir) || {
  printf '%s\n' 'Hook dispatcher could not resolve its installed plugin location.' >&2
  exit 2
}
PLUGIN_ROOT=$(cd -P "$SCRIPT_DIR/.." 2>/dev/null && pwd) || {
  printf '%s\n' 'Hook dispatcher could not resolve its installed plugin root.' >&2
  exit 2
}

umask 077
TEMP_DIR=$(mktemp -d "${TMPDIR:-/tmp}/moondex-hook-dispatch.XXXXXX" 2>/dev/null) || {
  printf '%s\n' 'Hook dispatcher could not create its private input buffer.' >&2
  exit 2
}

PAYLOAD="$TEMP_DIR/stdin"
CHILD_STDOUT="$TEMP_DIR/stdout"
CHILD_STDERR="$TEMP_DIR/stderr"
if ! cat 2>/dev/null > "$PAYLOAD"; then
  printf '%s\n' 'Hook dispatcher could not capture the hook input.' >&2
  exit 2
fi

CHILDREN=(
  "hooks/dangerous-command.sh"
  "hooks/secret-detect.sh"
  "hooks/enforcement/branch-gate.sh"
  "hooks/enforcement/e2e-gate.sh"
)

# Validate the complete chain before executing any policy. Every expected
# component below the canonical plugin root must be a real directory/file,
# never an alias to another installed or external asset.
for relative in "${CHILDREN[@]}"; do
  child="$PLUGIN_ROOT/$relative"
  cursor="$PLUGIN_ROOT"
  invalid=false
  IFS='/' read -r -a components <<< "$relative"
  last_index=$((${#components[@]} - 1))
  for index in "${!components[@]}"; do
    cursor="$cursor/${components[$index]}"
    if [ -L "$cursor" ]; then
      invalid=true
      break
    fi
    if [ "$index" -lt "$last_index" ] && [ ! -d "$cursor" ]; then
      invalid=true
      break
    fi
  done

  canonical_parent=$(cd -P "$(dirname "$child")" 2>/dev/null && pwd) || canonical_parent=""
  canonical_child="$canonical_parent/$(basename "$child")"
  expected_child="$PLUGIN_ROOT/$relative"
  case "$canonical_child" in
    "$PLUGIN_ROOT"/*) ;;
    *) invalid=true ;;
  esac

  if [ "$canonical_child" != "$expected_child" ] || [ ! -f "$child" ] || [ ! -x "$child" ]; then
    invalid=true
  fi
  if [ "$invalid" = true ]; then
    printf 'Hook dispatcher cannot run required child: %s\n' "$(basename "$relative")" >&2
    exit 2
  fi
done

for relative in "${CHILDREN[@]}"; do
  child="$PLUGIN_ROOT/$relative"
  # Non-interactive Bash starts ordinary background jobs with SIGINT ignored.
  # Enable monitor mode only while forking so the child starts with normal
  # signal dispositions, then disable it before wait to suppress job notices.
  set -m
  "$child" < "$PAYLOAD" > "$CHILD_STDOUT" 2> "$CHILD_STDERR" &
  ACTIVE_CHILD_PID=$!
  set +m
  wait "$ACTIVE_CHILD_PID"
  status=$?
  if [ "$SIGNAL_STATUS" -ne 0 ]; then
    # A trapped signal interrupts wait. Wait again after relaying it so the
    # child is reaped before EXIT removes capture files.
    wait "$ACTIVE_CHILD_PID" 2>/dev/null || true
  fi
  ACTIVE_CHILD_PID=""
  if [ "$SIGNAL_STATUS" -ne 0 ]; then
    exit "$SIGNAL_STATUS"
  fi
  if [ "$status" -ne 0 ]; then
    cat "$CHILD_STDOUT"
    cat "$CHILD_STDERR" >&2
    exit "$status"
  fi
done

exit 0
