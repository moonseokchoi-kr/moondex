# T-4: Port the Deterministic Local Review-Convergence Core

## Related documents

- Spec: `docs/sdd/spec/2026-07-14-codex-harness-parity.md` (F1, F5, F9)
- Architecture: `docs/sdd/design/arch/2026-07-14-codex-harness-parity.md` (`pr` core, strict local input, alignment, audit, and convergence contracts)

## Implementer / test type

- Implementer profile: Python engineer
- Test type: offline unit tests, strict-input fixtures, and atomic-persistence fixtures
- Complexity: 9/10 (high)

## Owned paths

- `harness_core/pr/`
- `tests/pr/`
- `tests/fixtures/pr/`

The core must not call a hosting API, invoke an LLM, mutate git, or require remote posting/CI evidence. Local input collection and presentation belong to the T-6 adapter boundary.

## Completion conditions

- [ ] Conversation, inline, and review-body inputs normalize into one revision-aware signal model with stable `source_identity`; edited bodies/revisions and reopened reviews require a new disposition.
- [ ] The strict parser rejects duplicate keys, trailing data, `NaN`/`Infinity`/non-standard constants, missing/type-mismatched IDs, non-finite/fractional/unsafe numeric ID or line values, and malformed identity as `BLOCKED`; none can converge or auto-mutate.
- [ ] A complete local collection snapshot is recorded before disposition. A malformed or incomplete local input blocks convergence rather than being treated as an empty queue.
- [ ] A single locked writer appends immutable machine-readable disposition events atomically before a request can leave the actionable queue. Lock loss, partial/audit write failure, or concurrent-writer failure is fail-closed.
- [ ] Each new request revision is deterministically classified from current local spec/design/task ownership and local validation evidence as `SAFE_FIX`, `REJECTED`, `ESCALATED`, `NON_ACTIONABLE`, or `BLOCKED`. Unknown/contradictory alignment, design trade-offs, missing authority, or LLM-only rationale becomes `ESCALATED`.
- [ ] `SAFE_FIX` requires an aligned local rule, owned scope, concrete local validation plan, and records changed files plus passing validation. Failed validation, scope expansion, or changed ownership escalates.
- [ ] `REJECTED` requires conflicting or out-of-scope local evidence, a human-readable reason, and an alternative or requested decision in the local disposition record.
- [ ] Circuit-breaker transitions are deterministic. `CONVERGED` requires valid complete local input, passing configured local build/lint/test commands, terminal dispositions for all actionable revisions, and no open escalation.

## Dependencies

- T-1

## Expected changed files

- `harness_core/pr/`
- `tests/pr/`
- `tests/fixtures/pr/`

## Steps

- [ ] Port the source state machine as pure data transformations and define strict JSON/schema validation without permissive parser defaults.
- [ ] Implement snapshot/revision lifecycle, deterministic deduplication, append-only atomic audit events, and circuit-breaker state for enumerated local input.
- [ ] Implement local SOT/evidence inputs and deterministic alignment/disposition predicates; keep natural-language/LLM suggestions non-authoritative.
- [ ] Implement convergence from complete persisted local evidence and configured build/lint/test results; model any provider mirror only as optional metadata.
- [ ] Add negative fixtures for duplicate keys, trailing JSON, `NaN`/`Infinity`, invalid IDs/lines, incomplete input, edited/reopened comments, unknown alignment, LLM-only evidence, audit write failure, failed validation, build/lint/test failure, and open escalation.
- [ ] Add positive fixtures for a fully evidenced `SAFE_FIX`, evidence-backed `REJECTED`, and local convergence with all terminal dispositions and passing commands.
- [ ] Run the PR core test suite offline.

## Validation commands

```bash
python3 -m pytest tests/pr -q
python3 -m pytest tests/pr -q -k 'strict or disposition or convergence or audit or revision'
```
