# T-4: Port the PR Convergence State Machine

## Related documents

- Spec: `docs/sdd/spec/2026-07-14-codex-harness-parity.md` (F1, F5, F9)
- Architecture: `docs/sdd/design/arch/2026-07-14-codex-harness-parity.md` (`pr` core and external adapter boundary)

## Implementer / test type

- Implementer profile: Python engineer
- Test type: offline unit tests
- Complexity: 7/10 (high)

## Owned paths

- `harness_core/pr/`
- `tests/pr/`
- `tests/fixtures/pr/`

## Completion conditions

- [ ] Conversation comments, inline comments, and review-body comments normalize into one deduplicated signal model.
- [ ] Repeated failures and total iteration limits open a circuit breaker.
- [ ] The core classifies safe auto-fix candidates separately from questions, design decisions, and blocked external signals.
- [ ] Convergence is declared only with green CI, zero actionable signals, and zero unresolved escalations.
- [ ] The deterministic core has no direct hosting API or git mutation dependency.

## Dependencies

- T-1

## Expected changed files

- `harness_core/pr/`, `tests/pr/`, `tests/fixtures/pr/`

## Steps

- [ ] Port the source state machine into pure data transformations and isolate all external inputs.
- [ ] Define comment identity and deduplication semantics across all required comment kinds.
- [ ] Implement iteration accounting, circuit-breaker transitions, escalation classification, and convergence predicate.
- [ ] Add fixtures for duplicate comments, new actionable comments, design questions, failing CI, and exhausted retries.
- [ ] Run the PR core test suite offline.

## Validation commands

```bash
python3 -m pytest tests/pr -q
```

