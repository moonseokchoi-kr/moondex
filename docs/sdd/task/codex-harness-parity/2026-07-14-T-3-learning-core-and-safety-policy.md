# T-3: Port the Learning Core and Safety Policy

## Related documents

- Spec: `docs/sdd/spec/2026-07-14-codex-harness-parity.md` (F1, F6, F8, F9)
- Architecture: `docs/sdd/design/arch/2026-07-14-codex-harness-parity.md` (`learning` module and benchmark gate)

## Implementer / test type

- Implementer profile: Python engineer
- Test type: offline unit tests
- Complexity: 8/10 (high)

## Owned paths

- `harness_core/learning/`
- `tests/learning/`
- `tests/fixtures/learning/`

## Completion conditions

- [ ] Raw learning input is append-only and cursor processing is idempotent.
- [ ] Provenance, recurrence, duplicate detection, tier routing, and protected-set checks are deterministic.
- [ ] Project-tier changes have a per-run cap and rollback record.
- [ ] Harness-tier changes are emitted only as proposals and cannot be auto-applied.
- [ ] Unconfigured knowledge sync produces a recorded `SKIPPED` outcome without blocking implementation completion.

## Dependencies

- T-1

## Expected changed files

- `harness_core/learning/`, `tests/learning/`, `tests/fixtures/learning/`

## Steps

- [ ] Compare the source deterministic learning behavior with the architecture boundaries and identify portable modules.
- [ ] Implement cursor, provenance, recurrence, tier classification, and rollback-record primitives.
- [ ] Add an explicit policy that rejects automatic edits to harness-tier files.
- [ ] Implement opt-in knowledge-sync outcome generation without personal defaults.
- [ ] Add regression fixtures for duplicate events, cursor restart, tier escalation, and rejected unsafe application.
- [ ] Run the learning test suite offline.

## Validation commands

```bash
python3 -m pytest tests/learning -q
```

