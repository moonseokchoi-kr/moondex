---
name: moondex-runtime
description: Use only after Moondex planning has produced READY wave tasks or existing runtime state must be inspected, dispatched, repaired, archived, or audited. Do not use as the default entrypoint for feature implementation requests.
---

# Moondex Runtime

Use this skill for state-first Moondex runtime work after planning is complete.

## Read First

- `../../docs/execution/moondex-cli-plan.md`
- `../../docs/execution/cmux-operations-playbook.md`
- `../../docs/execution/codex-hook-auto-discovery.md`
- `../../docs/execution/low-interruption-policy.md`
- `../../docs/system-ext/HANDOFF.md`

## Core Rule

`.moondex/state` is the source of truth. cmux screens, terminal scrollback, and dispatch wake-up messages are transport or evidence only.

## Bootstrap Check

Before operating the runtime, run the plugin source script against the target repo:

```bash
./scripts/doctor.sh --json
```

Use the returned `command_prefix` for runtime commands. If doctor reports `setup_required: true`, run:

```bash
./scripts/setup-moondex.sh
```

For a target repo outside the plugin source checkout, pass `--target-root <path>` to both scripts. The default runtime CLI is repo-local `.moondex/bin/moondex`; PATH `moondex` is optional. Do not use `codex plugin list` as an install check because the current Codex CLI does not provide that command.

## Common Commands

Initialize and inspect:

```bash
<command_prefix> init
<command_prefix> status --json
<command_prefix> api audit-state --json
```

Task lifecycle:

```bash
<command_prefix> api create-task --input '<json>' --json
<command_prefix> api claim-task --input '<json>' --json
<command_prefix> api transition-task --input '<json>' --json
<command_prefix> api release-task --input '<json>' --json
```

Mailbox and phase transfer:

```bash
<command_prefix> api write-mailbox --input '<json>' --json
<command_prefix> api consume-mailbox-for-task --input '<json>' --json
<command_prefix> api list-events --input '{"task_id":"T-01","kind":"phase_advanced"}' --json
```

Dispatch:

```bash
<command_prefix> dispatch <role-id> <task-id> --json
<command_prefix> api ack-dispatch --input '<json>' --json
<command_prefix> api retry-dispatch --input '<json>' --json
```

Hooks and archive:

```bash
<command_prefix> api inspect-hooks --json
<command_prefix> api archive-state --input '{"apply":false,"older_than_seconds":2592000}' --json
```

## Workflow

1. Run doctor and resolve setup issues before mutating runtime state.
2. If no runtime task exists yet, use `moondex-task-creator`, `moondex-task-planner`, and `moondex-wave-dispatcher` first. Runtime only receives READY wave tasks after planning is complete.
3. Run `<command_prefix> status --json` and `<command_prefix> api audit-state --json`.
4. Use `<command_prefix> api next-action --json` to choose the next state-first operation.
5. Apply one bounded operation with `orchestrator-step` or run `orchestrator-loop` with a small `max_steps`.
6. If the loop stops on `ack_dispatch_wait`, `review_hook_warnings`, `surface_ref_missing`, or `retry_exhausted`, resolve that state condition before continuing.
7. Query `list-events` after phase changes or archive operations.

## Interruption Policy

Inside an approved wave, continue autonomously unless `low-interruption-policy.md` requires operator input. Prefer mailbox `status`, `result`, or scoped repair over pausing to ask about local implementation choices.
