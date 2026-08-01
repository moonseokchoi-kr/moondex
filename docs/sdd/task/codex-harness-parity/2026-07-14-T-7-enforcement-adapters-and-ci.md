# T-7: Implement Shared Local Enforcement and Optional Hook Verification

## Related documents

- Spec: `docs/sdd/spec/2026-07-14-codex-harness-parity.md` (F2, F3, F6, F8, F9)
- Architecture: `docs/sdd/design/arch/2026-07-14-codex-harness-parity.md` (E0-E2 enforcement, shared local changed-file checks, containment, and secret policy)

## Implementer / test type

- Implementer profile: Python engineer
- Test type: deterministic filesystem/git-worktree integration fixtures
- Complexity: 8/10 (high)

## Owned paths

- `harness_core/enforcement/`
- `harness_core/cli.py` (enforcement command registration only)
- `scripts/install-hooks*`
- `scripts/verify*`
- `tests/enforcement/`
- `tests/fixtures/enforcement/`

T-7 is the sole owner of shared current-worktree changed-file classification, canonical path containment, local protected-set configuration, and secret scanning. T-2 retains phase/state logic; T-3 consumes this policy rather than duplicating it.

## Completion conditions

- [ ] Explicit `--changed-file` verification, worktree-derived preflight, and the optional git-hook wrapper delegate to one shared enforcement entrypoint and emit the same versioned report shape for equivalent current changes.
- [ ] A report records source (`explicit`, `worktree`, or `hook`), repository/worktree identity, canonical changed paths, applicable rules, redacted evidence, and `PASS`/`FAIL`/`INDETERMINATE` result. Missing or unusable changed-file input is `INDETERMINATE`, never a successful empty set.
- [ ] Changed-file classification uses the supplied current change set; when Git reports rename/copy it evaluates both old and new paths. It does not claim remote push history, first-push ancestry, provider events, or hosted-CI parity.
- [ ] Canonical containment rejects absolute/NUL/traversal/root-escape/broken-or-out-of-root symlink/indeterminate paths. Protected matching is segment-based; plugin minimum protected paths are non-removable and local configuration can only add protections.
- [ ] Branch, TDD-manifest, E2E, protected-path, and secret checks run through `harness_core preflight`; failures include the rule, changed-file evidence, and concrete local remediation.
- [ ] UI changes without required E2E evidence fail. Phase-4 implementation changes on the configured default branch fail. The optional hook is fast feedback only; hook absence does not invalidate an explicit preflight report.
- [ ] Secret scanning covers assignment, JSON credential literals, and Authorization/Bearer literals in the supplied local change set without writing secret values to audit. It accepts documented references/placeholders and valid scoped, unexpired local allowlists while recording redacted allowlist evidence; ambiguity, malformed encoding, or invalid allowlist fails closed.
- [ ] Hook wrappers delegate to the shared CLI and preserve existing user hooks. Hosted CI/provider integration, remote policy snapshots, full outgoing-range resolution, and required-check proof are not baseline requirements.

## Dependencies

- T-1

T-7 has no dependency on the reopened T-2 controller: it supplies shared local enforcement and preflight evidence, while T-2 owns only host-independent pipeline state and transition authority. T-7 remains complete and is therefore not reopened by the controller migration.

## Expected changed files

- `harness_core/enforcement/`
- enforcement CLI registration
- `scripts/install-hooks*`
- `scripts/verify*`
- enforcement tests and fixtures

## Steps

- [ ] Define versioned local report schemas for changed files, local configuration/allowlist hash, applicable rules, and rule outcomes; redact sensitive values.
- [ ] Implement one current-worktree/explicit changed-file collector and classifier, including rename/copy old/new handling when Git supplies it.
- [ ] Implement canonical containment, repository-mode detection, and non-removable minimum protected set with locally additive configuration.
- [ ] Implement branch/TDD/E2E/protected-path/secret preflight rules as consumers of shared evidence; do not duplicate policy in hooks or scripts.
- [ ] Implement optional hook installation/wrappers around the shared CLI. State plainly that hooks provide local fast feedback and explicit preflight/verify is the baseline evidence.
- [ ] Add negative fixtures for missing changed-file input, traversal and symlink aliases, rename/copy protected paths, UI without E2E, default-branch implementation, assignment/JSON/Bearer secrets, and expired/malformed/out-of-scope allowlists.
- [ ] Add parity fixtures proving explicit, worktree, and hook sources serialize the same canonical changed-file records and rule outcomes for equivalent current changes, plus placeholder/reference and valid allowlist cases.
- [ ] Run enforcement tests and local CLI fixture commands without network access.

## Validation commands

```bash
python3 -m pytest tests/enforcement -q
python3 -m pytest tests/enforcement -q -k 'changed_file or worktree or hook or secret or containment'
python3 -m harness_core preflight --help
bash -n scripts/install-hooks.sh
```
