---
name: task-planner
description: Use when one implementation task is already defined and needs to be converted into a single executor-ready plan with explicit ownership, execution steps, checkpoints, and verification. Do not use for broad scoping, task decomposition, or wave planning.
---

# Task Planner

Turn one task into one executor-ready plan.

Read these files before writing the plan:

- `../../../docs/planning/task-planner-subagent.md`
- `../../../docs/contracts/plan-schema.md`
- `../../../docs/templates/plan-template.md`

## Use This Skill When

- A single task already exists.
- The next step is to produce a plan an implementer can start immediately.
- The plan must be grounded in the current codebase, not in a greenfield assumption.

## Do Not Use This Skill When

- The request is still broad and needs task decomposition.
- Multiple tasks need to be coordinated together.
- You are building a wave or orchestration plan.
- You need to rewrite product or architecture decisions.

## Required Inputs

- One task document
- Relevant spec fragments
- Relevant design fragments
- Relevant implementation-design fragments
- Relevant codebase paths

If these inputs are missing or conflict in a way you cannot safely resolve, return `NEEDS_CONTEXT` or `BLOCKED`.

## Workflow

1. Confirm the task boundary.
2. Gather codebase facts before asking for clarification.
3. Write one plan that follows `plan-schema.md`.
4. Check that the plan is actionable enough, not over-detailed.

## Plan Requirements

The plan must include:

- Goal
- Non-goals
- Ownership
- Inputs and outputs
- Implementation notes
- Execution steps
- Checkpoints and fallbacks
- Acceptance criteria
- Test requirements
- Verification commands
- Integration notes

## Quality Bar

- Keep the plan focused on one task.
- Prefer 3 to 7 major steps.
- Name the target files or modules for each step.
- Explain why the steps are in that order.
- Make acceptance and verification testable.
- Stop at actionable-enough detail.

Avoid:

- broad summaries with no execution order
- micro-step overplanning
- guessed codebase facts
- task scope expansion
- vague verification such as “run tests if needed”

## Output Contract

Return exactly one of:

- `DONE`
- `NEEDS_CONTEXT`
- `BLOCKED`

On `DONE`, return one markdown plan that follows `plan-template.md`.

Only return `DONE` if the plan includes:

- explicit ownership
- a concrete first step
- at least one checkpoint
- at least one minimum verification command
