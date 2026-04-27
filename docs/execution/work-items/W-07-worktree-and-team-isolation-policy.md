# W-07 Worktree And Team Isolation Policy

이 문서는 `docs/execution/WORK_TRACKER.md`의 `W-07` 구현을 위한 executor-ready 계획이다.

## Goal

이 저장소가 git repo가 아닌 상태에서도 team isolation 정책을 명확히 하고, product repo가 worktree를 지원할 때만 worktree-first 운영을 적용하도록 문서화한다.

## Scope

수정 대상:

- `docs/execution/cmux-runtime-alignment.md`
- `docs/execution/moondex-cli-plan.md`
- `docs/execution/multi-agent-orchestration.md`
- `docs/execution/WORK_TRACKER.md`
- `docs/system-ext/HANDOFF.md`

비범위:

- worktree 자동 생성 코드
- git command automation
- role identity Rust schema 변경

## Isolation Modes

Document three modes:

- `no_worktree`: current docs/runtime workspace mode
- `external_worktree`: target product repository provides git worktrees
- `future_managed_worktree`: planned but out of scope for Moondex v1

Rules:

- `codex-moon-harness` cannot require git worktrees while it is not a git repository.
- cmux role surfaces are still required for visible role separation.
- worktree isolation belongs to target product repo execution, not documentation repo state.
- role identity may document future metadata such as `workspace_root`, `worktree_branch`, and `isolation_mode`, but do not add Rust fields in W-07.

## Tests

Docs-only verification:

```bash
rg -n "no_worktree|external_worktree|future_managed_worktree|worktree|isolation" docs/execution docs/system-ext/HANDOFF.md
```

## Completion

After implementation:

- mark W-07 as `done`
- remove HANDOFF wording that treats worktree policy as undecided

