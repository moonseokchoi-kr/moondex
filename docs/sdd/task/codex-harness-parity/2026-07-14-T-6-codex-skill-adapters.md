# T-6: Add Codex Skill Adapters for Verified Portable Cores

## Related documents

- Spec: `docs/sdd/spec/2026-07-14-codex-harness-parity.md` (F1, F5, F6, F7, F8)
- Architecture: `docs/sdd/design/arch/2026-07-14-codex-harness-parity.md` (Skills and local review-convergence contract)

## Implementer / test type

- Implementer profile: implementer
- Test type: documentation lint and offline CLI-integration tests with fake external commands
- Complexity: 8/10 (high)

## Owned paths

- `skills/self-improve/`
- `skills/pr-converge/`
- `skills/code-mapper/`
- `scripts/` adapter paths dedicated to these skills
- `tests/test_skill_adapters.py`
- `tests/fixtures/skill_adapters/`

T-6 consumes deterministic contracts from T-3, T-4, T-5, and T-7. It must not reimplement learning path policy, review disposition/convergence logic, or changed-file enforcement.

## Completion conditions

- [ ] Each skill explicitly invokes its corresponding portable core through a narrow adapter and documents invocation, inputs, outputs, local evidence locations, and resumable `BLOCKED`/`ESCALATED` behavior rather than lifecycle-triggered execution.
- [ ] `self-improve` exposes core outcomes faithfully: harness/indeterminate paths remain `PROPOSAL`/`BLOCKED`; it never converts them to `APPLY` or claims benchmark adoption without T-3 evidence.
- [ ] `pr-converge` sends complete local review-input bytes through the T-4 strict core and preserves collection snapshots/disposition audit evidence. It may request a safe fix only after deterministic `SAFE_FIX`; natural-language or LLM output alone cannot authorize a fix or rejection.
- [ ] `pr-converge` renders each local disposition with its reason and redacted local evidence. The trusted local `.harness/audit/` append-only record may retain the raw evidence needed to reproduce a disposition; that at-rest record is not a report/export and must not be treated as a failure. Optional provider mirroring is clearly non-authoritative: missing credentials/network/permission cannot erase a local disposition or change local convergence.
- [ ] `pr-converge` checks configured local build/lint/test results before reporting `CONVERGED`; malformed input, audit failure, validation failure, or open escalation stays `BLOCKED`/`ESCALATED`.
- [ ] `code-mapper` reports graph command/authentication failures as actionable `BLOCKED` and labels grep fallback as approximate without persisting graph claims as long-lived fact.
- [ ] Active skill paths contain no personal paths, Claude-only execution syntax, or undocumented external side effects.

## Dependencies

- T-3
- T-4
- T-5
- T-7
- T-8

## Expected changed files

- `skills/self-improve/`
- `skills/pr-converge/`
- `skills/code-mapper/`
- dedicated adapter scripts, adapter tests, and fixtures

## Steps

- [ ] Create Codex-oriented frontmatter and contracts that name validated core inputs/outputs, local evidence files, and failure/resume states.
- [ ] Connect each skill through a thin adapter; adapters serialize/deserialize only validated core contracts and retain no policy fork.
- [ ] Implement fake-command integration seams for graph and configured local build/lint/test failures; never use live network calls in tests.
- [ ] For local review reports, render source/revision identity, disposition reason, and redacted evidence references while preserving the T-4 raw-audit/report-rendering boundary. Treat provider reply/posting as an optional mirror rather than a completion precondition.
- [ ] Add reproducible negative scenarios for traversal/protected learning input, malformed or incomplete local review JSON, unknown alignment, audit/validation failure, open escalation, failed local build/lint/test, and unavailable graph tooling.
- [ ] Add an adapter scenario proving credential evidence can remain in the trusted local audit while CLI/report output is redacted; do not add an at-rest audit-masking gate.
- [ ] Add lint tests for portability and unsupported host syntax, then run all adapter and frontmatter validation.

## Validation commands

```bash
python3 -m pytest tests/test_skill_adapters.py -q
python3 -m pytest tests/test_skill_adapters.py -q -k 'blocked or escalated or strict or convergence'
python3 -c 'from pathlib import Path; import re,sys; errs=[]; [errs.append(str(f)) for f in sorted(Path("skills").glob("*/SKILL.md")) if not f.read_text().startswith("---\\n") or not re.search(r"^name:\\s*.+$", f.read_text(), re.M) or not re.search(r"^description:\\s*.+$", f.read_text(), re.M)]; sys.exit(bool(errs))'
```
