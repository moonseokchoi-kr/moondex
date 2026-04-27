# Orchestration Simulation

이 문서는 `money-track-app-bootstrap-theme` 예시를 기준으로 현재 하네스의 상태 머신과 역할 체인이 실제로 어떻게 동작하는지 end-to-end로 시뮬레이션한 샘플이다.

목표는 세 가지다.

1. `task -> plan -> wave -> execution`이 실제로 굴러가는지 확인한다.
2. `validated-ready`, `implementing`, `reviewing`의 차이를 예시로 고정한다.
3. mandatory `code-reviewer`, conditional `compliance-reviewer`, optional `tester`가 언제 붙는지 보여준다.

## Scope

이 시뮬레이션은 아래 예시 산출물을 입력으로 본다.

- [task-set.md](/Users/moon/Workspace/codex-moon-harness/docs/examples/money-track-app-bootstrap-theme/task-set.md)
- [plan-set.md](/Users/moon/Workspace/codex-moon-harness/docs/examples/money-track-app-bootstrap-theme/plan-set.md)
- [wave-plan.md](/Users/moon/Workspace/codex-moon-harness/docs/examples/money-track-app-bootstrap-theme/wave-plan.md)

기본 가정:

- planner layer는 이미 source documents를 읽고 task/plan/wave를 만들었다.
- implementer는 task 범위 안에서 unit-level TDD를 기본 규칙으로 따른다.
- `code-reviewer`는 모든 task에 대해 mandatory pass다.
- `compliance-reviewer`는 요구사항 단순성, 범위, shared contract 영향에 따라 조건부로 붙는다.
- `tester`는 integration test 또는 E2E 작성/실행이 필요할 때만 붙는다.

## Role Expectations By Task

| Task | Wave | Compliance Reviewer | Tester | Reason |
|------|------|---------------------|--------|--------|
| T-01 | Wave 1 | yes | no | bootstrap, DB seeding, startup contract 변경 |
| T-02 | Wave 2 | yes | no | theme contract와 app entry wiring 변경 |
| T-03 | Wave 3 | no | no | 요구사항이 단순하고 mapping 범위가 명확함 |
| T-04 | Wave 4 | yes | no | 사용자 가시 home redesign, CTA/spec 정합성 중요 |
| T-05 | Wave 4 | yes | yes | pagination/date grouping과 integration 검증 필요 |
| T-07 | Wave 4 | yes | yes | onboarding gate와 cycle 생성 흐름 검증 필요 |
| T-08 | Wave 4 | no | yes | CRUD 요구사항은 비교적 단순하지만 E2E 검증 가치가 있음 |
| T-09 | Wave 4 | yes | yes | reset/onboarding semantics와 settings contract 영향 |
| T-06 | Wave 5 | yes | yes | quick expense 3-step flow와 home invalidation coupling |
| T-10 | Wave 6 | no | yes | 신규 product scope가 아니라 regression/E2E 중심 |

## Phase 1. Initial Task Queue

메인 오케스트레이터는 source documents를 읽고 아래 task를 모두 `draft`로 만든다.

| Task | Initial Status | Owner | Notes |
|------|----------------|-------|-------|
| T-01 ~ T-10 | `draft` | none | 아직 planner lease 없음 |

이 단계에서 중요한 점:

- task는 존재하지만 아무도 점유하지 않는다.
- 아직 implementer를 붙일 수 없다.
- `draft`는 planning queue 상태다.

## Phase 2. Planning Pool

메인 오케스트레이터는 `task-planner` pool에 task를 넘긴다.

샘플 시나리오:

| Task | Planner | Transition |
|------|---------|------------|
| T-01 | planner-A | `draft -> planning -> planned` |
| T-02 | planner-B | `draft -> planning -> planned` |
| T-03 | planner-C | `draft -> planning -> planned` |
| T-04 | planner-D | `draft -> planning -> planned` |
| T-05 | planner-E | `draft -> planning -> planned` |
| T-06 | planner-F | `draft -> planning -> planned` |
| T-07 | planner-G | `draft -> planning -> planned` |
| T-08 | planner-H | `draft -> planning -> planned` |
| T-09 | planner-I | `draft -> planning -> planned` |
| T-10 | planner-J | `draft -> planning -> planned` |

오케스트레이터는 각 plan을 읽고 quality gate를 통과한 항목만 `wave-ready`로 올린다.

| Task | After Plan Review |
|------|-------------------|
| T-01 ~ T-10 | `planned -> wave-ready` |

이 단계에서 아직 구현은 시작되지 않는다.

- `planned`는 executor-ready plan이 생겼다는 뜻이다.
- `wave-ready`는 전역 병렬성 판단을 기다리는 상태다.

## Phase 3. Wave Dispatch

메인 오케스트레이터는 `wave-ready` plan set을 `wave-dispatcher`에 전달한다.

`wave-dispatcher`는 [wave-plan.md](/Users/moon/Workspace/codex-moon-harness/docs/examples/money-track-app-bootstrap-theme/wave-plan.md)의 6개 wave를 확정한다.

결과:

- Wave 1: T-01
- Wave 2: T-02
- Wave 3: T-03
- Wave 4: T-04, T-05, T-07, T-08, T-09
- Wave 5: T-06
- Wave 6: T-10

`wave-dispatcher` 승인 후 각 task는 실행 가능한 순서에 따라 `validated-ready`로 올라간다.

핵심 의미:

- `validated-ready`는 implementer queue다.
- implementer capacity가 없으면 이 상태에서 대기한다.
- 이 상태는 blocked가 아니다.

## Phase 4. Wave 1 Execution

### T-01 Database Bootstrap

1. `wave-ready -> validated-ready`
2. implementer-1 배정: `validated-ready -> implementing`
3. implementer-1은 unit-level TDD로 initializer와 provider wiring을 작업한다
4. 구현 완료: `implementing -> reviewing`
5. `code-reviewer` pass
6. `compliance-reviewer` pass
7. 승인: `reviewing -> done`

여기서 `compliance-reviewer`가 필요한 이유:

- startup contract가 바뀐다
- DB seed semantics가 spec 수준 요구사항이다
- shared contract 영향이 있다

## Phase 5. Wave 2 Execution

### T-02 Global Theme Infrastructure

1. T-01 완료 후 `validated-ready`
2. implementer-2 배정
3. theme token 정리와 app wiring 수행
4. `code-reviewer` pass
5. `compliance-reviewer` pass
6. `done`

이 task는 사용자 가시 디자인 계약을 직접 만지므로 `compliance-reviewer`를 생략하지 않는다.

## Phase 6. Wave 3 Execution

### T-03 Shared Category Visual Mapping

1. `validated-ready`
2. implementer-3 배정
3. mapping module과 fallback 작성
4. `code-reviewer` pass
5. `done`

이 task에서 `compliance-reviewer`를 생략한 이유:

- 요구사항이 단순하다
- 변경 범위가 `lib/core/category/`로 좁다
- default 16 category mapping과 fallback이라는 계약이 명확하다
- `code-reviewer`가 범위 일탈과 규칙 위반 가능성이 낮다고 판단했다

이 예시는 "아주 단순한 요구사항에서는 code review가 compliance 역할까지 커버할 수 있다"는 현재 규칙을 보여준다.

## Phase 7. Wave 4 Parallel Execution

Wave 4에서는 다섯 task가 동시에 `validated-ready`가 된다.

| Task | Implementer | Initial Status |
|------|-------------|----------------|
| T-04 | implementer-4 | `validated-ready -> implementing` |
| T-05 | implementer-5 | `validated-ready -> implementing` |
| T-07 | implementer-6 | `validated-ready -> implementing` |
| T-08 | implementer-7 | `validated-ready -> implementing` |
| T-09 | implementer-8 | `validated-ready -> implementing` |

### T-04 Home Screen Redesign

- 구현 후 `code-reviewer` pass
- home CTA와 banner semantics가 spec/UI와 직접 연결되므로 `compliance-reviewer` 추가
- 승인 후 `done`

### T-05 Transactions Screen With Pagination

이 task는 재작업 루프를 한 번 거치는 예시로 둔다.

1. implementer-5가 첫 구현 완료
2. `code-reviewer`가 pagination이 DB-level이 아니라 in-memory sublist shortcut으로 구현된 흔적을 발견
3. 상태 전이: `reviewing -> implementing`
4. implementer-5가 repository paging을 수정하고 테스트 보강
5. 다시 `code-reviewer` pass 통과
6. pagination/date grouping은 요구사항 해석 여지가 있으므로 `compliance-reviewer` 추가
7. integration test가 필요하므로 tester가 scroll load / filter path를 검증
8. 최종 `done`

이 예시가 보여주는 점:

- 대부분의 review 피드백은 `blocked`가 아니다
- 같은 implementer가 바로 수정하면 `implementing` 재진입이 자연스럽다
- tester는 integration 검증이 필요한 시점에만 붙는다

### T-07 Onboarding Flow Redesign

- onboarding gate와 cycle 생성은 app semantics를 바꾸므로 `compliance-reviewer` 필수
- first-run flow는 integration 성격이 강하므로 tester 추가
- 최종 `done`

### T-08 Category Management Screen

- CRUD 요구사항 자체는 비교적 단순하므로 `code-reviewer`만으로 review 종료 가능
- 다만 add/edit/delete flow는 E2E 검증 가치가 있어 tester 추가
- 최종 `done`

### T-09 Settings Screen Redesign

- reset data -> onboarding reset은 shared semantics를 건드린다
- `code-reviewer` 후 `compliance-reviewer` 추가
- settings flow와 reset path 때문에 tester 추가
- 최종 `done`

## Phase 8. Wave 5 Execution

### T-06 Quick Expense 3-Step Modal

Wave 5는 home CTA contract에 직접 의존하므로 직렬로 진행한다.

1. T-04 완료 후 `validated-ready`
2. implementer-9 배정
3. amount -> category -> confirmation flow와 save 후 invalidation 구현
4. `code-reviewer` pass
5. `compliance-reviewer` pass
6. tester가 modal flow와 home refresh를 검증
7. `done`

이 task는 UI flow도 사용자 가시고, home coupling도 있어서 `compliance-reviewer`를 생략하지 않는다.

## Phase 9. Wave 6 Execution

### T-10 E2E Validation And Polish

이 task는 product behavior를 새로 설계하는 작업이 아니라 통합 검증과 polish다.

1. `validated-ready`
2. implementer-10 또는 dedicated test owner가 finder update와 final polish를 수행
3. `code-reviewer`가 regression report와 touched files를 검토
4. tester가 integration/E2E suite를 실행
5. `done`

이 task에서 `compliance-reviewer`를 생략한 이유:

- 신규 feature 요구사항 추가가 아니다
- 주된 산출물은 regression confidence와 test status다
- 범위 일탈만 없다면 code review로 충분하다

## End State Snapshot

| Task | Final Status | Review Path | Tester |
|------|--------------|-------------|--------|
| T-01 | `done` | code -> compliance | no |
| T-02 | `done` | code -> compliance | no |
| T-03 | `done` | code only | no |
| T-04 | `done` | code -> compliance | no |
| T-05 | `done` | code -> rework -> code -> compliance | yes |
| T-06 | `done` | code -> compliance | yes |
| T-07 | `done` | code -> compliance | yes |
| T-08 | `done` | code only | yes |
| T-09 | `done` | code -> compliance | yes |
| T-10 | `done` | code only | yes |

## What This Simulation Validates

- `validated-ready`는 구현 가능하지만 아직 미배정이거나 재배정 가능한 queue 상태다.
- `implementing`은 implementer lease가 살아 있는 active execution 상태다.
- `reviewing`은 단일 reviewer 상태가 아니라 review phase다.
- `code-reviewer`는 모든 task에 대해 mandatory pass다.
- `compliance-reviewer`는 요구사항 복잡도와 contract 영향에 따라 조건부로 붙는다.
- `tester`는 integration/E2E가 필요할 때만 붙는다.
- review 피드백 대부분은 `blocked`가 아니라 `implementing` 재진입으로 처리된다.

## Follow-Up

이 문서를 더 엄밀하게 만들고 싶다면 다음 중 하나로 이어지면 된다.

1. 각 phase의 role transfer contract를 payload 수준으로 적는다.
2. `compliance_review_required` 판단 체크리스트를 별도 표로 뽑는다.
3. `cmux` pane/surface 배치까지 포함한 운영 시뮬레이션으로 확장한다.
