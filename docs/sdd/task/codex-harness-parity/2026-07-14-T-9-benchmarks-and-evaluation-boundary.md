# T-9: Establish Offline Benchmarks and the Live-Evaluation Boundary

## Related documents

- Spec: `docs/sdd/spec/2026-07-14-codex-harness-parity.md` (F5, F6, F8, F9)
- Architecture: `docs/sdd/design/arch/2026-07-14-codex-harness-parity.md` (Benchmarks, live eval, and local audit/report boundary)

## Implementer / test type

- Implementer profile: Python engineer
- Test type: fixture validation and benchmark command tests
- Complexity: 5/10 (medium)

## Owned paths

- `benchmarks/`
- `evals/`
- `tests/benchmarks/`
- `scripts/run-benchmarks*`

## Completion conditions

- [ ] Train and held-out benchmark fixture sets are separate and held-out fixtures are guarded against accidental modification by normal update commands.
- [ ] Benchmark output records baseline, candidate score, and held-out regression count.
- [ ] Harness-tier adoption is rejected without an improved train score and zero held-out regressions.
- [ ] Live evaluation has an explicit command and is excluded from the default offline test collection.
- [ ] PR-related benchmark fixtures distinguish trusted-local raw audit retention from rendered-report behavior: plaintext raw audit evidence is not a benchmark failure, while any report/eval presentation fixture containing credential literals fails.
- [ ] Benchmark commands use deterministic local cores and fixtures only; they do not require a provider, remote CI, external export, or host hook environment.

## Dependencies

- T-3, T-4, T-5

## Expected changed files

- `benchmarks/`, `evals/`, `tests/benchmarks/`, benchmark scripts

## Steps

- [ ] Create the benchmark directory contract and immutable held-out fixture policy.
- [ ] Add representative deterministic fixtures for learning, PR, and mapping decisions.
- [ ] Implement score comparison and adoption-gate reporting.
- [ ] Add tests for missing baseline, no improvement, and held-out regression rejection.
- [ ] Add a fixture-level data-boundary assertion for raw local audit versus redacted rendered report without changing the T-4 audit storage contract.
- [ ] Make live-eval execution opt-in and assert it is absent from pytest collection.
- [ ] Run benchmark fixture tests and the offline benchmark command.

## Validation commands

```bash
python3 -m pytest tests/benchmarks -q
python3 scripts/run-benchmarks.py --help
```
