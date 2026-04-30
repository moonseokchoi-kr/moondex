# Task Set Template

This template is the expected output shape for `moondex-task-creator`.

## Source Inputs

- spec:
- design set:
- implementation design set:
- codebase scan:

## Decomposition Summary

- implementation strategy:
- shared contracts:
- sequencing constraints:
- main risks:

## Task List

| task_id | title | priority | owner_role | depends_on | status |
| --- | --- | --- | --- | --- | --- |
| T-01 | replace with concrete task title | medium | implementer | [] | draft |

## Tasks

Use `docs/templates/task-template.md` for each task.

## Runtime Create Payloads

```json
[
  {
    "task_id": "T-01",
    "subject": "replace with concrete task title",
    "description": "Goal: ... Non-goals: ... Dependencies: ... Scope: ... Success: ...",
    "role": "implementer"
  }
]
```

## Planner Handoff

- Send each task to `moondex-task-planner` separately.
- Include the task block, relevant source document excerpts, and codebase scan notes.
- Do not request wave planning until task-level plans exist.
