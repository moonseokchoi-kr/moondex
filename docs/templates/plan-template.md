# Plan Template

이 템플릿은 Codex planning 단계가 task 하나를 executor-ready 수준으로 상세화할 때 사용하는 기준 형식이다.

```yaml
plan_id: P-T01
task_id: T-01
status: ready
priority: medium
owner_role: implementer
```

## Goal

- task 목표를 구현 관점으로 다시 서술:
- 이번 plan의 완료 기준 요약:

## Non-Goals

- 이번 plan에서 하지 않을 일:
- 다른 task/plan으로 넘길 일:

## Ownership

```yaml
ownership:
  allow:
    - path/to/owned/module/
  deny:
    - path/to/protected/module/
  shared_contract_change: false
```

## Inputs And Outputs

### Inputs

- 입력 데이터 또는 호출 계약:

### Outputs

- 출력 데이터 또는 상태 변화:

### Error Conditions

- 실패 조건:

## Implementation Notes

- 사용해야 하는 기존 모듈 또는 인터페이스:
- 금지 패턴:
- 성능/보안/호환성 제약:

## Execution Steps

### Step 1

- 대상 파일/모듈:
- 할 일:
- 이 순서인 이유:
- 완료 기준:

### Step 2

- 대상 파일/모듈:
- 할 일:
- 이 순서인 이유:
- 완료 기준:

### Step 3

- 대상 파일/모듈:
- 할 일:
- 이 순서인 이유:
- 완료 기준:

## Checkpoints And Fallbacks

- Checkpoint 1:
- Checkpoint 2:
- blocked 조건:
- fallback/rollback:

## Acceptance Criteria

### Happy Path

- [ ] 검증 가능한 완료 조건 1

### Edge Cases

- [ ] 경계 조건 1

### Failure Cases

- [ ] 실패 조건 1

## Test Requirements

```yaml
tests:
  required:
    - unit
  scenarios:
    - replace with concrete scenario
  regression_risks:
    - replace with concrete regression risk
```

## Verification Commands

### Minimum

```bash
# replace with focused verification command
```

### Full

```bash
# replace with broader verification command
```

## Integration Notes

- merge order:
- rollout risks:
- follow-up handoff:

## Planner Notes

- ownership 판단 근거:
- step 분해 근거:
- 검증 전략 근거:
