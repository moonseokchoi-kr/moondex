# Role Transfer Contracts

이 문서는 `codex-moon-harness`의 멀티에이전트 실행에서 역할 간 전달되는 canonical input/output contract를 정의한다.

현재 단계의 contract는 문서, 복사 가능한 `moondex api` payload 예시, 그리고 `moondex api validate-role-transfer` 검증으로 고정한다. 별도 JSON Schema 파일은 아직 추가하지 않는다.

자동 검증 entrypoint는 `.codex/hooks/validate-role-transfer.sh`다. 이 hook은 `moondex api validate-role-transfer --input '<json>' --json`를 호출하며, hard contract error가 있으면 non-zero로 종료한다.

## Position

Role transfer contract는 세션 인수인계 문서가 아니라 agent 간 실행 입력/출력 계약이다.

- `HANDOFF.md`: 세션 간 continuation artifact
- role transfer contract: 하나의 task가 다음 role로 넘어갈 때 보존해야 하는 실행 payload
- mailbox message: role output을 `.moondex/state/mailbox/<role>.json`에 저장하는 durable event

Source of truth는 `.moondex/state`와 문서 artifact다. 터미널 출력이나 `cmux` 화면은 보조 신호이며 contract를 대체하지 않는다.

## Common Rules

- 같은 task는 한 시점에 한 owner만 가진다.
- execution agent는 `validated-ready` task만 받는다.
- implementer는 승인된 plan, ownership 범위, verification commands 없이 시작하지 않는다.
- reviewer는 구현 결과, 변경 경로, verification 결과 없이 승인하지 않는다.
- contract는 "가능하면 해석"이 아니라 "없으면 blocked" 기준으로 본다.
- role output은 현재 mailbox schema를 사용한다. `body`는 JSON object encoded string이어야 한다.
- `.codex/hooks`는 contract enforcement 위치이고, `.moondex/state`는 runtime state 위치다.

Hard failures:

- canonical role output의 role/kind 조합이 contract와 맞지 않음
- canonical role output에 `task_id`가 없음
- required handoff envelope field 누락
- mailbox body schema 위반

Warnings:

- result evidence가 약함
- blocking review change request 설명이 너무 짧음
- handoff verification command가 지나치게 약함
- code-reviewer approval에 `compliance_review_required` 결정이 없음
- compliance skipped로 표시했지만 contract, CLI, schema, state, migration-sensitive path가 변경됨

## Common Envelope

실행 루프 payload는 아래 필드를 보존한다.

```json
{
  "task_id": "T-01",
  "plan_id": "P-01",
  "wave_id": "W-01",
  "source_role": "orchestrator",
  "target_role": "implementer",
  "current_status": "validated-ready",
  "target_status": "implementing",
  "source_document_paths": [
    "docs/templates/task-template.md",
    "docs/templates/plan-template.md"
  ],
  "scope_paths": [
    "crates/moondex/src/fs_state.rs"
  ],
  "verification_commands": [
    "cargo test -p moondex"
  ],
  "acceptance_criteria": [
    "new behavior is covered by tests"
  ],
  "handoff_summary": "Implement the approved task within the listed ownership scope.",
  "assumptions": []
}
```

Required fields for execution loop handoff:

- `task_id`
- `plan_id`
- `source_role`
- `target_role`
- `current_status`
- `target_status`
- `scope_paths`
- `verification_commands`
- `acceptance_criteria`
- `handoff_summary`

Optional but recommended:

- `wave_id`
- `source_document_paths`
- `blocked_reason`
- `shared_contract_change`
- `review_type`
- `assumptions`

## Orchestrator To Implementer

Purpose: assign one validated task to an implementer.

Minimum payload:

```json
{
  "task_id": "T-01",
  "plan_id": "P-01",
  "wave_id": "W-01",
  "source_role": "orchestrator",
  "target_role": "implementer",
  "current_status": "validated-ready",
  "target_status": "implementing",
  "scope_paths": [
    "crates/moondex/src/fs_state.rs",
    "docs/execution/moondex-cli-plan.md"
  ],
  "forbidden_paths": [
    "Cargo.lock"
  ],
  "verification_commands": [
    "cargo fmt --check",
    "cargo test -p moondex"
  ],
  "acceptance_criteria": [
    "retry-dispatch rejects exhausted retry attempts",
    "docs describe the public behavior"
  ],
  "handoff_summary": "Implement the approved retry limit plan without changing unrelated runtime behavior.",
  "blocked_return": {
    "kind": "blocked",
    "reason_required": true,
    "needs_required": true
  }
}
```

State transition:

- `validated-ready -> implementing`

## Implementer Output

Successful implementer output uses `kind: result`.

```bash
moondex api write-mailbox --input '{"from_role":"implementer","kind":"result","task_id":"T-01","body":"{\"summary\":\"Implemented retry limit and updated docs.\",\"changed_files\":[\"crates/moondex/src/fs_state.rs\",\"docs/execution/moondex-cli-plan.md\"],\"tests\":[\"cargo fmt --check\",\"cargo test -p moondex\"]}"}' --json
```

If tests were not run, `tests` may be omitted or empty only when `not_run_reason` is present:

```bash
moondex api write-mailbox --input '{"from_role":"implementer","kind":"result","task_id":"T-01","body":"{\"summary\":\"Documentation-only update completed.\",\"changed_files\":[\"docs/execution/role-transfer-contracts.md\"],\"not_run_reason\":\"docs-only change\"}"}' --json
```

Blocked implementer output uses `kind: blocked`.

```bash
moondex api write-mailbox --input '{"from_role":"implementer","kind":"blocked","task_id":"T-01","body":"{\"reason\":\"The approved scope does not include the required API change.\",\"needs\":\"Orchestrator decision on whether to expand scope or return to planning.\"}"}' --json
```

Clarification output uses `kind: question`.

```bash
moondex api write-mailbox --input '{"from_role":"implementer","kind":"question","task_id":"T-01","body":"{\"question\":\"Should this change update runtime state or docs only?\",\"decision_needed\":\"Choose docs-only or code+docs before implementation continues.\"}"}' --json
```

Progress output uses `kind: status`.

```bash
moondex api write-mailbox --input '{"from_role":"implementer","kind":"status","task_id":"T-01","body":"{\"state\":\"working\",\"summary\":\"Tests are passing; updating docs next.\"}"}' --json
```

State transitions:

- `implementation -> code_review` when the orchestrator consumes an implementer `result`
- `implementing -> blocked` when blocked output requires orchestrator action

## Orchestrator To Code-Reviewer

Purpose: request mandatory code quality review for an implementer result.

Minimum payload:

```json
{
  "task_id": "T-01",
  "plan_id": "P-01",
  "source_role": "orchestrator",
  "target_role": "code-reviewer",
  "current_status": "reviewing",
  "target_status": "reviewing",
  "review_type": "code",
  "plan_path": "docs/templates/plan-template.md",
  "implementer_result": {
    "summary": "Implemented retry limit and updated docs.",
    "changed_files": [
      "crates/moondex/src/fs_state.rs",
      "docs/execution/moondex-cli-plan.md"
    ],
    "tests": [
      "cargo test -p moondex"
    ]
  },
  "scope_paths": [
    "crates/moondex/src/fs_state.rs",
    "docs/execution/moondex-cli-plan.md"
  ],
  "verification_commands": [
    "cargo test -p moondex"
  ],
  "acceptance_criteria": [
    "retry exhaustion is durable and tested"
  ],
  "handoff_summary": "Review for correctness, regressions, test coverage, and contract drift."
}
```

Code-reviewer must lead with findings. If there are no findings, it must say so and note residual test risk.

## Code-Reviewer Output

Approval uses `kind: review_approved`.

```bash
moondex api write-mailbox --input '{"from_role":"code-reviewer","kind":"review_approved","task_id":"T-01","body":"{\"summary\":\"No blocking issues found. Retry exhaustion behavior and tests match the plan.\",\"checks\":[\"Reviewed retry limit behavior\",\"Reviewed exhausted state persistence\",\"Reviewed test coverage\"]}"}' --json
```

Requested changes use `kind: review_changes_requested`.

```bash
moondex api write-mailbox --input '{"from_role":"code-reviewer","kind":"review_changes_requested","task_id":"T-01","body":"{\"summary\":\"Retry exhaustion updates state but lacks a regression test for delivered requests.\",\"changes\":[\"Add a test proving delivered dispatch still rejects retry before retry limit logic.\"],\"severity\":\"medium\"}"}' --json
```

State transitions:

- approval with no compliance requirement: same task `phase=done`
- approval with compliance requirement: same task requeues as `phase=compliance_review`, `role=compliance-reviewer`
- approval with tester requirement: same task requeues as `phase=testing`, `role=tester`
- changes within plan scope: `reviewing -> implementing`
- plan or ownership issue: `reviewing -> planned`
- external decision needed: `reviewing -> blocked`

## Orchestrator To Compliance-Reviewer

Purpose: request conditional compliance review for spec/design/implementation alignment.

Minimum payload:

```json
{
  "task_id": "T-01",
  "plan_id": "P-01",
  "source_role": "orchestrator",
  "target_role": "compliance-reviewer",
  "current_status": "reviewing",
  "target_status": "reviewing",
  "review_type": "compliance",
  "plan_path": "docs/templates/plan-template.md",
  "spec_paths": [
    "docs/executor-direction.md"
  ],
  "design_paths": [
    "docs/execution/multi-agent-orchestration.md"
  ],
  "implementation_paths": [
    "docs/execution/moondex-cli-plan.md"
  ],
  "implementer_result": {
    "summary": "Implemented retry limit and updated docs.",
    "changed_files": [
      "crates/moondex/src/fs_state.rs",
      "docs/execution/moondex-cli-plan.md"
    ],
    "tests": [
      "cargo test -p moondex"
    ]
  },
  "code_review_result": {
    "summary": "No blocking code issues found.",
    "checks": [
      "Reviewed retry limit behavior"
    ]
  },
  "scope_paths": [
    "crates/moondex/src/fs_state.rs",
    "docs/execution/moondex-cli-plan.md"
  ],
  "handoff_summary": "Check whether the implementation remains aligned with source-of-truth runtime contracts."
}
```

Compliance review is required when any of these are true:

- user-visible behavior changes
- shared contract, CLI/API, schema, persisted state, or external interface semantics change
- security, privacy, safety, or policy-sensitive behavior changes
- multiple spec/design documents must agree
- broad refactor or scope drift risk exists
- data migration, repair, cleanup, or archive behavior changes
- `code-reviewer` explicitly marks `compliance_review_required: true`

Compliance review may be skipped when all of these are true:

- change is narrow and internal
- no public behavior or durable state contract changes
- no shared contract or interface changes
- tests or review evidence cover the touched behavior
- code-reviewer explicitly marks the task low risk and `compliance_review_required: false`

Compliance decision is blocked when source documents are missing, task scope conflicts with source documents, or product/user decision is required.

Code-reviewer approval with compliance skipped:

```bash
moondex api write-mailbox --input '{"from_role":"code-reviewer","kind":"review_approved","task_id":"T-01","body":"{\"summary\":\"No blocking issues found. Change is narrow and internal.\",\"checks\":[\"Reviewed implementation\",\"Reviewed tests\"],\"compliance_review_required\":false,\"changed_files\":[\"crates/moondex/src/fs_state.rs\"]}"}' --json
```

Code-reviewer approval with compliance required:

```bash
moondex api write-mailbox --input '{"from_role":"code-reviewer","kind":"review_approved","task_id":"T-01","body":"{\"summary\":\"No code issues found, but persisted state semantics changed.\",\"checks\":[\"Reviewed implementation\",\"Reviewed tests\"],\"compliance_review_required\":true,\"changed_files\":[\"crates/moondex/src/model.rs\",\"docs/execution/moondex-cli-plan.md\"]}"}' --json
```

Compliance decision blocked:

```bash
moondex api write-mailbox --input '{"from_role":"code-reviewer","kind":"blocked","task_id":"T-01","body":"{\"reason\":\"Compliance decision needs the missing source contract for archive semantics.\",\"needs\":\"Provide or update the source-of-truth retention policy before compliance dispatch.\"}"}' --json
```

## Compliance-Reviewer Output

Approval uses `kind: review_approved`.

```bash
moondex api write-mailbox --input '{"from_role":"compliance-reviewer","kind":"review_approved","task_id":"T-01","body":"{\"summary\":\"Implementation aligns with runtime contract and documented retry policy.\",\"checks\":[\"Checked CLI behavior against docs\",\"Checked persisted state semantics\",\"Checked scope boundaries\"]}"}' --json
```

Requested changes use `kind: review_changes_requested`.

```bash
moondex api write-mailbox --input '{"from_role":"compliance-reviewer","kind":"review_changes_requested","task_id":"T-01","body":"{\"summary\":\"Docs and implementation disagree on whether initial dispatch counts as a retry.\",\"changes\":[\"Update docs or implementation so initial dispatch counting is unambiguous.\"],\"severity\":\"high\"}"}' --json
```

State transitions:

- approval: same task `phase=done`
- approval with tester requirement: same task requeues as `phase=testing`, `role=tester`
- changes within plan scope: `reviewing -> implementing`
- implementation should be reassigned: `reviewing -> validated-ready`
- plan or ownership issue: `reviewing -> planned`
- external decision needed: `reviewing -> blocked`

## Minimal Transfer Matrix

Execution loop minimum:

1. orchestrator -> implementer: assignment payload
2. implementer -> orchestrator: mailbox `result`, `blocked`, `question`, or `status`
3. orchestrator -> code-reviewer: review request payload
4. code-reviewer -> orchestrator: mailbox `review_approved` or `review_changes_requested`
5. orchestrator -> compliance-reviewer when required: compliance request payload
6. compliance-reviewer -> orchestrator: mailbox `review_approved` or `review_changes_requested`
7. orchestrator -> tester when required: `tester_input`
8. tester -> orchestrator: mailbox `result`, `blocked`, `question`, or `status`

## Planning Payload Contracts

`validate-role-transfer` recognizes planning payloads by `contract_type`.

### task_planner_input

```json
{
  "contract_type": "task_planner_input",
  "task_id": "T-01",
  "source_role": "orchestrator",
  "target_role": "task-planner",
  "task": {
    "subject": "Add readiness validator",
    "description": "Turn the readiness gate into a CLI validator."
  },
  "source_document_paths": [
    "docs/execution/task-readiness-gate.md"
  ],
  "scope_paths": [
    "crates/moondex/src/fs_state.rs",
    "crates/moondex/src/cli.rs"
  ],
  "planning_requirements": [
    "produce one executor-ready plan",
    "include ownership and verification commands"
  ],
  "output_contract": "docs/contracts/plan-schema.md"
}
```

### task_planner_output

```json
{
  "contract_type": "task_planner_output",
  "task_id": "T-01",
  "plan_id": "P-01",
  "source_role": "task-planner",
  "target_role": "orchestrator",
  "status": "DONE",
  "plan_path": "docs/plans/P-01.md",
  "ownership": [
    "crates/moondex/src/fs_state.rs"
  ],
  "acceptance_criteria": [
    "valid payload returns READY"
  ],
  "verification_commands": [
    "cargo test -p moondex"
  ]
}
```

For `status: "BLOCKED"`, include `blocked_reason`. For `status: "NEEDS_CONTEXT"`, include `needs`.

### wave_dispatcher_input

```json
{
  "contract_type": "wave_dispatcher_input",
  "source_role": "orchestrator",
  "target_role": "wave-dispatcher",
  "candidate_tasks": [
    "T-01",
    "T-02"
  ],
  "plans": [
    {
      "task_id": "T-01",
      "plan_id": "P-01",
      "plan_path": "docs/plans/P-01.md"
    },
    {
      "task_id": "T-02",
      "plan_id": "P-02",
      "plan_path": "docs/plans/P-02.md"
    }
  ],
  "dependency_notes": [
    "T-02 depends on T-01 public contract"
  ],
  "ownership_conflicts": [],
  "shared_contract_candidates": [
    "crates/moondex/src/model.rs"
  ],
  "parallel_safety_note": "T-02 waits until T-01 model contract is stable.",
  "output_contract": "docs/contracts/wave-schema.md"
}
```

### wave_dispatcher_output

```json
{
  "contract_type": "wave_dispatcher_output",
  "wave_id": "W-01",
  "source_role": "wave-dispatcher",
  "target_role": "orchestrator",
  "status": "APPROVED",
  "wave_groups": [
    {
      "group_id": "G-01",
      "tasks": [
        "T-01"
      ]
    }
  ],
  "dependency_graph": [
    {
      "task_id": "T-01",
      "depends_on": []
    }
  ],
  "verification_plan": [
    "cargo test -p moondex"
  ],
  "validated_ready_tasks": [
    "T-01"
  ]
}
```

For `status: "REVISION_REQUIRED"`, include `revision_requests`. For `status: "BLOCKED"`, include `blocked_reason`.

## Tester Contract

Tester is a canonical execution role for integration and E2E validation only. Dispatch tester when integration/E2E execution is required, cross-flow regression must be verified, environment-specific behavior matters, reviewer asks for independent test evidence, or the task changes onboarding, persistence, routing, auth, external IO, or user-critical flows.

Tester can be skipped only when unit tests cover the change, no integration boundary changed, no cross-flow behavior changed, and code-reviewer does not request independent testing.

Tester input:

```json
{
  "contract_type": "tester_input",
  "task_id": "T-01",
  "plan_id": "P-01",
  "source_role": "orchestrator",
  "target_role": "tester",
  "test_scope": "integration reset flow",
  "changed_files": [
    "integration_test/reset_flow_test.dart"
  ],
  "verification_commands": [
    "flutter test integration_test/reset_flow_test.dart"
  ],
  "acceptance_criteria": [
    "reset flow returns user to onboarding"
  ],
  "environment_notes": [
    "requires simulator or device"
  ]
}
```

Tester output uses mailbox `result`, `blocked`, `question`, or `status`. Reviewer-only kinds are rejected for canonical tester output.

## Next Work

- Decide whether to add JSON Schema files in addition to the Rust runtime checker.
- Expand native lifecycle hook discovery if Codex exposes a stable hook loading contract.
