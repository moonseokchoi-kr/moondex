# T-5: Port the Code Mapper Core with Explicit Fallbacks

## Related documents

- Spec: `docs/sdd/spec/2026-07-14-codex-harness-parity.md` (F1, F7, F9)
- Architecture: `docs/sdd/design/arch/2026-07-14-codex-harness-parity.md` (`code_mapper` module)

## Implementer / test type

- Implementer profile: Python engineer
- Test type: offline unit tests
- Complexity: 6/10 (medium)

## Owned paths

- `harness_core/code_mapper/`
- `tests/code_mapper/`
- `tests/fixtures/code_mapper/`

## Completion conditions

- [ ] Graph availability is classified as `healthy`, `not-initialized`, or `unavailable`.
- [ ] The fallback reports an approximate grep-based result rather than graph certainty.
- [ ] Mapping output includes entry points, candidate relationships, impact scope, provenance, and confidence limitations.
- [ ] Reports are ephemeral and do not mutate long-lived project state.
- [ ] Deterministic tests cover all graph states and fallback output.

## Dependencies

- T-1

## Expected changed files

- `harness_core/code_mapper/`, `tests/code_mapper/`, `tests/fixtures/code_mapper/`

## Steps

- [ ] Port portable probing and formatting logic while leaving graph-process invocation to a thin adapter.
- [ ] Define a stable result schema with explicit approximation and source metadata.
- [ ] Implement grep fallback patterns that return no fabricated call relationships.
- [ ] Add fixtures for healthy graph, unavailable graph command, and uninitialized graph data.
- [ ] Run code-mapper tests offline.

## Validation commands

```bash
python3 -m pytest tests/code_mapper -q
```

