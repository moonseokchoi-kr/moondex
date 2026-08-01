# T-2: Rebuild the Host-Independent SDD State Controller

## Related documents

- Spec: `docs/sdd/spec/2026-07-14-codex-harness-parity.md` (F2, F4, F8)
- Architecture: `docs/sdd/design/arch/2026-07-14-codex-harness-parity.md` (execution control, state and authority, validation design)

## Implementer / test type

- Implementer profile: Python engineer
- Test type: offline unit and clean-process integration fixtures
- Complexity: 10/10 (high)

## Owned paths

- `harness_core/state/`
- `harness_core/cli.py` (state command registration and rendering only)
- `tests/state/`
- `tests/fixtures/state/`

## Completion conditions

- [ ] `python3 -m harness_core state start|status|resume|transition|doctor` is a stdlib-only, host-independent controller interface; its behavior does not depend on `HARNESS_HOOKS`, `CODEX_PLUGIN_ROOT`, a session ID, or a lifecycle hook.
- [ ] `state start <feature>` atomically creates a new normalized `.harness/state/pipeline.json` only when no active state for that feature exists. It never overwrites an existing active state or guesses a replacement state.
- [ ] `status` and `resume` are read-only: from state plus required SDD artifacts they return one deterministic `ACTION`, `WAITING_USER`, `BLOCKED_*`, `STATE_*`, `COMPLETE`, or `ADVISORY_UNAVAILABLE` result and a manually executable next step without changing state.
- [ ] Only the orchestrator-facing `transition` API can advance phase, approval, retry, worktree, or task status. It validates expected prior state, adjacent transition rules, required artifacts, explicit approvals, and retry/circuit-breaker limits under an exclusive lock.
- [ ] State creation and transition use atomic replace, fsync, and rollback-safe error handling. Lock contention/loss preserves the prior state and returns `STATE_BUSY`; malformed or document-inconsistent state returns `STATE_INVALID`; more than one active feature without an explicit target returns `AMBIGUOUS_FEATURE`.
- [ ] `doctor` reports missing, unusable, or legacy hooks only as `ADVISORY_UNAVAILABLE`, including the current state and a manual start/resume/verification command. Hook absence never makes start, status, resume, or transition fail.
- [ ] Tests prove idempotent start/resume, read-only status/resume, approval and artifact gates, lock contention, corruption, stale/interrupted state, retry escalation, and identical controller decisions in clean environments with `HARNESS_HOOKS`/`CODEX_PLUGIN_ROOT` unset or arbitrary.

## Dependencies

- T-1

## Expected changed files

- `harness_core/state/`, state CLI registration, state tests, and state fixtures only

## Steps

- [ ] Replace the prior preflight-centric state contract with versioned normalized state and explicit result/action schemas.
- [ ] Implement atomic new-state creation and idempotent active-feature detection without reading host hook variables.
- [ ] Implement read-only `status`/`resume` artifact inspection and deterministic next-action/user-gate calculation.
- [ ] Implement single-writer `transition` with expected-state checks, approvals, artifact gates, retry/circuit-breaker handling, lock discipline, and durable writes.
- [ ] Implement advisory-only hook discovery in `doctor`; do not source legacy shell helpers or wait for Stop-hook directives.
- [ ] Add clean-process fixtures for unset/arbitrary host variables, hook absence, existing state, ambiguous features, corruption, interrupted work, locks, approval gates, and retry limits.
- [ ] Run the offline state suite and CLI smoke commands.

## Validation commands

```bash
env -u HARNESS_HOOKS -u CODEX_PLUGIN_ROOT python3 -m pytest tests/state -q
env -u HARNESS_HOOKS -u CODEX_PLUGIN_ROOT python3 -m harness_core state start --help
env -u HARNESS_HOOKS -u CODEX_PLUGIN_ROOT python3 -m harness_core state resume --help
env -u HARNESS_HOOKS -u CODEX_PLUGIN_ROOT python3 -m harness_core state doctor --help
```
