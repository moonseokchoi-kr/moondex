# T-7: Implement Enforcement Adapters, Git Hooks, and CI Verification

## Related documents

- Spec: `docs/sdd/spec/2026-07-14-codex-harness-parity.md` (F2, F3, F8, F9)
- Architecture: `docs/sdd/design/arch/2026-07-14-codex-harness-parity.md` (E0-E3 enforcement)

## Implementer / test type

- Implementer profile: Python engineer
- Test type: integration fixtures and CI configuration checks
- Complexity: 9/10 (high)

## Owned paths

- `harness_core/validation/`
- `harness_core/cli.py` (only validation command registration)
- `scripts/install-hooks*`
- `scripts/verify*`
- `.github/workflows/` paths created for verification
- `tests/validation/`
- `tests/fixtures/validation/`

## Completion conditions

- [ ] Phase, branch, TDD-manifest, E2E, secret, and protected-path checks execute through `harness_core preflight`.
- [ ] Local hook wrappers call the same checks and report the authoritative CI limitation.
- [ ] CI invokes the offline verification command and contains a default-branch guard.
- [ ] Fixtures prove intentional failures for a default-branch implementation commit, UI change without E2E evidence, and exposed secret.
- [ ] Failures state the reason and a concrete corrective action.

## Dependencies

- T-1, T-2

## Expected changed files

- `harness_core/validation/`, scripts, CI workflow, validation tests and fixtures

## Steps

- [ ] Translate each enforcement requirement into an explicit preflight rule and evidence format.
- [ ] Implement the preflight command and deterministic changed-file classification.
- [ ] Add installable git-hook wrappers that delegate to preflight rather than duplicate policy logic.
- [ ] Add CI workflow/configuration guidance with required-check naming and default-branch protection verification.
- [ ] Build intentional-failure fixtures and verify actionable messages.
- [ ] Run validation tests and the CI verification command locally.

## Validation commands

```bash
python3 -m pytest tests/validation -q
python3 -m harness_core preflight --help
```

