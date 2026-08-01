# T-3: Port the Learning Core and Safe-Application Policy

## Related documents

- Spec: `docs/sdd/spec/2026-07-14-codex-harness-parity.md` (F1, F6, F8, F9)
- Architecture: `docs/sdd/design/arch/2026-07-14-codex-harness-parity.md` (`learning`, canonical containment, protected set, and benchmark gate)

## Implementer / test type

- Implementer profile: Python engineer
- Test type: offline unit tests and deterministic filesystem fixtures
- Complexity: 8/10 (high)

## Owned paths

- `harness_core/learning/`
- `tests/learning/`
- `tests/fixtures/learning/`

T-7 owns the shared canonical path-containment and local protected-set policy. This task consumes that API rather than copying or weakening its rules.

## Completion conditions

- [ ] Raw learning input remains append-only; cursor processing, provenance, recurrence, and duplicate detection are deterministic and idempotent across restart.
- [ ] Tier routing uses T-7's canonical repository-relative containment result and the current trusted local repository configuration, never a raw string prefix.
- [ ] Only a `CANONICAL_INSIDE` project-tier target outside the non-removable protected set can reach `APPLY`; it also requires a rollback record, configured per-run cap, and recurrence/critic prechecks.
- [ ] Absolute paths, NUL paths, any `..` segment, root escape, broken/out-of-root/indeterminate symlink, and unprovable containment produce a recorded `PROPOSAL` or `BLOCKED` result and never create an automatic edit.
- [ ] Plugin/harness-tier paths (`skills/`, `agents/`, `.codex-plugin/`, `harness_core/`, `scripts/`, `.github/`, `hooks/`, `tests/`, `benchmarks/`, `evals/`, plus local additive protections) are always proposal-only. Local configuration can add protections but cannot remove the minimum set.
- [ ] Harness-tier adoption remains separate from application: it requires a recorded baseline, train-score improvement, and zero held-out regression; missing evidence never becomes automatic adoption.
- [ ] Unconfigured knowledge sync records `SKIPPED` without personal defaults and without blocking implementation completion.

## Dependencies

- T-1
- T-7 (canonical containment and local protected-set policy)

## Expected changed files

- `harness_core/learning/`
- `tests/learning/`
- `tests/fixtures/learning/`

## Steps

- [ ] Compare the source deterministic learning behavior with the local-first architecture boundaries; retain portable state logic and keep mutation/external effects outside the core.
- [ ] Implement append-only cursor, provenance, recurrence, duplicate detection, rollback-record, run-cap, and proposal/application outcome primitives.
- [ ] Integrate T-7 containment/protected-set results as the sole path-policy input; return `BLOCKED` when containment proof is unavailable.
- [ ] Implement project/harness tier routing and opt-in knowledge-sync outcome generation without personal paths or external transmission.
- [ ] Add negative fixtures for `app/../scripts/x`, absolute/NUL paths, root escape, broken and out-of-root symlinks, protected-set removal attempts, missing rollback/cap, and missing benchmark baseline/held-out evidence.
- [ ] Add positive fixtures proving a canonical in-root, non-protected project path can produce `APPLY` only with all required local records.
- [ ] Run the learning suite offline.

## Validation commands

```bash
python3 -m pytest tests/learning -q
python3 -m pytest tests/learning -q -k 'traversal or symlink or protected or rollback or held_out'
```
