# T-2: Implement State Transitions and Phase Preflight

## Related documents

- Spec: `docs/sdd/spec/2026-07-14-codex-harness-parity.md` (F2, F3, F4)
- Architecture: `docs/sdd/design/arch/2026-07-14-codex-harness-parity.md` (state and E0-E3 enforcement)

## Implementer / test type

- Implementer profile: Python engineer
- Test type: unit and integration fixtures
- Complexity: 8/10 (high)

## Owned paths

- `harness_core/state/`
- `tests/state/`
- `tests/fixtures/state/`

## Completion conditions

- [ ] `pipeline.json` schema, phase order, approval rules, retry limits, and resume data are represented by deterministic code.
- [ ] Invalid phase jumps, missing artifacts, missing approvals, and retry-limit breaches fail with a reason and remediation.
- [ ] Preflight checks distinguish documentation state from runtime state and never require an unsupported lifecycle event.
- [ ] Only the orchestrator-facing transition API may mutate normalized state.
- [ ] Fixtures prove that an interrupted run can identify the next valid action from files alone.

## Dependencies

- T-1

## Expected changed files

- `harness_core/state/`, `tests/state/`, `tests/fixtures/state/`

## Steps

- [ ] Define schemas and pure transition functions for planning, execution, completion, and escalation.
- [ ] Implement artifact, approval, worktree, ownership, and retry preflight checks as explicit commands/APIs.
- [ ] Make state writes atomic and preserve actionable failure information.
- [ ] Build resume fixtures covering incomplete documents, approval denial, and interrupted task execution.
- [ ] Add tests for each rejected transition and each allowed adjacent transition.
- [ ] Run state tests without network or LLM access.

## Validation commands

```bash
python3 -m pytest tests/state -q
python3 -m harness_core preflight phase --help
```

