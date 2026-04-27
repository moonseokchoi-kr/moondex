# Wave Template

이 템플릿은 Codex planning 단계가 여러 task/plan을 오케스트레이션 가능한 단위로 묶을 때 사용하는 기준 형식이다.

```yaml
wave_plan_id: WAVE-001
feature_name: replace-with-feature-name
source_documents:
  spec: path/to/spec.md
  design_set:
    - path/to/arch.md
    - path/to/ui.md
    - path/to/api.md
  implementation_design_set:
    - path/to/context.md
    - path/to/implementation-notes.md
planning_date: YYYY-MM-DD
```

## Planning Summary

- 전체 구현 전략:
- 코드베이스에서 확인한 핵심 제약:
- 계획의 주요 가정:

## Task And Plan List

| Task | Plan | Goal Summary | Owner Role | Priority |
|------|------|--------------|------------|----------|
| T-01 | P-T01 | replace with summary | implementer | medium |

## Dependency Graph

```text
T-01 -> T-03
T-02 -> T-03
```

### Blocked Conditions

- T-03 blocked until:

## Wave Groups

- Wave 1: T-01/P-T01, T-02/P-T02
- Wave 2: T-03/P-T03

## Ownership Map

| Task | Allow | Deny | Shared Contract Change |
|------|-------|------|------------------------|
| T-01 | `path/a` | `path/b` | false |

## Verification Plan

### Task-Level Verification

- T-01:

### Wave-Level Verification

- Wave 1:

### Final Integration Verification

- 전체 통합 검증:

## Risk Notes

- 충돌 위험:
- shared contract 위험:
- 테스트 누락 위험:
- 후속 조치:

## Planner Notes

- wave 구성 기준:
- 병렬화 판단 기준:
- merge 순서:
