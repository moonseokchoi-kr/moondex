# Codex Hook Auto-Discovery

Moondex currently treats `.codex/hooks/` as a repo-local, inspectable contract. It does not assume private Codex lifecycle hook behavior that has not been verified in this repository.

## Current Repo-Local Hooks

The executable validators are:

- `.codex/hooks/validate-role-transfer.sh`
- `.codex/hooks/validate-readiness.sh`

Inspect them through Moondex:

```bash
moondex api inspect-hooks --json
```

The response reports hook `name`, `path`, executable status, target operation, smoke command, and status. A hook is `ok` when it is executable and maps to a known Moondex validation operation.

## Discovery Contract

Repo-local discovery means:

- hooks live under `.codex/hooks/`
- executable shell hooks are inspectable
- hook metadata is documented in `.codex/hooks/role-transfer-contract.md`
- `inspect-hooks` reports the hook inventory without mutating runtime state

This gives operators and tests a stable surface even when native Codex lifecycle auto-discovery is unknown.

## Lifecycle Bridge

If native Codex hook auto-discovery is verified later, add the official Codex manifest or config here and update `inspect-hooks` to report that lifecycle status explicitly.

Until then, bridge lifecycle enforcement with explicit validator calls around orchestration:

```bash
moondex api inspect-hooks --json
.codex/hooks/validate-readiness.sh '<readiness-json>'
.codex/hooks/validate-role-transfer.sh '<role-transfer-json>'
moondex api orchestrator-step --input '{"apply":true}' --json
moondex api audit-state --json
```

`write-mailbox` already enforces role output contracts before writing durable mailbox state. `dispatch` already applies lifecycle guards for terminal tasks, role mismatch, and active claims. Explicit hook calls are still useful before planning handoff, readiness dispatch, and operator-controlled transitions.

## Smoke Commands

Valid role transfer:

```bash
.codex/hooks/validate-role-transfer.sh '{"from_role":"implementer","kind":"result","task_id":"T-01","body":"{\"summary\":\"done\",\"changed_files\":[],\"tests\":[\"cargo test -p moondex\"]}"}'
```

Invalid role transfer:

```bash
.codex/hooks/validate-role-transfer.sh '{"from_role":"implementer","kind":"review_approved","task_id":"T-01","body":"{\"summary\":\"bad\",\"checks\":[\"checked\"]}"}'
```

Valid readiness:

```bash
.codex/hooks/validate-readiness.sh '{"task":{"task_id":"T-01","subject":"Add gate","description":"Implement gate."},"plan":{"plan_id":"P-01","task_id":"T-01","objective":"Implement gate.","scope_paths":["crates/moondex/src/fs_state.rs"],"acceptance_criteria":["gate passes"],"verification_commands":["cargo test -p moondex"],"ownership":["crates/moondex/src/fs_state.rs"]}}'
```

Invalid readiness:

```bash
.codex/hooks/validate-readiness.sh '{"task":{"task_id":"T-01"},"plan":{}}'
```

## Operating Rule

Do not treat cmux screen output or assumed Codex hook behavior as source of truth. The source of truth is `.moondex/state`, including hook warnings, audit output, dispatch records, mailbox records, and `events.jsonl`.

