# Low-Interruption Execution Policy

Moondex should continue autonomously inside an approved wave unless a high-impact blocker requires operator input.

## Default Rule

- Continue without asking the user for low-level implementation choices.
- Use repository conventions, approved task/plan/wave artifacts, tests, and conservative defaults.
- Report progress through Moondex state, mailbox, and phase checkpoints.
- Do not pause for confirmation when the decision is local to the approved task scope.

## Ask The User Only For

- Source documents conflict and the conflict changes user-visible behavior.
- Approved plan scope must expand into API, schema, persisted state, migration, security, privacy, payment, deletion, or external service behavior.
- A destructive command or external credential/access is required.
- Dependency installation or network access is required and not already approved.
- Test failures reveal an architectural decision outside the task plan.
- The wave plan must change because task boundaries or ownership are invalid.

## Do Not Ask For

- File location choices that existing repo conventions answer.
- Small refactors inside ownership allow paths.
- Test placement or fixture details when local patterns are clear.
- Lint, format, type, or unit test failures that are fixable inside the task.
- Reviewer requested changes that remain inside the approved task and plan.
- Choosing a conservative fallback already described by the plan.

## Reporting

- Use mailbox `status` for progress.
- Use mailbox `question` only for high-impact blockers.
- Use mailbox `blocked` only when execution cannot continue without operator input or upstream planning repair.
- Summarize at phase checkpoints instead of interrupting for every decision.

## Approval Points

The expected operator touchpoints are:

- wave approval before runtime enqueue
- high-impact blocker resolution
- final integration summary
