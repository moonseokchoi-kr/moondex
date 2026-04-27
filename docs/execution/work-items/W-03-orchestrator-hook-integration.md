# W-03 Orchestrator Hook Integration

이 문서는 `docs/execution/WORK_TRACKER.md`의 `W-03` 구현을 위한 executor-ready 계획이다.

## Goal

수동으로 호출하던 validator를 Moondex lifecycle에 연결한다. canonical role output과 role handoff는 runtime 경계에서 hard validation을 받고, advisory warning은 `.moondex/state/hooks/warnings.json`에 남긴다.

## Dependencies

- W-01 완료 필요
- W-02 완료 필요

## Scope

수정 대상:

- `crates/moondex/src/model.rs`
- `crates/moondex/src/fs_state.rs`
- `crates/moondex/src/cli.rs`
- `docs/execution/moondex-cli-plan.md`
- `docs/execution/WORK_TRACKER.md`
- `docs/system-ext/HANDOFF.md`

비범위:

- Codex native hook auto-discovery
- next-action command
- readiness auto-dispatch decisions

## Runtime Warning State

Add hook warnings state:

```text
.moondex/state/hooks/warnings.json
```

Warning shape:

```json
{
  "warning_id": "hook-warning-...",
  "hook": "write-mailbox",
  "type": "weak_result_evidence",
  "severity": "warning",
  "task_id": "T-01",
  "role_id": "implementer",
  "message_id": "message-...",
  "detail": "result has no changed_files or tests",
  "created_at": "1777200000"
}
```

## Lifecycle Integration

`write_mailbox`:

- Build a mailbox output validation payload from `WriteMailboxInput`.
- Run the same role transfer validator used by `validate-role-transfer`.
- If `valid == false`, reject before writing with `invalid_role_transfer_contract`.
- If warnings exist, write mailbox normally and then append warning records with the new `message_id`.

`dispatch`:

- Keep existing `dispatch(role, task_id)` shape.
- Apply hard guards:
  - terminal task cannot be dispatched
  - task role mismatch cannot be dispatched
  - task already claimed by another owner cannot be dispatched
- Add warning when dispatch target has no role identity surface.

`audit-state`:

- Add `hooks` issues section or `hook_warnings` section.
- Add `summary.hook_warnings`.
- Do not add hook warnings to `mailbox_issues` or `dispatch_issues`.

## Tests

Required unit tests:

- valid implementer result writes successfully and no hook warning
- implementer `review_approved` write fails
- canonical role output without task_id fails
- warning-only result writes and records hook warning
- completed task dispatch fails
- role mismatch dispatch fails
- dispatch without surface succeeds and records warning
- audit-state includes `hook_warnings` separately

Required commands:

```bash
cargo fmt --check
cargo test -p moondex
cargo build -p moondex
./target/debug/moondex api audit-state --json
```

## Completion

After implementation:

- mark W-03 as `done`
- update docs that previously described validator as manual-only
- leave `.codex/hooks` scripts in place as external entrypoints

