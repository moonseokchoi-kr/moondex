# T-8: Standardize Role Profiles and Codex SDD Resume

## Related documents

- Spec: `docs/sdd/spec/2026-07-14-codex-harness-parity.md` (F2, F4, F8, F10)
- Architecture: `docs/sdd/design/arch/2026-07-14-codex-harness-parity.md` (role profiles, single writer, Skills)

## Implementer / test type

- Implementer profile: implementer
- Test type: profile lint and collaboration-contract integration tests
- Complexity: 8/10 (high)

## Owned paths

- `agents/`
- `agents/archive/` paths created by this task
- `skills/sdd/SKILL.md`
- `skills/sdd-orchestrator/`
- `tests/test_agent_profiles.py`
- `tests/test_sdd_resume.py`

## Completion conditions

- [ ] Active role profiles use the common input, authority, and output contracts from the architecture.
- [ ] Role profiles express capabilities and owned-file boundaries, but never claim state-write authority.
- [ ] The SDD and orchestrator skills read normalized state and execute only the next valid explicit step.
- [ ] The orchestrator is the sole state writer; worker results are validated before a state transition.
- [ ] Legacy profiles are either migrated to current `docs/sdd/` contracts or explicitly archived.
- [ ] Organization knowledge sync returns `SKIPPED` when configuration is absent.

## Dependencies

- T-2

## Expected changed files

- `agents/`, `skills/sdd/`, `skills/sdd-orchestrator/`, profile and resume tests

## Steps

- [ ] Inventory active and legacy profiles against the architecture classification.
- [ ] Define a lintable host-neutral profile format and migrate active SDD profiles.
- [ ] Archive or clearly mark unintegrated legacy profiles without deleting compatibility material.
- [ ] Rewrite active SDD resume and orchestration instructions around explicit preflight and state transitions.
- [ ] Add tests proving no worker path can write state and no active profile contains unsupported execution syntax or private defaults.
- [ ] Run profile and resume tests.

## Validation commands

```bash
python3 -m pytest tests/test_agent_profiles.py tests/test_sdd_resume.py -q
```

