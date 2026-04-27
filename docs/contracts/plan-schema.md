# Plan Schema

이 문서는 Codex planning 단계가 생성하는 `plan`의 최소 계약을 정의한다.

plan은 개별 task 하나를 실제로 어떻게 수행할지 적는 executor-ready 문서다.

핵심 원칙:

- plan은 executor가 추가 설계 없이 구현을 시작할 수 있어야 한다
- task가 "무엇"이라면 plan은 "어떻게"다
- task 하나당 plan 하나를 기본으로 한다
- 좋은 plan은 `plan mode`처럼 단계별 실행 순서와 체크포인트가 보여야 한다

## Required Sections

### 1. Plan Metadata

- `plan_id`
- `task_id`
- `status`
- `priority`
- `owner_role`

예시:

```yaml
plan_id: P-T03
task_id: T-03
status: ready
priority: high
owner_role: implementer
```

## 2. Goal

필수:

- task 목표를 구현 관점으로 다시 서술
- 이번 plan의 완료 기준 요약

## 3. Non-Goals

필수:

- 이 plan에서 하지 않을 일
- 다른 task/plan으로 넘길 일

## 4. Ownership

필수:

- 수정 허용 경로
- 수정 금지 경로
- 공유 계약 변경 여부

## 5. Inputs And Outputs

필수:

- 입력 데이터 또는 호출 계약
- 출력 데이터 또는 상태 변화
- 에러 조건

## 6. Implementation Notes

필수:

- 사용해야 하는 기존 모듈 또는 인터페이스
- 금지 패턴
- 성능/보안/호환성 제약

## 7. Execution Steps

필수:

- Step 1, 2, 3... 형태의 순차 실행 계획
- 각 step의 대상 파일 또는 모듈
- 각 step를 그 순서로 두는 이유
- 각 step 완료 기준

좋은 step 예:

- Step 1: provider data shape 고정 (`lib/features/home/application/home_provider.dart`)
- Step 2: screen skeleton 구성 (`lib/features/home/presentation/screens/home_screen.dart`)
- Step 3: hero/grid/banner widget 분리 및 연결

## 8. Checkpoints And Fallbacks

필수:

- 중간 검증 체크포인트
- blocked 조건
- fallback 또는 rollback 전략

## 9. Acceptance Criteria

필수:

- 정상 시나리오
- 경계 시나리오
- 실패 시나리오

## 10. Test Requirements

필수:

- 필요한 테스트 종류
- 반드시 포함할 시나리오
- 회귀 위험 포인트

## 11. Verification Commands

필수:

- 최소 검증 명령어
- 전체 검증 명령어

## 12. Integration Notes

필수:

- merge order
- rollout risks
- follow-up handoff notes

## Ready Definition

아래를 모두 만족해야 `executor-ready` plan으로 본다.

- ownership이 명시돼 있다
- 입력/출력 계약이 있다
- 단계별 실행 순서가 있다
- 체크포인트와 blocked 조건이 있다
- acceptance criteria가 검증 가능하다
- test requirements와 verification commands가 있다
- executor가 추가 설계 없이 바로 구현 시작 가능하다

## Not Ready Signals

- "필요 시 조정" 같은 모호한 문구가 많다
- ownership이 파일 단위 또는 경로 단위로 특정되지 않는다
- step가 없거나 순서 이유가 없다
- 중간 체크포인트가 없다
- acceptance criteria가 바람 수준이다
- 테스트 요구사항이 없다
- shared contract 변경 여부가 빠져 있다
