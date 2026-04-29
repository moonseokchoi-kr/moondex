#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
SOURCE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"
TARGET_ROOT="$PWD"
INSTALL_CLI=false

usage() {
  cat <<'USAGE'
Usage: scripts/setup-moondex.sh [--target-root <path>] [--install-cli]

Build Moondex and prepare a target repository for runtime use.

Default behavior:
  - cargo build --release -p moondex
  - copy target/release/moondex to <target>/.moondex/bin/moondex
  - initialize <target>/.moondex/state
  - run status and audit-state smoke checks

Options:
  --target-root <path>  Target repository to initialize. Defaults to cwd.
  --install-cli        Also run cargo install --path crates/moondex.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --target-root)
      if [ "$#" -lt 2 ]; then
        echo "setup-moondex: --target-root requires a path" >&2
        exit 2
      fi
      TARGET_ROOT="$2"
      shift 2
      ;;
    --install-cli)
      INSTALL_CLI=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "setup-moondex: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if ! TARGET_ROOT="$(cd "$TARGET_ROOT" 2>/dev/null && pwd -P)"; then
  echo "setup-moondex: target root does not exist" >&2
  exit 2
fi

if [ ! -f "$SOURCE_ROOT/Cargo.toml" ] || [ ! -f "$SOURCE_ROOT/crates/moondex/Cargo.toml" ]; then
  echo "setup-moondex: source root does not look like the Moondex repository: $SOURCE_ROOT" >&2
  exit 1
fi

if ! command -v cargo >/dev/null 2>&1; then
  echo "setup-moondex: cargo is required to build Moondex from source" >&2
  echo "setup-moondex: run scripts/doctor.sh for diagnostics" >&2
  exit 1
fi

echo "Moondex setup"
echo "Source root: $SOURCE_ROOT"
echo "Target root: $TARGET_ROOT"
echo

echo "Building release CLI..."
(cd "$SOURCE_ROOT" && cargo build --release -p moondex)

RELEASE_CLI="$SOURCE_ROOT/target/release/moondex"
TARGET_BIN_DIR="$TARGET_ROOT/.moondex/bin"
TARGET_CLI="$TARGET_BIN_DIR/moondex"

if [ ! -x "$RELEASE_CLI" ]; then
  echo "setup-moondex: release binary was not created: $RELEASE_CLI" >&2
  exit 1
fi

echo "Installing repo-local CLI..."
mkdir -p "$TARGET_BIN_DIR"
cp "$RELEASE_CLI" "$TARGET_CLI"
chmod 0755 "$TARGET_CLI"

if [ "$INSTALL_CLI" = "true" ]; then
  echo "Installing global CLI with cargo install..."
  (cd "$SOURCE_ROOT" && cargo install --path crates/moondex)
fi

echo "Initializing runtime state..."
(cd "$TARGET_ROOT" && "$TARGET_CLI" init)

echo "Running status smoke..."
(cd "$TARGET_ROOT" && "$TARGET_CLI" status --json)

echo "Running audit-state smoke..."
(cd "$TARGET_ROOT" && "$TARGET_CLI" api audit-state --json)

echo
echo "Moondex is ready."
echo "Command prefix: $TARGET_CLI"
echo "State root: $TARGET_ROOT/.moondex/state"
