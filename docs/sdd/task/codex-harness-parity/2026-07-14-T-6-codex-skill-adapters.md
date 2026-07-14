# T-6: Add Codex Skill Adapters for the Portable Cores

## Related documents

- Spec: `docs/sdd/spec/2026-07-14-codex-harness-parity.md` (F1, F5, F6, F7)
- Architecture: `docs/sdd/design/arch/2026-07-14-codex-harness-parity.md` (Skills)

## Implementer / test type

- Implementer profile: implementer
- Test type: documentation lint and CLI integration tests
- Complexity: 7/10 (high)

## Owned paths

- `skills/self-improve/`
- `skills/pr-converge/`
- `skills/code-mapper/`
- `tests/test_skill_adapters.py`
- `scripts/` adapter paths dedicated to these skills

## Completion conditions

- [ ] Each portable workflow has a Codex-facing skill that invokes a narrow local or external adapter boundary.
- [ ] Skill instructions describe explicit invocation and resume behavior, not lifecycle-driven automatic execution.
- [ ] External hosting and graph commands return `BLOCKED` or an equivalent actionable status on authentication/network failures.
- [ ] Skill documentation has no active personal paths or unsupported host-specific execution syntax.
- [ ] CLI integration tests validate argument forwarding and failure reporting without network calls.

## Dependencies

- T-3, T-4, T-5

## Expected changed files

- `skills/self-improve/`, `skills/pr-converge/`, `skills/code-mapper/`, dedicated adapter scripts, tests

## Steps

- [ ] Create skill frontmatter and Codex-oriented workflow contracts for all three skills.
- [ ] Connect each skill to the corresponding deterministic core through a thin adapter.
- [ ] Implement explicit external-command failure handling and evidence output.
- [ ] Add lint tests for active-path portability and unsupported host syntax.
- [ ] Run skill-adapter tests and the plugin frontmatter validator.

## Validation commands

```bash
python3 -m pytest tests/test_skill_adapters.py -q
python3 -c 'from pathlib import Path; import re,sys; errs=[]; [errs.append(str(f)) for f in sorted(Path("skills").glob("*/SKILL.md")) if not f.read_text().startswith("---\\n") or not re.search(r"^name:\\s*.+$", f.read_text(), re.M) or not re.search(r"^description:\\s*.+$", f.read_text(), re.M)]; sys.exit(bool(errs))'
```

