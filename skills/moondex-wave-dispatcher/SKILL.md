---
name: moondex-wave-dispatcher
description: Use within the Moondex implementation workflow after the full task set and all executor-ready plans exist to decide wave order, parallel execution groups, runtime enqueue order, and dispatch readiness.
---

# Moondex Wave Dispatcher

Turn a complete task set and plan set into an execution wave decision.

## Read First

- `../../docs/contracts/wave-schema.md`
- `../../docs/templates/wave-template.md`
- `../../docs/execution/task-readiness-gate.md`
- `../../docs/execution/multi-agent-orchestration.md`
- `../../docs/execution/low-interruption-policy.md`

## Use For

- Deciding which planned tasks can run in parallel.
- Sequencing tasks with dependencies, shared contracts, or ownership conflicts.
- Producing a wave plan that tells runtime which READY tasks to enqueue and dispatch.

## Do Not Use For

- Creating tasks from specs. Use `moondex-task-creator`.
- Writing task-level executor plans. Use `moondex-task-planner`.
- Executing runtime dispatch directly.

## Workflow

1. Read the complete task set and all corresponding executor-ready plans.
2. Build the dependency graph from task dependencies and plan-level implementation constraints.
3. Compare ownership allow/deny paths and shared contract changes.
4. Group tasks into waves only when they can run without ownership or sequencing conflicts.
5. Mark serial tasks with the concrete reason they cannot run in parallel.
6. Produce validation inputs for `validate-readiness`.
7. Return the runtime enqueue order for READY tasks.

## Required Output

Produce a wave plan following `docs/templates/wave-template.md` with:

- task and plan list
- dependency graph
- wave groups
- parallel execution rationale
- serial execution rationale
- ownership map
- verification plan
- runtime enqueue order
- high-impact blocker conditions that require operator input

## Runtime Rule

Only tasks in approved wave groups and validated as READY should be registered with:

```bash
<command_prefix> api create-task --input '<json>' --json
```

After registration, runtime dispatch can proceed through `moondex-runtime`.
