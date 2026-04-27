# W-06 Orchestrator Next Action Automation

이 문서는 `docs/execution/WORK_TRACKER.md`의 `W-06` 구현을 위한 executor-ready 계획이다.

## Goal

운영자가 `.moondex/state`를 직접 해석하지 않아도 다음에 해야 할 state-first action 하나를 받을 수 있게 한다.

## Dependencies

- W-02 완료 필요
- W-03 완료 필요
- W-04 완료 필요
- W-05 완료 필요

## Scope

수정 대상:

- `crates/moondex/src/model.rs`
- `crates/moondex/src/fs_state.rs`
- `crates/moondex/src/cli.rs`
- `docs/execution/moondex-cli-plan.md`
- `docs/execution/WORK_TRACKER.md`
- `docs/system-ext/HANDOFF.md`

비범위:

- action 자동 실행
- scheduler loop
- cmux pane 생성 자동화

## API Shape

Command:

```bash
moondex api next-action --json
```

Output shape:

```json
{
  "action": "consume_mailbox",
  "reason": "orchestrator has unconsumed result for task T-01",
  "task_id": "T-01",
  "role_id": "orchestrator",
  "command": "moondex api consume-mailbox-for-task --input '...' --json",
  "confidence": "high"
}
```

Allowed actions:

- `repair_state`
- `review_hook_warnings`
- `consume_mailbox`
- `ack_dispatch_wait`
- `dispatch_implementer`
- `dispatch_code_reviewer`
- `dispatch_compliance_reviewer`
- `dispatch_tester`
- `validate_readiness`
- `transition_completed`
- `mark_blocked`
- `wait`

## Priority Rules

1. If audit has mailbox/dispatch issues, recommend `repair_state`.
2. If hook warnings exist, recommend `review_hook_warnings`.
3. If unconsumed orchestrator mailbox exists, recommend `consume_mailbox`.
4. If dispatch is pending/notified and not delivered, recommend `ack_dispatch_wait`.
5. If task is ready but unassigned, recommend dispatch to required role.
6. If code review passed and compliance required, recommend compliance dispatch.
7. If tester required, recommend tester dispatch.
8. If task appears done and all reviews passed, recommend transition completed.
9. Otherwise recommend `wait`.

## Tests

Required unit tests:

- audit issue recommends repair
- unconsumed mailbox recommends consume
- pending dispatch recommends wait for ACK
- ready task recommends implementer dispatch
- code-review approval with compliance required recommends compliance reviewer
- no actionable state recommends wait

Required commands:

```bash
cargo fmt --check
cargo test -p moondex
cargo build -p moondex
./target/debug/moondex api next-action --json
```

## Completion

After implementation:

- mark W-06 as `done`
- document that next-action is advisory and non-mutating

