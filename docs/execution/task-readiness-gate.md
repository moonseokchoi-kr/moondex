# Readiness Gate

이 문서는 Codex planning 단계가 생성한 task, plan, wave가 실행 단계로 넘어갈 수 있는지 판정하는 기준이다.

목표는 단순하다.

- 실행 가능한 산출물만 통과시킨다
- planning 보완이 필요한 산출물은 실행 전에 걸러낸다

## Gate Decision

판정은 세 가지 중 하나다.

- `READY`: execution 단계로 전달 가능
- `REVISION_REQUIRED`: planning 산출물 보완 후 재검토
- `BLOCKED`: 상위 입력 문서가 부족하거나 선행 결정이 없어 실행 불가

자동 검증 entrypoint:

```bash
moondex api validate-readiness --input '<json>' --json
.codex/hooks/validate-readiness.sh '<json>'
```

Hook은 `READY`일 때만 `0`으로 종료한다. `REVISION_REQUIRED`와 `BLOCKED`는 non-zero다.

입력 payload:

```json
{
  "task": {
    "task_id": "T-01",
    "subject": "Add readiness validator",
    "description": "Validate executor readiness before dispatch."
  },
  "plan": {
    "plan_id": "P-01",
    "task_id": "T-01",
    "objective": "Implement readiness validator.",
    "scope_paths": [
      "crates/moondex/src/fs_state.rs"
    ],
    "acceptance_criteria": [
      "complete payload returns READY"
    ],
    "verification_commands": [
      "cargo test -p moondex"
    ],
    "ownership": [
      "crates/moondex/src/fs_state.rs"
    ]
  },
  "wave": {
    "wave_id": "W-01",
    "validated_ready_tasks": [
      "T-01"
    ],
    "dependency_graph": [
      {
        "task_id": "T-01",
        "depends_on": []
      }
    ],
    "verification_plan": [
      "cargo test -p moondex"
    ]
  }
}
```

출력 payload:

```json
{
  "decision": "READY",
  "errors": [],
  "warnings": [],
  "missing_fields": []
}
```

## Gate Checklist

## 1. Task Clarity

질문:

- 각 task의 단일 목표가 분명한가
- 범위 밖 항목이 명시돼 있는가
- task 간 경계가 보이는가

실패 시:

- `REVISION_REQUIRED`

## 2. Dependency Clarity

질문:

- 선행 task가 명시돼 있는가
- 아직 끝나지 않은 전제가 있으면 blocked 조건으로 적혀 있는가

실패 시:

- `BLOCKED`

## 3. Plan Completeness

질문:

- 각 task에 executor-ready plan이 있는가
- ownership, contracts, tests, verification이 plan에 있는가

실패 시:

- `REVISION_REQUIRED`

## 4. Parallel Safety

질문:

- wave에 병렬 가능 여부가 적혀 있는가
- 충돌 대상이나 충돌 조건이 적혀 있는가

실패 시:

- `REVISION_REQUIRED`

## 5. Wave Completeness

질문:

- wave에 dependency graph가 있는가
- ownership map이 있는가
- verification plan이 있는가

실패 시:

- `REVISION_REQUIRED`

wave가 제공된 경우 `dependency_graph`가 payload에 없는 task를 참조하면 `BLOCKED`다.

## 6. Executor Independence

최종 질문:

- executor가 추가 설계나 범위 결정을 하지 않고 바로 구현 가능한가

실패 시:

- `REVISION_REQUIRED`

## Block Examples

### READY

- task 경계가 명확하다
- 각 task에 대응하는 plan이 있다
- wave에 순서와 검증 계획이 있다

### REVISION_REQUIRED

- task는 있는데 plan이 비어 있다
- 공용 타입 수정 가능성이 있는데 ownership이 없다
- wave는 있는데 병렬화 근거가 없다

### BLOCKED

- 선행 API 계약이 아직 확정되지 않았다
- 다른 task 완료 없이는 시작할 수 없다
- 데이터 모델 결정이 비어 있다

## Recommended Workflow

1. planning 산출물(task set + plan set + wave)을 schema 기준으로 읽는다
2. 각 항목을 gate checklist로 판정한다
3. READY가 아니면 부족한 항목을 명시적으로 반환한다
4. READY인 산출물만 execution 단계로 전달한다
