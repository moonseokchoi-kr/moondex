---
name: moondex-task-creator
description: Use within the Moondex implementation workflow when specs, design documents, implementation notes, or repository context need to be decomposed into a complete task set before all-task planning and wave dispatch decisions.
---

# Moondex Task Creator

Create a bounded Moondex task set from product or implementation input.

## Read First

- `../../docs/planning/planning-workflow.md`
- `../../docs/contracts/task-schema.md`
- `../../docs/templates/task-set-template.md`
- `../../docs/templates/task-template.md`

## Use For

- Turning `spec`, `design set`, or `implementation design set` into implementation tasks.
- Splitting broad work into single-goal tasks with dependencies and boundaries.
- Preparing task metadata that can later become runtime create-task payloads after wave approval.

## Do Not Use For

- Writing executor-ready plans for one task. Use `moondex-task-planner`.
- Wave planning or parallel group scheduling.
- Implementing code changes.
- Rewriting product direction when input documents are incomplete.

## Workflow

1. Read the input documents and scan the relevant codebase surface.
2. Separate requirements, constraints, risks, and implementation surfaces.
3. Create task IDs in stable order: `T-01`, `T-02`, ...
4. Keep each task focused on one implementation outcome.
5. Give every task clear non-goals, dependencies, scope notes, and success conditions.
6. Mark blocked tasks explicitly instead of hiding unresolved decisions.
7. Emit planner handoff inputs for every task.
8. Include draft runtime payloads only as deferred enqueue data.

## Required Output

Produce:

- task set markdown following `docs/templates/task-set-template.md`
- one task block per task following `docs/templates/task-template.md`
- one deferred runtime payload per task:

```json
{
  "task_id": "T-01",
  "subject": "Short task title",
  "description": "Goal, non-goals, dependencies, scope notes, and success conditions.",
  "role": "implementer"
}
```

## Runtime Rule

Do not register runtime tasks immediately after task creation. Runtime registration happens after:

- the full task set exists
- every dispatchable task has an executor-ready plan
- `moondex-wave-dispatcher` has decided wave order and parallelism
- readiness validation returns READY

## Handoff

After task creation, hand every task to `moondex-task-planner`, one task per planner request. Multiple planner requests may run in parallel when their inputs are independent.
