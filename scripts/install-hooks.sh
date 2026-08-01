#!/usr/bin/env bash
# Install optional local fast-feedback hooks around the shared verifier.
set -euo pipefail

root="$(git rev-parse --show-toplevel)"
install_hook() {
  local hook="$1" existing="$root/.git/hooks/$1" preserved="$root/.git/hooks/moondex-user-$1"
  if [[ -e "$existing" && ! -e "$preserved" ]]; then
    mv "$existing" "$preserved"
  fi
  cat > "$existing" <<EOF
#!/usr/bin/env bash
set -euo pipefail
root="\$(git rev-parse --show-toplevel)"
preserved="\$root/.git/hooks/moondex-user-$hook"
if [[ -x "\$preserved" ]]; then "\$preserved" "\$@"; fi
branch="\$(git branch --show-current)"
args=(--project-root "\$root" --default-branch "\${DEFAULT_BRANCH:-main}" --source hook)
append_name_status_paths() {
  local status first second
  while IFS= read -r -d '' status; do
    if ! IFS= read -r -d '' first; then
      echo "PREFLIGHT_FAILED: CHANGED_FILE_INDETERMINATE: malformed Git name-status output" >&2
      return 2
    fi
    args+=(--changed-file "\$first")
    if [[ "\$status" == R* || "\$status" == C* ]]; then
      if ! IFS= read -r -d '' second; then
        echo "PREFLIGHT_FAILED: CHANGED_FILE_INDETERMINATE: rename/copy lacks both paths" >&2
        return 2
      fi
      args+=(--changed-file "\$second")
    fi
  done
}
EOF
  if [[ "$hook" == "pre-commit" ]]; then
    cat >> "$existing" <<'EOF'
# Include deleted paths as well: a staged removal of a protected harness asset
# must be checked by the same shared verifier as an edit or rename.
append_name_status_paths < <(git diff --cached --name-status -z -M -C --diff-filter=ACDMRT)
cd "$root"
python3 scripts/verify.py --content-source index --branch "$branch" "${args[@]}"
EOF
  else
    cat >> "$existing" <<'EOF'
# Inspect every outgoing commit independently.  Both changed paths and all
# policy/evidence/content inputs are read from that commit's tree, so a later
# deletion or an unstaged worktree file cannot hide an earlier bad commit.
updates=()
while read -r local_ref local_sha remote_ref remote_sha; do
  if [[ -z "$local_ref" || -z "$local_sha" || -z "$remote_ref" || -z "$remote_sha" ]]; then
    echo "PREFLIGHT_FAILED: REMOTE_REF_UNSUPPORTED: malformed pre-push update" >&2
    exit 2
  fi
  if [[ ! "$remote_ref" =~ ^refs/heads/(.+)$ ]]; then
    echo "PREFLIGHT_FAILED: REMOTE_REF_UNSUPPORTED: expected refs/heads/<branch>, got $remote_ref" >&2
    exit 2
  fi
  remote_branch="${BASH_REMATCH[1]}"
  if [[ "$remote_branch" == */../* || "$remote_branch" == .. || "$remote_branch" == */. || "$remote_branch" == . ]]; then
    echo "PREFLIGHT_FAILED: REMOTE_REF_UNSUPPORTED: invalid target branch $remote_ref" >&2
    exit 2
  fi
  # A branch deletion has no outgoing commit snapshot to validate.  Its target
  # was still required to be a normal branch ref above.
  [[ "$local_sha" =~ ^0+$ ]] || updates+=("$local_sha $remote_sha $remote_branch")
done
if (( ${#updates[@]} > 1 )); then
  echo "PREFLIGHT_FAILED: MULTI_REF_UNSUPPORTED: run one local ref update at a time" >&2
  exit 2
fi
for update in "${updates[@]}"; do
  read -r local_sha remote_sha remote_branch <<<"$update"
  commits=()
  if [[ "$remote_sha" =~ ^0+$ ]]; then
    # Initial push: commits not reachable from any configured remote are the
    # local outgoing set.  This is intentionally local-first, not a hosted-CI
    # ancestry assertion.
    while IFS= read -r commit; do commits+=("$commit"); done < <(git rev-list --reverse "$local_sha" --not --remotes)
  else
    while IFS= read -r commit; do commits+=("$commit"); done < <(git rev-list --reverse "$remote_sha..$local_sha")
  fi
  if (( ${#commits[@]} == 0 )); then
    echo "PREFLIGHT_FAILED: RANGE_UNRESOLVED: no outgoing commits could be resolved" >&2
    exit 2
  fi
  for commit in "${commits[@]}"; do
    args_for_commit=(--branch "$remote_branch" "${args[@]}")
    append_name_status_paths_for_commit() {
      local status first second
      while IFS= read -r -d '' status; do
        if ! IFS= read -r -d '' first; then
          echo "PREFLIGHT_FAILED: CHANGED_FILE_INDETERMINATE: malformed Git name-status output" >&2
          return 2
        fi
        args_for_commit+=(--changed-file "$first")
        if [[ "$status" == R* || "$status" == C* ]]; then
          if ! IFS= read -r -d '' second; then
            echo "PREFLIGHT_FAILED: CHANGED_FILE_INDETERMINATE: rename/copy lacks both paths" >&2
            return 2
          fi
          args_for_commit+=(--changed-file "$second")
        fi
      done
    }
    append_name_status_paths_for_commit < <(git diff-tree --no-commit-id -r --name-status -z -M -C "$commit")
    cd "$root"
    python3 scripts/verify.py --content-source revision --content-revision "$commit" "${args_for_commit[@]}"
  done
done
EOF
  fi
  chmod +x "$existing"
}

install_hook pre-commit
install_hook pre-push
echo "HOOK_INSTALLED: optional local feedback hooks installed"
echo "HOOK_NOTICE: run python3 -m harness_core preflight check for baseline local evidence."
