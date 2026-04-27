# W-08 Runtime State Cleanup And Archive Policy

이 문서는 `docs/execution/WORK_TRACKER.md`의 `W-08` 구현을 위한 executor-ready 계획이다.

## Goal

`.moondex/state`가 장기 운영 중 계속 커질 때 무엇을 보존하고 무엇을 archive할지 정한다.

## Scope

수정 대상:

- `docs/execution/moondex-cli-plan.md`
- `docs/execution/cmux-runtime-alignment.md`
- `docs/execution/WORK_TRACKER.md`
- `docs/system-ext/HANDOFF.md`

W-08 비범위:

- `archive-state` Rust command 구현
- 자동 삭제
- evidence 파일 압축

Note: the Rust command was implemented later in W-12.

## Retention Policy

Must keep:

- active tasks
- in-progress task claims
- pending/notified dispatch requests
- unread or unconsumed mailbox messages
- current role identity/status
- audit-relevant invalid state until repaired

Can archive manually:

- completed tasks older than an operator-chosen cutoff
- consumed mailbox messages linked to completed tasks
- delivered dispatch requests linked to completed tasks
- old hook warnings after review
- evidence files once referenced in a handoff or external artifact

Must not delete silently:

- failed dispatch requests
- blocked tasks
- retry_exhausted records
- repair/audit evidence needed for debugging

## Command Spec

W-08 documented the future command shape; W-12 implemented it:

```bash
moondex api archive-state --input '{"apply":false,"older_than_seconds":2592000}' --json
```

Dry-run output should include:

- candidate tasks
- candidate mailbox messages
- candidate dispatch requests
- candidate hook warnings
- candidate evidence files

Apply mode should move records under:

```text
.moondex/state/archive/<timestamp>/
```

## Tests

Docs-only verification:

```bash
rg -n "archive-state|retention|archive|cleanup|retry_exhausted|hook warnings" docs/execution docs/system-ext/HANDOFF.md
```

## Completion

After implementation:

- mark W-08 as `done`
- track actual `archive-state` implementation in W-12
