# T-8: Migrate Active SDD Paths to Controller-First Resume

## Related documents

- Spec: `docs/sdd/spec/2026-07-14-codex-harness-parity.md` (F2, F4, F8, F10)
- Architecture: `docs/sdd/design/arch/2026-07-14-codex-harness-parity.md` (state controller, Skills, role profiles, migration order)

## Implementer / test type

- Implementer profile: implementer
- Test type: profile lint, skill-path policy, and clean-environment resume integration tests
- Complexity: 9/10 (high)

## Owned paths

- `agents/`
- `agents/archive/` paths created by this task
- `skills/sdd/SKILL.md`
- `skills/sdd-orchestrator/`
- `tests/test_agent_profiles.py`
- `tests/test_sdd_resume.py`
- `tests/fixtures/sdd_resume/`

## Completion conditions

- [ ] Active role profiles use common host-neutral input, authority, and output contracts; workers return results and evidence but never claim authority to write `ORCHESTRATOR_STATE.md` or `.harness/state/pipeline.json`.
- [ ] `/sdd start <feature>` instructs the active SDD path to invoke `harness_core state start` and then consume controller results. A normal Codex turn uses `state status`/`resume`; neither path sources `$HARNESS_HOOKS`, `pipeline-utils.sh`, or any hook helper.
- [ ] Active SDD and orchestrator instructions do not claim Stop-hook automatic continuation, session-hook registration, or background phase advancement. The controller result determines an explicit next action or `WAITING_USER`; only the orchestrator invokes `state transition` after validating worker output.
- [ ] An absent/unusable optional hook is presented as advisory availability plus a manual command, never as a hard-gate failure. An installed optional hook cannot create a different label, bypass approval, or mutate state outside the controller contract.
- [ ] Legacy lifecycle paths and profiles are archived or explicitly marked compatibility/advisory material; active paths contain no `HARNESS_HOOKS`, `CODEX_PLUGIN_ROOT`, `pipeline-utils.sh` source, Claude-only lifecycle syntax, personal paths, or unsupported hook-registration claim.
- [ ] Clean-environment tests prove start, existing-state re-entry, status/resume, approval waiting, and hook-absent parity without host variables; tests also prove workers cannot write orchestration state and organization knowledge sync remains `SKIPPED` when unconfigured.

## Dependencies

- T-2

## Expected changed files

- active `agents/` profiles, explicit archives, active SDD/orchestrator skill instructions, profile/resume tests, and resume fixtures only

## Steps

- [ ] Inventory active versus compatibility SDD/profile paths and identify every lifecycle-hook reference in an executable instruction path.
- [ ] Migrate active SDD entry and ordinary-turn resume instructions to the T-2 controller commands and result vocabulary.
- [ ] Migrate orchestrator instructions to the sole-writer transition contract; preserve worker result-only authority.
- [ ] Standardize active profile contracts and archive or mark legacy lifecycle-only material without deleting compatibility sources.
- [ ] Add policy tests that reject active references to host variables, `pipeline-utils.sh`, Stop-hook automation, unsupported registration, and private defaults.
- [ ] Add clean-process start/re-entry/resume/approval/hook-absent parity fixtures and worker-state-write rejection tests.
- [ ] Run profile, resume, and active skill-frontmatter validation.

## Validation commands

```bash
env -u HARNESS_HOOKS -u CODEX_PLUGIN_ROOT python3 -m pytest tests/test_agent_profiles.py tests/test_sdd_resume.py -q
rg -n 'HARNESS_HOOKS|CODEX_PLUGIN_ROOT|pipeline-utils\.sh|Stop hook' agents skills/sdd skills/sdd-orchestrator
python3 -c 'from pathlib import Path; import re,sys; errs=[]; [errs.append(str(f)) for f in (Path("skills/sdd"), Path("skills/sdd-orchestrator")) if not (f / "SKILL.md").read_text().startswith("---\\n") or not re.search(r"^name:\\s*.+$", (f / "SKILL.md").read_text(), re.M)]; sys.exit(bool(errs))'
```
