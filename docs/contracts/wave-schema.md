# Wave Schema

이 문서는 Codex planning 단계가 생성하는 `wave` 문서의 최소 스키마를 정의한다.

wave는 여러 task/plan을 어떤 순서와 병렬성으로 실행할지 정의하는 오케스트레이션 단위다.

## Required Sections

### 1. Wave Metadata

- `wave_plan_id`
- `feature_name`
- `source_documents`
- `planning_date`

## 2. Planning Summary

필수:

- 전체 구현 전략 요약
- 코드베이스에서 확인한 핵심 제약
- 계획의 주요 가정

## 3. Task And Plan List

필수:

- 생성된 task 목록
- 각 task에 대응하는 plan ID
- 각 task의 owner role

## 4. Dependency Graph

필수:

- task 간 선행 관계
- blocked 조건
- wave 간 선행 관계

## 5. Wave Groups

필수:

- 각 wave에 포함되는 task/plan
- 병렬 실행 가능한 근거
- 직렬 실행이 필요한 이유

## 6. Ownership Map

필수:

- task별 소유 파일 또는 디렉터리
- 공유 계약 변경이 일어나는 지점
- 충돌 가능 영역

## 7. Verification Plan

필수:

- task 단위 검증
- wave 단위 검증
- 최종 통합 검증

## 8. Risk Notes

필수:

- 충돌 위험
- shared contract 위험
- 테스트 누락 위험
- 후속 조치 필요 사항

## Ready Definition

좋은 wave 문서는 아래를 만족한다.

- task와 plan을 어떤 순서로 돌릴지 보인다
- dependency와 ownership이 연결되어 있다
- 병렬화 근거가 명시돼 있다
- 검증 계획이 있다
- orchestrator가 추가 설계 없이 배정 가능한 수준이다
