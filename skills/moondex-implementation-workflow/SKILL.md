---
name: moondex-implementation-workflow
description: Use when the user asks Moondex to implement a feature, proceed, continue, 진행해줘, 계속해줘, 다음 단계 진행, 구현 진행, implement, proceed, or continue in an SDD/Moondex-style repository with specs, designs, tasks, plans, waves, or .moondex state.
---

# Moondex Implementation Workflow

Default entrypoint for feature execution in SDD/Moondex-style repositories.

## Trigger Rule

Use this skill for short proceed commands when repo markers indicate SDD/Moondex workflow intent:

- Korean: `진행해줘`, `계속해줘`, `다음 단계 진행`, `구현 진행`
- English: `implement`, `proceed`, `continue`, `next step`

Repo markers include any of:

- `.moondex/`
- `.codex-plugin/plugin.json` with `moondex`
- `docs/contracts/task-schema.md`, `docs/contracts/plan-schema.md`, or `docs/contracts/wave-schema.md`
- `docs/planning/`
- `docs/PRD.md`, `docs/spec*.md`, `docs/design*.md`, `docs/architecture*.md`
- `task-set.md`, `plan-set.md`, `wave-plan.md`
- `AGENTS.md`, `README.md`, or `docs/` mentioning `SDD`, `spec-driven`, `task/plan/wave`, or `Moondex`

If no marker exists, ask for the spec/design/task context instead of inventing a Moondex workflow.

## Mandatory Order

Do not skip stages:

1. Run `scripts/doctor.sh --json` for the target repo when available.
2. If no complete task set exists, use `moondex-task-creator`.
3. If task plans are missing, use `moondex-task-planner` for every task. Independent task-planner requests may run in parallel.
4. If no approved wave exists, use `moondex-wave-dispatcher` on the complete plan set.
5. Validate readiness for the task/plan/wave payloads.
6. Enqueue only READY wave tasks into runtime with `create-task`.
7. Use `moondex-runtime` for dispatch, claim, review, test, events, audit, and archive.

## Hard Rules

- Default path is `all tasks -> all plans -> wave approval -> runtime enqueue -> dispatch`.
- Do not register runtime tasks immediately after task creation.
- Do not dispatch a task without an executor-ready plan.
- Do not decide parallel execution from task titles alone; decide from the complete plan set.
- Do not let terminal state override `.moondex/state`.

## Stage Selection

- Specs/designs exist, no task set: create the full task set.
- Task set exists, plans missing: plan all tasks.
- Task set and plan set exist, wave missing: decide waves and parallelism.
- Wave exists, readiness missing: validate readiness.
- READY wave exists, runtime task missing: enqueue READY tasks.
- Runtime tasks exist: operate with `moondex-runtime`.
