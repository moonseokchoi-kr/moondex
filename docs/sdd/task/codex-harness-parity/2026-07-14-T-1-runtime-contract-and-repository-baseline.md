# T-1: Establish the Codex Runtime Contract and Repository Baseline

## Related documents

- Spec: `docs/sdd/spec/2026-07-14-codex-harness-parity.md` (F1, F2, F3, F8, F9, F10)
- Architecture: `docs/sdd/design/arch/2026-07-14-codex-harness-parity.md`

## Implementer / test type

- Implementer profile: Python engineer
- Test type: unit and repository-policy tests
- Complexity: 6/10 (medium)

## Owned paths

- `harness_core/__init__.py`
- `harness_core/__main__.py`
- `harness_core/cli.py`
- `harness_core/config.py`
- `tests/conftest.py`
- `tests/test_config.py`
- `pyproject.toml` or existing Python test configuration
- `scripts/` paths created solely for the Codex adapter

## Completion conditions

- [ ] A stdlib-first `harness_core` package has a stable CLI entry point.
- [ ] Project configuration can be loaded from `.harness/config.json` with secure defaults, including disabled knowledge sync.
- [ ] Invalid configuration reports an actionable error and does not silently enable an external destination.
- [ ] Repository-policy tests reject personal absolute paths from newly added user execution paths.
- [ ] The test runner has an offline-only default command; `evals/` is excluded from collection.

## Dependencies

- None

## Expected changed files

- `harness_core/`, `tests/`, Python test configuration, newly introduced Codex adapter scripts only

## Steps

- [ ] Inspect existing Python packaging and test conventions without modifying preserved compatibility hooks.
- [ ] Add the minimal package layout and CLI dispatch contract.
- [ ] Implement config parsing, defaults, and validation with only Python stdlib dependencies.
- [ ] Add deterministic unit tests for valid, invalid, and unset knowledge-sync configurations.
- [ ] Add a focused repository-policy test for forbidden personal-path defaults in new active paths.
- [ ] Run the offline test command and record its output for the task result.

## Validation commands

```bash
python3 -m pytest tests/test_config.py -q
python3 -m harness_core doctor --help
```

