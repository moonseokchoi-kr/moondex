#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
SOURCE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"
TARGET_ROOT="$PWD"
JSON=false

usage() {
  cat <<'USAGE'
Usage: scripts/doctor.sh [--json] [--target-root <path>]

Diagnose whether Moondex can run for a target repository.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --json)
      JSON=true
      shift
      ;;
    --target-root)
      if [ "$#" -lt 2 ]; then
        echo "doctor: --target-root requires a path" >&2
        exit 2
      fi
      TARGET_ROOT="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "doctor: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if ! TARGET_ROOT="$(cd "$TARGET_ROOT" 2>/dev/null && pwd -P)"; then
  echo "doctor: target root does not exist" >&2
  exit 2
fi

json_escape() {
  local value="$1"
  value=${value//\\/\\\\}
  value=${value//\"/\\\"}
  value=${value//$'\n'/\\n}
  value=${value//$'\r'/}
  printf '%s' "$value"
}

bool_json() {
  if [ "$1" = "true" ]; then
    printf 'true'
  else
    printf 'false'
  fi
}

check_status() {
  if [ "$1" = "ok" ]; then
    printf 'ok'
  elif [ "$1" = "skipped" ]; then
    printf 'skipped'
  else
    printf 'missing'
  fi
}

PLUGIN_STATUS=missing
PLUGIN_DETAIL="$SOURCE_ROOT/.codex-plugin/plugin.json"
if [ -f "$SOURCE_ROOT/.codex-plugin/plugin.json" ]; then
  PLUGIN_STATUS=ok
fi

SKILLS_STATUS=missing
SKILLS_DETAIL="$SOURCE_ROOT/skills"
MISSING_SKILLS=""
for skill in moondex-implementation-workflow moondex-runtime moondex-cmux moondex-task-creator moondex-task-planner moondex-wave-dispatcher moondex-diagnostics moondex-team-designer; do
  if [ ! -f "$SOURCE_ROOT/skills/$skill/SKILL.md" ]; then
    MISSING_SKILLS="$MISSING_SKILLS $skill"
  fi
done
if [ -z "$MISSING_SKILLS" ]; then
  SKILLS_STATUS=ok
else
  SKILLS_DETAIL="missing:$MISSING_SKILLS"
fi

RUSTC_STATUS=missing
RUSTC_DETAIL="rustc not found"
if command -v rustc >/dev/null 2>&1; then
  RUSTC_STATUS=ok
  RUSTC_DETAIL="$(rustc --version 2>&1)"
fi

CARGO_STATUS=missing
CARGO_DETAIL="cargo not found"
if command -v cargo >/dev/null 2>&1; then
  CARGO_STATUS=ok
  CARGO_DETAIL="$(cargo --version 2>&1)"
fi

CLI_PATH_STATUS=missing
CLI_PATH_DETAIL="moondex not found in PATH"
CLI_PATH=""
if CLI_PATH="$(command -v moondex 2>/dev/null)"; then
  CLI_PATH_STATUS=ok
  CLI_PATH_DETAIL="$CLI_PATH"
fi

LOCAL_CLI="$TARGET_ROOT/.moondex/bin/moondex"
CLI_LOCAL_STATUS=missing
CLI_LOCAL_DETAIL="$LOCAL_CLI"
if [ -x "$LOCAL_CLI" ]; then
  CLI_LOCAL_STATUS=ok
fi

COMMAND_PREFIX=""
COMMAND_SOURCE=missing
if [ "$CLI_PATH_STATUS" = "ok" ]; then
  COMMAND_PREFIX="$CLI_PATH"
  COMMAND_SOURCE=path
elif [ "$CLI_LOCAL_STATUS" = "ok" ]; then
  COMMAND_PREFIX="$LOCAL_CLI"
  COMMAND_SOURCE=repo-local
fi

RUNTIME_STATE_STATUS=missing
RUNTIME_STATE_DETAIL="$TARGET_ROOT/.moondex/state"
if [ -d "$TARGET_ROOT/.moondex/state" ]; then
  RUNTIME_STATE_STATUS=ok
fi

STATUS_STATUS=skipped
STATUS_DETAIL="requires command prefix and existing .moondex/state"
AUDIT_STATUS=skipped
AUDIT_DETAIL="requires command prefix and existing .moondex/state"
if [ -n "$COMMAND_PREFIX" ] && [ "$RUNTIME_STATE_STATUS" = "ok" ]; then
  STATUS_OUTPUT="$(cd "$TARGET_ROOT" && "$COMMAND_PREFIX" status --json 2>&1)"
  STATUS_CODE=$?
  if [ "$STATUS_CODE" -eq 0 ]; then
    STATUS_STATUS=ok
    STATUS_DETAIL="status ok"
  else
    STATUS_STATUS=failed
    STATUS_DETAIL="$STATUS_OUTPUT"
  fi

  AUDIT_OUTPUT="$(cd "$TARGET_ROOT" && "$COMMAND_PREFIX" api audit-state --json 2>&1)"
  AUDIT_CODE=$?
  if [ "$AUDIT_CODE" -eq 0 ]; then
    AUDIT_STATUS=ok
    AUDIT_DETAIL="audit-state ok"
  else
    AUDIT_STATUS=failed
    AUDIT_DETAIL="$AUDIT_OUTPUT"
  fi
fi

SETUP_REQUIRED=false
if [ -z "$COMMAND_PREFIX" ] || [ "$RUNTIME_STATE_STATUS" != "ok" ]; then
  SETUP_REQUIRED=true
fi

CAN_SETUP=false
if [ "$CARGO_STATUS" = "ok" ]; then
  CAN_SETUP=true
fi

OK=true
for status in "$PLUGIN_STATUS" "$SKILLS_STATUS" "$RUNTIME_STATE_STATUS" "$STATUS_STATUS" "$AUDIT_STATUS"; do
  if [ "$status" != "ok" ]; then
    OK=false
  fi
done
if [ -z "$COMMAND_PREFIX" ]; then
  OK=false
fi

RECOMMENDED_ACTION="Moondex is ready. Use: $COMMAND_PREFIX"
if [ "$PLUGIN_STATUS" != "ok" ] || [ "$SKILLS_STATUS" != "ok" ]; then
  RECOMMENDED_ACTION="Reinstall or repair the Moondex plugin package."
elif [ -z "$COMMAND_PREFIX" ] && [ "$CAN_SETUP" = "true" ]; then
  RECOMMENDED_ACTION="$SCRIPT_DIR/setup-moondex.sh --target-root \"$TARGET_ROOT\""
elif [ -z "$COMMAND_PREFIX" ]; then
  RECOMMENDED_ACTION="Install Cargo/Rust or provide a prebuilt moondex CLI, then run setup-moondex.sh."
elif [ "$RUNTIME_STATE_STATUS" != "ok" ]; then
  RECOMMENDED_ACTION="$SCRIPT_DIR/setup-moondex.sh --target-root \"$TARGET_ROOT\""
elif [ "$STATUS_STATUS" = "failed" ] || [ "$AUDIT_STATUS" = "failed" ]; then
  RECOMMENDED_ACTION="Inspect the failed status/audit output and repair .moondex/state."
fi

if [ "$JSON" = "true" ]; then
  cat <<JSON
{
  "ok": $(bool_json "$OK"),
  "source_root": "$(json_escape "$SOURCE_ROOT")",
  "target_root": "$(json_escape "$TARGET_ROOT")",
  "command_prefix": "$(json_escape "$COMMAND_PREFIX")",
  "command_source": "$(json_escape "$COMMAND_SOURCE")",
  "setup_required": $(bool_json "$SETUP_REQUIRED"),
  "can_setup": $(bool_json "$CAN_SETUP"),
  "recommended_action": "$(json_escape "$RECOMMENDED_ACTION")",
  "checks": {
    "plugin_manifest": { "status": "$(json_escape "$PLUGIN_STATUS")", "detail": "$(json_escape "$PLUGIN_DETAIL")" },
    "skills": { "status": "$(json_escape "$SKILLS_STATUS")", "detail": "$(json_escape "$SKILLS_DETAIL")" },
    "rustc": { "status": "$(json_escape "$RUSTC_STATUS")", "detail": "$(json_escape "$RUSTC_DETAIL")" },
    "cargo": { "status": "$(json_escape "$CARGO_STATUS")", "detail": "$(json_escape "$CARGO_DETAIL")" },
    "cli_path": { "status": "$(json_escape "$CLI_PATH_STATUS")", "detail": "$(json_escape "$CLI_PATH_DETAIL")" },
    "cli_local": { "status": "$(json_escape "$CLI_LOCAL_STATUS")", "detail": "$(json_escape "$CLI_LOCAL_DETAIL")" },
    "runtime_state": { "status": "$(json_escape "$RUNTIME_STATE_STATUS")", "detail": "$(json_escape "$RUNTIME_STATE_DETAIL")" },
    "status": { "status": "$(json_escape "$STATUS_STATUS")", "detail": "$(json_escape "$STATUS_DETAIL")" },
    "audit_state": { "status": "$(json_escape "$AUDIT_STATUS")", "detail": "$(json_escape "$AUDIT_DETAIL")" }
  }
}
JSON
  exit 0
fi

echo "Moondex Doctor"
echo
echo "Source root: $SOURCE_ROOT"
echo "Target root: $TARGET_ROOT"
echo
echo "Plugin manifest: $(check_status "$PLUGIN_STATUS") ($PLUGIN_DETAIL)"
echo "Skills: $(check_status "$SKILLS_STATUS") ($SKILLS_DETAIL)"
echo "Rust: $(check_status "$RUSTC_STATUS") ($RUSTC_DETAIL)"
echo "Cargo: $(check_status "$CARGO_STATUS") ($CARGO_DETAIL)"
echo "CLI in PATH: $(check_status "$CLI_PATH_STATUS") ($CLI_PATH_DETAIL)"
echo "Repo-local CLI: $(check_status "$CLI_LOCAL_STATUS") ($CLI_LOCAL_DETAIL)"
echo "Runtime state: $(check_status "$RUNTIME_STATE_STATUS") ($RUNTIME_STATE_DETAIL)"
echo "Status smoke: $STATUS_STATUS ($STATUS_DETAIL)"
echo "Audit smoke: $AUDIT_STATUS ($AUDIT_DETAIL)"
echo
if [ -n "$COMMAND_PREFIX" ]; then
  echo "Command prefix: $COMMAND_PREFIX"
else
  echo "Command prefix: unavailable"
fi
echo "Setup required: $SETUP_REQUIRED"
echo "Next step: $RECOMMENDED_ACTION"
