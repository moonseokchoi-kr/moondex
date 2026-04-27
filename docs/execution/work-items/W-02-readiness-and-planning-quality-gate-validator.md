# W-02 Readiness And Planning Quality Gate Validator

이 문서는 `docs/execution/WORK_TRACKER.md`의 `W-02` 구현을 위한 executor-ready 계획이다.

## Goal

`docs/execution/task-readiness-gate.md`의 READY / REVISION_REQUIRED / BLOCKED 판정을 `moondex api validate-readiness`와 `.codex/hooks/validate-readiness.sh`로 실행 가능하게 만든다.

## Dependencies

- W-01 완료 필요
- `validate-role-transfer`가 planning payload를 검증할 수 있어야 한다

## Scope

수정 대상:

- `crates/moondex/src/cli.rs`
- `crates/moondex/src/fs_state.rs`
- `.codex/hooks/validate-readiness.sh`
- `.codex/hooks/role-transfer-contract.md`
- `docs/execution/task-readiness-gate.md`
- `docs/execution/moondex-cli-plan.md`
- `docs/execution/WORK_TRACKER.md`
- `docs/system-ext/HANDOFF.md`

비범위:

- orchestrator flow 자동 연결
- hook warning 저장
- next-action 자동화

## API Shape

Command:

```bash
moondex api validate-readiness --input '<json>' --json
```

Input shape:

```json
{
  "task": {
    "task_id": "T-01",
    "subject": "Add retry limit",
    "description": "Limit retry attempts."
  },
  "plan": {
    "plan_id": "P-01",
    "task_id": "T-01",
    "objective": "Implement retry limit.",
    "scope_paths": ["crates/moondex/src/fs_state.rs"],
    "acceptance_criteria": ["retry is capped"],
    "verification_commands": ["cargo test -p moondex"],
    "ownership": ["crates/moondex/src/fs_state.rs"]
  },
  "wave": {
    "wave_id": "W-01",
    "validated_ready_tasks": ["T-01"],
    "dependency_graph": [{"task_id": "T-01", "depends_on": []}],
    "verification_plan": ["cargo test -p moondex"]
  }
}
```

Output shape:

```json
{
  "decision": "READY",
  "errors": [],
  "warnings": [],
  "missing_fields": []
}
```

Decision values:

- `READY`
- `REVISION_REQUIRED`
- `BLOCKED`

## Validation Rules

Hard `BLOCKED`:

- task has an explicit unresolved dependency
- task or plan contains `blocked_reason`
- required upstream decision is missing
- wave dependency references a task not present in the payload

Hard `REVISION_REQUIRED`:

- missing task subject or description
- missing plan
- missing plan objective
- missing ownership or scope paths
- missing acceptance criteria
- missing verification commands
- missing wave dependency graph when wave is supplied
- missing verification plan when wave is supplied

Warnings:

- verification command is too weak
- scope paths are broad, such as `.` or repository root
- acceptance criteria are vague
- wave has multiple tasks but no parallel-safety note

Decision precedence:

1. Any `BLOCKED` issue returns `BLOCKED`.
2. Otherwise any revision issue returns `REVISION_REQUIRED`.
3. Otherwise return `READY`.

## Hook Wrapper

Add:

```bash
.codex/hooks/validate-readiness.sh '<json>'
```

Behavior:

- exits `0` only when `decision` is `READY`
- exits non-zero for `REVISION_REQUIRED` or `BLOCKED`
- prints the full JSON response

## Tests

Required unit tests:

- valid task + plan returns `READY`
- valid task + plan + wave returns `READY`
- missing plan verification returns `REVISION_REQUIRED`
- missing ownership returns `REVISION_REQUIRED`
- explicit blocked reason returns `BLOCKED`
- unresolved dependency returns `BLOCKED`
- warning-only payload remains `READY`

Required commands:

```bash
cargo fmt --check
cargo test -p moondex
cargo build -p moondex
.codex/hooks/validate-readiness.sh '<valid-ready-json>'
.codex/hooks/validate-readiness.sh '<invalid-missing-verification-json>'
```

## Completion

After implementation:

- mark W-02 as `done` in `WORK_TRACKER.md`
- add a completion note with date
- update HANDOFF immediate next item to W-03 or W-04 depending on chosen order

