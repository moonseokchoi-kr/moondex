# T-11: Run Codex Adapter End-to-End Acceptance and Record Evidence

## Related documents

- Spec: `docs/sdd/spec/2026-07-14-codex-harness-parity.md` (F1-F10, completion criteria)
- Architecture: `docs/sdd/design/arch/2026-07-14-codex-harness-parity.md` (End-to-end acceptance)

## Implementer / test type

- Implementer profile: test automator
- Test type: end-to-end sample-project and acceptance evidence
- Complexity: 9/10 (high)

## Owned paths

- `tests/e2e/`
- `tests/fixtures/e2e_sample_project/`
- `docs/sdd/result/2026-07-14-codex-harness-parity.md`
- `docs/sdd/result/` evidence artifacts for this feature only

## Completion conditions

- [ ] In a clean environment with `HARNESS_HOOKS` and `CODEX_PLUGIN_ROOT` unset, a sample project completes the explicit `state start` plan-to-result flow using project-local state; a separate normal-turn re-entry runs `state status` then `state resume` against the same state without hook helpers or a session ID.
- [ ] In that clean-environment flow, `state doctor` reports missing or unavailable optional hook integration as advisory diagnostic output and neither prevents `start`/`resume` nor changes their controller decision.
- [ ] Intentional default-branch, missing-E2E, and secret scenarios fail before completion.
- [ ] Engineer, compliance, review, test, retry, and escalation outcomes are present in the recorded state history.
- [ ] PR convergence scenarios distinguish safe fixes from escalated questions and declare convergence only under the defined predicate.
- [ ] Learning scenarios prove project-tier application and harness-tier proposal separation.
- [ ] A trusted-local PR scenario proves that raw credential evidence may remain only in `.harness/audit/`, while the corresponding CLI output and `.harness/reports/` evidence are redacted; result evidence must not reproduce the raw credential.
- [ ] The result document maps every F1-F10 criterion to test output or reproducible command evidence, including any externally managed CI limitation.

## Dependencies

- T-6, T-7, T-8, T-9, T-10
- T-2

## Expected changed files

- E2E tests/fixtures and feature-specific result evidence only

## Steps

- [ ] Create an isolated fixture project with no personal paths or credentials.
- [ ] With `HARNESS_HOOKS` and `CODEX_PLUGIN_ROOT` unset, execute `state start`, then a separate `state status`/`state resume` re-entry, through the explicit controller-first plan and one scoped UI-change scenario.
- [ ] Record and assert `state doctor` advisory output for unavailable optional hook integration without allowing it to block controller start or resume.
- [ ] Exercise each intentional failure condition and assert its remediation message.
- [ ] Simulate review/test retry and escalation state transitions.
- [ ] Exercise PR and learning acceptance scenarios using deterministic adapters/fixtures.
- [ ] Assert the trusted-local raw-audit/redacted-CLI-and-report boundary without copying raw credential evidence into result artifacts.
- [ ] Produce the criterion-to-evidence result document and run the complete offline suite.

## Validation commands

```bash
python3 -m pytest tests -q
python3 -m pytest tests/e2e -q
env -u HARNESS_HOOKS -u CODEX_PLUGIN_ROOT python3 -m pytest tests/e2e -q
```
