#!/usr/bin/env bash
set -euo pipefail

payload="${1:-}"
if [[ -z "$payload" ]]; then
  payload="$(cat)"
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"

if [[ -x "$repo_root/target/debug/moondex" ]]; then
  output="$("$repo_root/target/debug/moondex" api validate-role-transfer --input "$payload" --json)"
else
  output="$(cd "$repo_root" && cargo run -q -p moondex -- api validate-role-transfer --input "$payload" --json)"
fi

printf '%s\n' "$output"

python3 -c 'import json, sys; data=json.load(sys.stdin); sys.exit(0 if data.get("data", {}).get("valid") is True else 1)' <<<"$output"
