# Orchestrator State

## Metadata

- Architecture document: `docs/sdd/design/arch/2026-07-14-codex-harness-parity.md`
- Spec document: `docs/sdd/spec/2026-07-14-codex-harness-parity.md`
- Feature: `codex-harness-parity`
- Started at: `2026-07-14T00:00:00+09:00`
- Last updated: `2026-07-14T00:40:00+09:00`
- Status: `EXECUTING`
- Phase 3 approval: `APPROVED 2026-07-14`
- Worktree: `/Users/moon/Workspace/moondex-codex-harness-parity` on `feat/codex-harness-parity`

## Codex adapter constraints

- Execution is explicit state preflight plus CI/git-hook enforcement; unsupported lifecycle automation is not a gate.
- Role profiles are prompt contracts only. The orchestrator is the sole writer of this file and `.harness/state/pipeline.json`.
- Workers report status, changed files, validation output, and evidence; they do not edit orchestration state.
- Organization knowledge sync is opt-in. An unset configuration must result in `SKIPPED`, not a failed implementation.

## Wave plan

| Wave | Tasks | Dependencies | Purpose |
|---|---|---|---|
| 1 | T-1 | None | Establish package, configuration, test, and portability baseline. |
| 2 | T-2, T-3, T-4, T-5 | T-1 | Build independent deterministic state, learning, PR, and mapping cores. |
| 3 | T-6, T-7, T-8, T-9 | T-3/T-4/T-5; T-1/T-2; T-2; T-3/T-4/T-5 | Connect cores to skills, enforcement, SDD collaboration contracts, and benchmarks. |
| 4 | T-10 | T-6, T-7, T-8, T-9 | Align public plugin surface and portable user guidance. |
| 5 | T-11 | T-6, T-7, T-8, T-9, T-10 | Run end-to-end acceptance and create F1-F10 evidence. |

## DAG

```text
T-1
|- T-2 --+-- T-7 --+
|        |          |
|        +-- T-8 ---+-- T-10 --+
|- T-3 --+-- T-6 ---+          |
|        +-- T-9 ---+          +-- T-11
|- T-4 --+-- T-6 ---+          |
|        +-- T-9 ---+----------+
`- T-5 --+-- T-6
          `-- T-9
```

## Task status

| ID | Wave | Status | Iteration | Role profile | Notes |
|---|---:|---|---:|---|---|
| T-1 | 1 | complete | 1 | sdd-python-engineer | `pytest`: 6 passed; CLI and bytecode compilation passed. |
| T-2 | 2 | complete | 1 | sdd-python-engineer | `pytest tests/state`: 9 passed; CLI preflight contract verified. |
| T-3 | 2 | complete | 1 | sdd-python-engineer | Cursor, tier, proposal, and sync-skip tests passed. |
| T-4 | 2 | complete | 1 | sdd-python-engineer | Comment dedup, convergence, and escalation tests passed. |
| T-5 | 2 | complete | 1 | sdd-python-engineer | Three graph states and approximate fallback tests passed. |
| T-6 | 3 | pending | 0 | sdd-implementer | Codex skill adapters. |
| T-7 | 3 | pending | 0 | sdd-python-engineer | Preflight, hook wrapper, and CI adapter. |
| T-8 | 3 | pending | 0 | sdd-implementer | Role contracts and SDD resume. |
| T-9 | 3 | pending | 0 | sdd-python-engineer | Benchmarks and evaluation boundary. |
| T-10 | 4 | pending | 0 | sdd-implementer | Manifest, guidance, and portability audit. |
| T-11 | 5 | pending | 0 | sdd-test-automator | End-to-end acceptance and result evidence. |

## File ownership

| Task | Owned files/directories |
|---|---|
| T-1 | `harness_core/{__init__,__main__,cli,config}.py`, test configuration, baseline tests |
| T-2 | `harness_core/state/`, state tests and fixtures |
| T-3 | `harness_core/learning/`, learning tests and fixtures |
| T-4 | `harness_core/pr/`, PR tests and fixtures |
| T-5 | `harness_core/code_mapper/`, mapper tests and fixtures |
| T-6 | three portable skills, their adapters, skill-adapter test |
| T-7 | `harness_core/validation/`, verification scripts, CI workflow, validation tests |
| T-8 | `agents/`, active SDD/orchestrator skills, profile and resume tests |
| T-9 | `benchmarks/`, `evals/`, benchmark tests and scripts |
| T-10 | manifest, `AGENTS.md`, `README.md`, portability-policy test |
| T-11 | E2E fixture/tests and feature-specific result evidence |

## Agent assignment

- Orchestrator: main Codex session
- Engineer slots: assign only tasks whose Wave dependencies are `complete`
- Compliance/review/test: each task must pass in that order before `complete`

## History

- [2026-07-14T00:00:00+09:00] Phase 3 task plan and DAG created from approved spec and architecture SSOT.
- [2026-07-14T00:00:00+09:00] User approved Phase 3 plan.
- [2026-07-14T00:10:00+09:00] Phase 4 worktree created; T-1 started.
- [2026-07-14T00:20:00+09:00] T-1 completed: offline config tests passed; secure defaults and CLI baseline recorded.
- [2026-07-14T00:25:00+09:00] T-2 started: explicit state transition and preflight adapter.
- [2026-07-14T00:40:00+09:00] T-2 completed: transition, retry, ownership, atomic-I/O, and resume preflight evidence passed.
- [2026-07-15T09:00:00+09:00] T-3/T-4/T-5 completed: portable deterministic cores verified by offline tests.
