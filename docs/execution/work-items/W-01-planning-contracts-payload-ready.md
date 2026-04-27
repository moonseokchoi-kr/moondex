# W-01 Planning Contracts Payload-Ready

이 문서는 `docs/execution/WORK_TRACKER.md`의 `W-01` 구현을 위한 executor-ready 계획이다.

## Goal

`task-planner`와 `wave-dispatcher` 계약을 문서 설명 수준에서 실제 JSON payload 예시와 `validate-role-transfer` 검증 대상으로 내린다.

완료 후 아래 네 종류의 planning payload가 문서와 hook validator에서 모두 다뤄져야 한다.

- orchestrator -> `task-planner`
- `task-planner` -> orchestrator
- orchestrator -> `wave-dispatcher`
- `wave-dispatcher` -> orchestrator

## Scope

수정 대상:

- `docs/execution/role-transfer-contracts.md`
- `docs/execution/WORK_TRACKER.md`
- `docs/system-ext/HANDOFF.md`
- `crates/moondex/src/fs_state.rs`

필요하면 수정:

- `docs/execution/moondex-cli-plan.md`
- `.codex/hooks/role-transfer-contract.md`

비범위:

- `validate-readiness` 추가
- orchestrator flow 자동 연결
- lifecycle hook warning 저장
- compliance-reviewer 정책 심화
- tester contract 추가

## Contract Type Dispatch

`validate-role-transfer`는 다음 순서로 payload를 판별한다.

1. `contract_type`이 있으면 planning contract validator를 사용한다.
2. `contract_type`이 없고 `from_role`, `kind`, `body` 중 하나가 있으면 mailbox output validator를 사용한다.
3. 그 외에는 기존 generic handoff payload validator를 사용한다.

알 수 없는 `contract_type`은 hard fail이다.

## Planning Contract Payloads

### task_planner_input

Purpose:

- orchestrator가 draft 또는 planning 대상 task 하나를 `task-planner`에게 넘긴다.

Required fields:

- `contract_type: "task_planner_input"`
- `task_id`
- `source_role: "orchestrator"`
- `target_role: "task-planner"`
- `task`
- `source_document_paths`
- `scope_paths`
- `planning_requirements`
- `output_contract`

Valid example:

```json
{
  "contract_type": "task_planner_input",
  "task_id": "T-01",
  "source_role": "orchestrator",
  "target_role": "task-planner",
  "task": {
    "subject": "Add retry limit",
    "description": "Limit retry-dispatch attempts and document behavior."
  },
  "source_document_paths": [
    "docs/execution/moondex-cli-plan.md"
  ],
  "scope_paths": [
    "crates/moondex/src/fs_state.rs"
  ],
  "planning_requirements": [
    "produce one executor-ready plan",
    "include ownership and verification commands"
  ],
  "output_contract": "docs/contracts/plan-schema.md"
}
```

### task_planner_output

Purpose:

- `task-planner`가 task 하나에 대한 executor-ready plan 결과를 orchestrator에게 반환한다.

Required fields:

- `contract_type: "task_planner_output"`
- `task_id`
- `plan_id`
- `source_role: "task-planner"`
- `target_role: "orchestrator"`
- `status: "DONE" | "NEEDS_CONTEXT" | "BLOCKED"`
- `ownership`
- `acceptance_criteria`
- `verification_commands`

Conditional fields:

- `status: "DONE"`이면 `plan_path` 또는 `plan` 필요
- `status: "BLOCKED"`이면 `blocked_reason` 필요
- `status: "NEEDS_CONTEXT"`이면 `needs` 필요

Valid example:

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
    "retry attempts are capped"
  ],
  "verification_commands": [
    "cargo test -p moondex"
  ]
}
```

### wave_dispatcher_input

Purpose:

- orchestrator가 plan set을 `wave-dispatcher`에게 넘겨 dependency와 병렬 실행 가능성을 확정하게 한다.

Required fields:

- `contract_type: "wave_dispatcher_input"`
- `source_role: "orchestrator"`
- `target_role: "wave-dispatcher"`
- `candidate_tasks`
- `plans`
- `dependency_notes`
- `ownership_conflicts`
- `shared_contract_candidates`
- `output_contract`

Valid example:

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
  "output_contract": "docs/contracts/wave-schema.md"
}
```

### wave_dispatcher_output

Purpose:

- `wave-dispatcher`가 실행 가능한 wave grouping과 validated-ready task 목록을 반환한다.

Required fields:

- `contract_type: "wave_dispatcher_output"`
- `wave_id`
- `source_role: "wave-dispatcher"`
- `target_role: "orchestrator"`
- `status: "APPROVED" | "REVISION_REQUIRED" | "BLOCKED"`
- `wave_groups`
- `dependency_graph`
- `verification_plan`

Conditional fields:

- `status: "APPROVED"`이면 `validated_ready_tasks`가 non-empty여야 한다.
- `status: "REVISION_REQUIRED"`이면 `revision_requests`가 필요하다.
- `status: "BLOCKED"`이면 `blocked_reason`이 필요하다.

Valid example:

```json
{
  "contract_type": "wave_dispatcher_output",
  "wave_id": "W-01",
  "source_role": "wave-dispatcher",
  "target_role": "orchestrator",
  "status": "APPROVED",
  "wave_groups": [
    {
      "group_id": "W-01-G1",
      "task_ids": [
        "T-01"
      ],
      "parallel": false
    }
  ],
  "dependency_graph": [
    {
      "task_id": "T-01",
      "depends_on": []
    }
  ],
  "validated_ready_tasks": [
    "T-01"
  ],
  "verification_plan": [
    "cargo test -p moondex"
  ]
}
```

## Validator Rules

Hard failures:

- unknown `contract_type`
- missing required field
- invalid status enum
- `task_planner_output` with `DONE` but no `plan_path` or `plan`
- `task_planner_output` with `BLOCKED` but no `blocked_reason`
- `task_planner_output` with `NEEDS_CONTEXT` but no `needs`
- `wave_dispatcher_output` with `APPROVED` but empty or missing `validated_ready_tasks`
- `wave_dispatcher_output` with `REVISION_REQUIRED` but no `revision_requests`
- `wave_dispatcher_output` with `BLOCKED` but no `blocked_reason`
- missing `verification_commands` or `verification_plan` where required

Warnings:

- `scope_paths` is empty
- `verification_commands` looks too weak
- `ownership` is present but too abstract
- `candidate_tasks` has more than one task and `dependency_notes` is empty
- `ownership_conflicts` is non-empty but no serial/dependency note explains it

## Implementation Steps

1. Extend `role-transfer-contracts.md` with the four planning contract sections and examples above.
2. Add `contract_type` dispatch to `validate_role_transfer_payload`.
3. Add private validators:
   - `validate_task_planner_input`
   - `validate_task_planner_output`
   - `validate_wave_dispatcher_input`
   - `validate_wave_dispatcher_output`
4. Reuse existing helper style for `required_string` and required array checks.
5. Add unit tests for valid and invalid planning payloads.
6. Run hook smoke with at least one valid planning payload and one invalid planning payload.
7. Mark W-01 as `done` in `WORK_TRACKER.md` and add a completion note.
8. Update HANDOFF to remove or complete the planning contract payload-ready gap.

## Tests

Required unit tests:

- valid `task_planner_input` passes
- valid `task_planner_output` with `DONE` passes
- `task_planner_output` with `DONE` but no `plan_path` or `plan` fails
- `task_planner_output` with `BLOCKED` but no `blocked_reason` fails
- valid `wave_dispatcher_input` passes
- valid `wave_dispatcher_output` with `APPROVED` passes
- `wave_dispatcher_output` with `APPROVED` and empty `validated_ready_tasks` fails
- unknown `contract_type` fails

Required commands:

```bash
cargo fmt --check
cargo test -p moondex
cargo build -p moondex
.codex/hooks/validate-role-transfer.sh '<valid-task-planner-input-json>'
.codex/hooks/validate-role-transfer.sh '<invalid-task-planner-output-json>'
```

Expected hook behavior:

- valid payload exits `0`
- invalid payload exits non-zero
- warning-only payload exits `0`

