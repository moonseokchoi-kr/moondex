# T-10: Align Plugin Surface and Portability Documentation

## Related documents

- Spec: `docs/sdd/spec/2026-07-14-codex-harness-parity.md` (F1, F8, F10)
- Architecture: `docs/sdd/design/arch/2026-07-14-codex-harness-parity.md` (plugin boundary and company configuration)

## Implementer / test type

- Implementer profile: implementer
- Test type: manifest validation and documentation-policy tests
- Complexity: 5/10 (medium)

## Owned paths

- `.codex-plugin/plugin.json`
- `.codex-plugin/marketplace.json`
- `AGENTS.md`
- `README.md`
- `tests/test_portability_policy.py`

## Completion conditions

- [ ] The manifest exposes only supported plugin fields and skills as its public surface.
- [ ] User-facing instructions identify `.harness/` as project runtime state and do not require personal infrastructure.
- [ ] Documentation accurately describes optional organization knowledge sync and required CI protections.
- [ ] Active execution guidance contains no personal absolute paths or unsupported lifecycle automation assumptions.
- [ ] Manifest and portability policy tests pass.

## Dependencies

- T-6, T-7, T-8, T-9

## Expected changed files

- manifest files, `AGENTS.md`, `README.md`, portability-policy tests

## Steps

- [ ] Reconcile the public manifest with installed Codex skill directories.
- [ ] Update user-facing runtime guidance to reference explicit preflight, CI, and project-local configuration.
- [ ] Document the organization opt-in contract without providing a private default destination.
- [ ] Add a focused active-path scan that excludes preserved compatibility/archive material by declared policy.
- [ ] Run manifest, frontmatter, and portability validation.

## Validation commands

```bash
python3 -m json.tool .codex-plugin/plugin.json >/dev/null
python3 -m json.tool .codex-plugin/marketplace.json >/dev/null
python3 -m pytest tests/test_portability_policy.py -q
```

