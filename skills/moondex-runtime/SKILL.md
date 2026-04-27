---
name: moondex-runtime
description: Use when operating the Moondex runtime CLI, inspecting `.moondex/state`, advancing task phases, querying event logs, archiving state, or checking Codex hook discovery for this harness.
---

# Moondex Runtime

Use this skill for state-first Moondex runtime work.

## Read First

- `../../docs/execution/moondex-cli-plan.md`
- `../../docs/execution/cmux-operations-playbook.md`
- `../../docs/execution/codex-hook-auto-discovery.md`
- `../../docs/system-ext/HANDOFF.md`

## Core Rule

`.moondex/state` is the source of truth. cmux screens, terminal scrollback, and dispatch wake-up messages are transport or evidence only.

## Common Commands

Initialize and inspect:

```bash
moondex init
moondex status --json
moondex api audit-state --json
```

Task lifecycle:

```bash
moondex api create-task --input '<json>' --json
moondex api claim-task --input '<json>' --json
moondex api transition-task --input '<json>' --json
moondex api release-task --input '<json>' --json
```

Mailbox and phase transfer:

```bash
moondex api write-mailbox --input '<json>' --json
moondex api consume-mailbox-for-task --input '<json>' --json
moondex api list-events --input '{"task_id":"T-01","kind":"phase_advanced"}' --json
```

Dispatch:

```bash
moondex dispatch <role-id> <task-id> --json
moondex api ack-dispatch --input '<json>' --json
moondex api retry-dispatch --input '<json>' --json
```

Hooks and archive:

```bash
moondex api inspect-hooks --json
moondex api archive-state --input '{"apply":false,"older_than_seconds":2592000}' --json
```

## Workflow

1. Run `moondex status --json` and `moondex api audit-state --json`.
2. Use `moondex api next-action --json` to choose the next state-first operation.
3. Apply one bounded operation with `orchestrator-step` or run `orchestrator-loop` with a small `max_steps`.
4. If the loop stops on `ack_dispatch_wait`, `review_hook_warnings`, `surface_ref_missing`, or `retry_exhausted`, resolve that state condition before continuing.
5. Query `list-events` after phase changes or archive operations.

