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

- [ ] A sample project completes the explicit SDD plan-to-result flow using project-local state.
- [ ] Intentional default-branch, missing-E2E, and secret scenarios fail before completion.
- [ ] Engineer, compliance, review, test, retry, and escalation outcomes are present in the recorded state history.
- [ ] PR convergence scenarios distinguish safe fixes from escalated questions and declare convergence only under the defined predicate.
- [ ] Learning scenarios prove project-tier application and harness-tier proposal separation.
- [ ] The result document maps every F1-F10 criterion to test output or reproducible command evidence, including any externally managed CI limitation.

## Dependencies

- T-6, T-7, T-8, T-9, T-10

## Expected changed files

- E2E tests/fixtures and feature-specific result evidence only

## Steps

- [ ] Create an isolated fixture project with no personal paths or credentials.
- [ ] Execute the approved plan and one scoped UI-change scenario through the explicit preflight/orchestration path.
- [ ] Exercise each intentional failure condition and assert its remediation message.
- [ ] Simulate review/test retry and escalation state transitions.
- [ ] Exercise PR and learning acceptance scenarios using deterministic adapters/fixtures.
- [ ] Produce the criterion-to-evidence result document and run the complete offline suite.

## Validation commands

```bash
python3 -m pytest tests -q
python3 -m pytest tests/e2e -q
```

