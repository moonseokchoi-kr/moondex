# Moondex Risk Probes

이 문서는 `moondex` runtime MVP의 남은 리스크를 실제 CLI/cmux probe로 확인한 결과다.

## Probe Summary

| Risk | Probe Result | Status |
| --- | --- | --- |
| task별 mailbox 필터 부재 | `read-mailbox`가 `task_id`를 무시해 다른 task 메시지를 반환했다. | fixed |
| output schema validation 부재 | 빈 `body`와 임의 `kind`가 mailbox에 저장됐다. | fixed for new writes |
| stale heartbeat detection 부재 | 오래된 role status를 판정하는 명령이 없었다. | fixed with `list-stale-roles` |
| invalid cmux surface fallback | `cmux send --surface surface:999999`가 현재 surface로 fallback하고 성공처럼 보였다. | fixed |
| failed worker retry policy 부재 | same-request `retry-dispatch`가 없었다. | fixed |
| legacy invalid state | 수정 전 생성된 invalid mailbox/dispatch가 그대로 남아 있었다. | fixed with audit/repair |
| task-scoped consume helper 부재 | reviewer/orchestrator가 message id를 직접 복사해야 했다. | fixed |
| retry attempt evidence 부재 | retry count/history가 없어 반복 전송 추적이 어려웠다. | fixed |

## Fixes Applied

- `read-mailbox` now accepts `task_id` and filters messages by task.
- `write-mailbox` now rejects unknown `kind` and requires `body` to be a JSON object string matching the selected `kind` schema.
- `list-stale-roles` reports role statuses older than a configured threshold.
- `cmux send` and `cmux capture` validate that the target surface exists in `cmux tree --json`.
- `cmux send` also checks that stdout starts with the requested `OK surface:<id>` target.
- `retry-dispatch` reuses the same request id and resolves the latest role identity surface before sending.
- `retry-dispatch` records `retry_count` and `retry_history` with each retry outcome.
- `consume-mailbox-for-task` consumes the first matching unconsumed message for a task, optionally narrowed by sender and kind.
- `audit-state` reports legacy invalid mailbox and dispatch entries.
- `repair-state --input '{"apply":true}'` repairs legacy invalid mailbox and dispatch entries.

## Verified Commands

```bash
cargo test -p moondex
./target/debug/moondex api read-mailbox --input '{"role_id":null,"task_id":"T-RUNTIME-02","unconsumed_only":true}' --json
./target/debug/moondex api write-mailbox --input '{"from_role":"implementer","kind":"not_a_contract_kind","task_id":"T-RUNTIME-02","body":""}' --json
./target/debug/moondex api list-stale-roles --input '{"older_than_seconds":60}' --json
./target/debug/moondex dispatch broken_worker T-RISK-RETRY-02 --json
./target/debug/moondex api audit-state --json
./target/debug/moondex api repair-state --input '{"apply":false}' --json
./target/debug/moondex api repair-state --input '{"apply":true}' --json
./target/debug/moondex api retry-dispatch --input '{"request_id":"dispatch-broken_worker-1777186295920"}' --json
./target/debug/moondex api write-mailbox --input '{"from_role":"implementer","kind":"result","task_id":"T-RUNTIME-03","body":"{\"summary\":\"task scoped consume smoke\",\"changed_files\":[],\"not_run_reason\":\"smoke message\"}"}' --json
./target/debug/moondex api consume-mailbox-for-task --input '{"role_id":null,"task_id":"T-RUNTIME-03","from_role":"implementer","kind":"result"}' --json
./target/debug/moondex api retry-dispatch --input '{"request_id":"dispatch-broken_worker-1777188159870"}' --json
```

## Important Finding

`cmux` may accept an invalid `--surface` argument and target the current surface instead. Therefore `moondex` must not treat `cmux send` exit code alone as delivery evidence.

The runtime now validates target surface existence before send/capture. It also rejects a send result if the returned `OK surface:<id>` does not match the requested surface.

## Remaining Work

- Define any future retry backoff policy if automation is added. Current runtime intentionally uses a limit-only manual retry policy.
