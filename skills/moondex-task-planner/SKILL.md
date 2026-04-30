---
name: moondex-task-planner
description: Use when one Moondex implementation task is already defined and needs to be converted into a single executor-ready plan with ownership, steps, checkpoints, acceptance criteria, and verification.
---

# Moondex Task Planner

Turn one defined task into one executor-ready Moondex plan.

## Read First

- `../../docs/planning/task-planner-subagent.md`
- `../../docs/contracts/plan-schema.md`
- `../../docs/templates/plan-template.md`
- `../../docs/execution/role-transfer-contracts.md`
- `../../docs/execution/low-interruption-policy.md`

## Do Not Use For

- Broad task decomposition.
- Wave planning.
- Rewriting product direction.
- Combining multiple tasks into one plan.

## Required Output

Produce a plan with:

- goal and non-goals
- ownership allow/deny paths
- inputs and outputs
- implementation notes
- ordered execution steps
- checkpoints and fallbacks
- acceptance criteria
- test requirements
- verification commands
- integration notes

## Runtime Expectations

The resulting plan should be ready for `moondex` dispatch:

- one logical `task_id`
- clear active role
- no unresolved external decision hidden in the execution steps
- verification commands that an implementer or tester can run
- explicit state/reporting expectations through mailbox output
- clear high-impact blocker conditions so executors do not ask the user for low-level implementation choices
