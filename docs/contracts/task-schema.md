# Task Schema

이 문서는 Codex planning 단계가 생성하는 `task`의 최소 계약을 정의한다.

task는 상위 작업 단위다. 아직 실행 상세를 모두 담지 않는다.

핵심 원칙:

- task는 "무슨 일을 해야 하는가"를 정의한다
- task는 너무 거칠면 안 되지만, executor-ready 상세 계획까지 떠안지도 않는다
- 상세 구현 판단은 별도의 `plan` 문서로 내려간다

## Required Sections

### 1. Task Metadata

- `task_id`
- `title`
- `status`
- `priority`
- `owner_role`

예시:

```yaml
task_id: T-03
title: add retry scheduling
status: draft
priority: high
owner_role: implementer
```

## 2. Goal

이 task가 해결해야 하는 단일 목표를 명시한다.

필수:

- 무엇을 바꾸는지
- 어떤 사용자/시스템 효과를 기대하는지

## 3. Non-Goals

이 task에서 하지 않는 일을 명시한다.

필수:

- 범위 밖 변경
- 후속 task로 넘길 일

## 4. Dependencies

선행 task와 필요한 전제 조건을 명시한다.

필수:

- 선행 task IDs
- blocked 조건

## 5. Scope Notes

필수:

- 대상 모듈 또는 레이어
- 예상 변경 영역
- 이 task를 별도로 분리한 이유

## 6. Success Conditions

필수:

- 이 task가 끝났다고 볼 최소 조건
- 이 task가 다른 task에 넘겨야 할 산출물

## Good Task Definition

좋은 task는 아래를 만족한다.

- 단일 목표가 있다
- 다른 task와의 경계가 있다
- dependency가 보인다
- 이후 별도 `plan`으로 상세화할 수 있다

## Bad Task Signals

- 하나의 task가 여러 독립 기능을 함께 담는다
- 성공 조건이 모호하다
- 다른 task와 경계가 없다
- ownership이나 검증이 task 수준에서 완전히 불명확하다
