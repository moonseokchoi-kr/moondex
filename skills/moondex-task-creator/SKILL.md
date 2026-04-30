---
name: moondex-task-creator
description: Use when specs, design documents, implementation notes, or repository context need to be decomposed into a Moondex task set and runtime create-task payloads before task planning begins.
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
- Producing `moondex api create-task` payloads for runtime registration.

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
7. Emit runtime create-task payloads that match the current CLI API.

## Required Output

Produce:

- task set markdown following `docs/templates/task-set-template.md`
- one task block per task following `docs/templates/task-template.md`
- one runtime payload per task:

```json
{
  "task_id": "T-01",
  "subject": "Short task title",
  "description": "Goal, non-goals, dependencies, scope notes, and success conditions.",
  "role": "implementer"
}
```

## Registration Rule

By default, only generate payloads. If the user explicitly asks to register or create runtime tasks, run doctor first, use the returned `command_prefix`, and execute:

```bash
<command_prefix> api create-task --input '<json>' --json
```

## Handoff

After task creation, hand each task to `moondex-task-planner` one at a time. Do not combine multiple tasks into one planner request.
