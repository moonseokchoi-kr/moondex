# W-05 Tester Contract And Integration/E2E Boundary

이 문서는 `docs/execution/WORK_TRACKER.md`의 `W-05` 구현을 위한 executor-ready 계획이다.

## Goal

tester를 언제 별도 role로 dispatch하는지, tester가 어떤 payload를 받고 어떤 mailbox output을 반환하는지 고정한다.

## Scope

수정 대상:

- `docs/execution/role-transfer-contracts.md`
- `docs/execution/multi-agent-orchestration.md`
- `docs/execution/task-readiness-gate.md`
- `docs/examples/money-track-app-bootstrap-theme/`
- `docs/examples/money-track-app-bootstrap-theme-raw-replan/`
- `docs/execution/WORK_TRACKER.md`
- `docs/system-ext/HANDOFF.md`

필요하면 수정:

- `crates/moondex/src/fs_state.rs` role/kind validator to recognize `tester`

비범위:

- test runner automation
- E2E environment provisioning
- next-action automation

## Tester Dispatch Criteria

Dispatch tester when any condition is true:

- integration test or E2E execution is required
- cross-flow regression must be verified
- environment-specific behavior must be validated
- reviewer asks for independent test evidence
- task changes onboarding, persistence, routing, auth, external IO, or user-critical flows

Tester can be skipped when all conditions are true:

- unit tests cover the change
- no integration boundary changed
- no cross-flow behavior changed
- code-reviewer does not request independent testing

## Payload Contracts

Tester input required fields:

- `contract_type: "tester_input"`
- `task_id`
- `plan_id`
- `source_role`
- `target_role: "tester"`
- `test_scope`
- `changed_files`
- `verification_commands`
- `acceptance_criteria`
- `environment_notes`

Tester output uses mailbox kinds:

- `result`: test pass or completed test evidence
- `blocked`: environment/test fixture unavailable
- `question`: unclear expected behavior
- `status`: long-running test progress

## Validator Updates

If role/kind gating includes canonical `tester`:

- allow `tester`: `result`, `blocked`, `question`, `status`
- require `task_id`
- reject reviewer-only kinds from tester

If planning contract validator exists:

- add `tester_input` validation

## Tests

Docs-only verification:

```bash
rg -n "tester_input|tester|integration|E2E|cross-flow|regression" docs/execution docs/examples
```

If validator changes:

```bash
cargo fmt --check
cargo test -p moondex
.codex/hooks/validate-role-transfer.sh '<valid-tester-result-json>'
```

## Completion

After implementation:

- mark W-05 as `done`
- update HANDOFF so tester boundary is no longer listed as unclear

