# W-04 Compliance-Reviewer Escalation Policy

이 문서는 `docs/execution/WORK_TRACKER.md`의 `W-04` 구현을 위한 executor-ready 계획이다.

## Goal

`compliance-reviewer`를 언제 붙이고 언제 생략할 수 있는지 운영자가 새 기준을 만들지 않아도 판단할 수 있게 정책을 고정한다.

## Scope

수정 대상:

- `docs/execution/role-transfer-contracts.md`
- `docs/execution/multi-agent-orchestration.md`
- `docs/executor-direction.md`
- `docs/execution/WORK_TRACKER.md`
- `docs/system-ext/HANDOFF.md`

필요하면 수정:

- `crates/moondex/src/fs_state.rs` validator warning rules

비범위:

- tester contract
- next-action automation
- lifecycle hook integration

## Policy

Compliance review required when any condition is true:

- user-visible behavior changes
- shared contract, CLI/API, schema, persisted state, or external interface changes
- security, privacy, safety, or policy-sensitive behavior changes
- multiple spec/design/implementation docs must agree
- broad refactor or scope drift risk exists
- data migration, repair, or archive behavior changes
- code-reviewer explicitly marks `compliance_review_required: true`

Compliance review can be skipped only when all conditions are true:

- change is narrow and internal
- no public behavior change
- no durable state contract change
- no shared interface change
- tests or review evidence cover the touched behavior
- code-reviewer explicitly marks low risk

Blocked compliance decision when:

- relevant spec/design source is missing
- task scope conflicts with source documents
- product/user decision is required

## Documentation Additions

Add examples:

- code-reviewer approval with compliance skipped
- code-reviewer approval with compliance required
- code-reviewer blocked because compliance decision lacks source docs
- compliance-reviewer approval
- compliance-reviewer changes requested

## Validator Updates

If W-01 validator supports code-reviewer output payloads with `compliance_review_required`, add warnings:

- code-reviewer approval missing `compliance_review_required`
- compliance skipped while changed files include docs/contracts, model, schema, CLI, state, or migration-sensitive paths

Do not make these hard failures in W-04 unless role-transfer contract already requires the field.

## Tests

Docs-only verification:

```bash
rg -n "compliance_review_required|compliance skipped|compliance required|Compliance review required" docs/execution docs/executor-direction.md
```

If validator changes:

```bash
cargo fmt --check
cargo test -p moondex
```

## Completion

After implementation:

- mark W-04 as `done`
- remove HANDOFF item saying compliance escalation criteria are not defined

