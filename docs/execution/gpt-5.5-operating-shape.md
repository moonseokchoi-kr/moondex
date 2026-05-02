# GPT-5.5 Operating Shape

This document adapts OpenAI GPT-5.5 prompt guidance for Moondex skills.

Source:

- OpenAI Prompt guidance: `https://developers.openai.com/api/docs/guides/prompt-guidance`

## Purpose

Moondex should preserve its state-first runtime invariants while avoiding overly procedural skill behavior. GPT-5.5 works best when prompts are outcome-first, completion criteria are explicit, and tool-heavy work continues through reversible in-scope decisions without excessive narration.

## Operating Rules

- Prefer outcome-first execution over process narration.
- Use mandatory order only to preserve Moondex invariants.
- Choose the shortest safe path that satisfies task, plan, wave, readiness, and runtime truth.
- Keep preambles short: state the current stage and first concrete action, then use tools.
- Continue through reversible, in-scope implementation choices without asking the user.
- Use progress updates for meaningful state changes, not every local decision.
- Stop only for high-impact blockers, missing source-of-truth artifacts, unsafe side effects, or required external approvals.
- Treat incomplete task, plan, wave, readiness, or runtime evidence as work to resolve, not as a final answer.

## Moondex Invariants

These rules remain hard constraints:

- `.moondex/state` is runtime source of truth.
- Do not dispatch a task without an executor-ready plan.
- Do not enqueue runtime tasks before wave approval and readiness validation.
- Do not decide parallelism from task titles alone; use dependencies, ownership, shared contracts, and plan constraints.
- Do not treat terminal output, cmux wake-up, or chat narration as runtime truth.
- Do not bypass `low-interruption-policy.md` high-impact blocker rules.

## Skill Writing Guidance

When updating Moondex skills:

- Put short decision rules before long procedural checklists.
- Keep `must`, `never`, and `only` for true invariants.
- Convert situational instructions into `if/then` rules.
- Define what counts as done.
- Tell the agent which evidence to inspect and what signal should trigger the next phase.
- Prefer one compact status update before tool-heavy work instead of an upfront plan that delays execution.

## Runtime Guidance

For runtime operation:

- Run doctor before mutating runtime state when the target repo has Moondex bootstrap scripts.
- Use `next-action`, `orchestrator-step`, or `orchestrator-loop` to advance state instead of inventing a local flow.
- After state mutation, inspect event, mailbox, dispatch, or audit evidence relevant to that mutation.
- Do not stop after advisory inspection if a safe state-first next action is available.

## Planning Guidance

For task, plan, and wave work:

- Create all missing tasks before planning individual execution unless a source-of-truth task set already exists.
- Plan every dispatchable task before deciding waves.
- Decide parallelism from the complete plan set.
- If a required artifact is missing, create or repair that artifact rather than explaining how to create it.

## Verification Guidance

Use the lightest verification that proves the affected Moondex layer:

- docs-only skill or policy change: `rg` checks, file existence checks, and `git diff --check`
- plugin metadata change: JSON validation and doctor
- runtime-impacting change: `cargo fmt --check`, `cargo test -p moondex`, and doctor
- release/version change: version grep, tag check, and clean worktree check

Do not add full automatic evolution, rollout aggregation, or auto-rollback behavior under this guidance. Those remain outside AHE-lite.
