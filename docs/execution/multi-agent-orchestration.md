# Multi-Agent Orchestration

이 문서는 `moondex`의 멀티에이전트 운영 시나리오를 정리하는 초안이다.

목표는 규칙을 섣불리 고정하는 것이 아니라, 실제 동작 흐름을 끝까지 그려보고 어디에 planner subagent가 필요하고 어디에 execution agent가 필요한지 판단하는 것이다.

현재 기준:

- 메인 오케스트레이터가 전체 상태를 가진다
- `task-planner`는 planning layer의 하위 agent다
- `wave-dispatcher`는 plan set 이후에 동작하는 전역 planning agent다
- implementer/`code-reviewer`/`compliance-reviewer`/tester는 execution layer다
- `cmux`는 Moondex runtime의 기본 운영 레이어다
- `spawn_agent` 같은 내부 서브에이전트 호출은 Moondex 본래 runtime 모델로 채택하지 않는다

## Questions To Resolve

이 문서는 아래 네 질문을 풀기 위한 작업 문서다.

1. task state machine은 어떻게 둘 것인가
2. 어떤 상태에서 어떤 역할을 dispatch할 것인가
3. agent 간 role transfer contract는 무엇으로 고정할 것인가
4. `cmux`는 어떤 수준까지 운영 레이어로 사용할 것인가

## 1. Task State Machine

현재 초안 상태값:

- `draft`
- `planning`
- `planned`
- `wave-ready`
- `validated-ready`
- `implementing`
- `reviewing`
- `done`
- `blocked`

### State Meaning

- `draft`
  task는 존재하지만 아직 planner가 점유하지 않았다.
- `planning`
  특정 `task-planner`가 task를 점유하고 plan을 작성 중이다.
- `planned`
  task 단위 plan은 생성됐지만 아직 전역 병렬성/충돌 검토 전이다.
- `wave-ready`
  plan 품질은 통과했고 `wave-dispatcher` 입력으로 올릴 수 있다.
- `validated-ready`
  wave 확정과 dependency 검토가 끝나 구현 가능 상태다. 아직 implementer가 task를 점유하지 않았거나, 다시 구현 큐로 되돌려 재배정 가능한 상태다.
- `implementing`
  implementer가 task를 점유하고 구현 중이다. 이 상태에서는 implementer lease가 살아 있고 다른 agent가 같은 task를 잡으면 안 된다.
- `reviewing`
  구현 완료 후 review phase에 들어간 상태다. 이 단계에서는 `code-reviewer`와 `compliance-reviewer`가 순차적으로 같은 task를 검토한다.
- `done`
  종료됐다.
- `blocked`
  planning 또는 execution 어디선가 멈췄다.

### State Transitions

- `draft -> planning`
  `task-planner` 할당
- `planning -> planned`
  plan 작성 완료
- `planning -> blocked`
  입력 부족, 충돌, ownership 판단 실패
- `planned -> wave-ready`
  메인 오케스트레이터가 plan 품질 확인
- `wave-ready -> validated-ready`
  `wave-dispatcher`가 dependency와 병렬성 검토 후 승인
- `validated-ready -> implementing`
  implementer 할당
- `implementing -> reviewing`
  구현 완료
- `implementing -> blocked`
  구현 blocker 발생
- `reviewing -> done`
  리뷰 통과
- `reviewing -> implementing`
  같은 plan 범위 안에서 구현 수정 후 다시 리뷰
- `reviewing -> validated-ready`
  수정 필요하지만 같은 implementer가 즉시 이어서 처리하지 않고 재배정 가능한 구현 큐로 복귀
- `reviewing -> planned`
  리뷰 결과가 plan 수정이나 ownership 재검토를 요구함
- `reviewing -> blocked`
  사용자 판단, 상위 설계 변경, 외부 의존성 등 외부 개입이 필요함
- `blocked -> planning`
  planning blocker 해소 후 재시도
- `blocked -> validated-ready`
  execution blocker 해소 후 재개

### Ownership Rule

같은 task는 한 시점에 한 owner만 가진다.

- `planning` 상태면 `task-planner` 하나만 점유
- `validated-ready` 상태면 active owner가 없다
- `implementing` 상태면 implementer 하나만 점유
- `reviewing` 상태면 현재 review pass를 수행 중인 reviewer 하나만 점유

즉 상태는 단순 추적값이 아니라 lock 역할도 한다.

Moondex runtime은 planning-level state와 별도로 `phase`를 둔다. 하나의 logical task는 같은 `task_id`를 유지하면서 `implementation -> code_review -> compliance_review/testing -> done`으로 이동한다. phase가 바뀌면 `role`은 현재 dispatchable role로 갱신된다.

Runtime phase transfer는 orchestrator가 mailbox output을 소비할 때 발생한다. implementer `result`를 소비하면 같은 task가 `code_review` phase와 `code-reviewer` role로 requeue된다. code-reviewer approval에서 `compliance_review_required: true`면 같은 task가 `compliance_review` phase로 넘어간다.

### Planner Pool Rule

`task-planner`는 여러 task에 대해 병렬로 돌 수 있다.

하지만 아래는 금지한다.

- 같은 task를 planner 두 개가 동시에 잡는 것
- `planning` 상태의 task를 다른 planner가 다시 가져가는 것

즉 `task-planner`는 parallelizable across tasks 이지만, task 내부에서는 단일 owner만 허용한다.

### Suggested Metadata

상태 머신을 운영하려면 task마다 최소 아래 필드가 필요하다.

- `status`
- `owner_role`
- `owner_agent_id`
- `lease_expires_at`
- `plan_id`
- `wave_id`
- `blocked_reason`
- `blocked_reason_type`
- `review_type`
- `review_pass_status`
- `updated_at`

특히 `owner_agent_id`와 `lease_expires_at`는 같은 task 중복 planning을 막고, 죽은 agent의 lease를 회수하는 데 필요하다.

### Notes

- task 수준의 병렬 가능 여부는 가설이다.
- 최종 병렬성은 `plan` 기준으로 다시 판단한다.
- 따라서 `planned`는 아직 구현 가능 상태가 아니다.
- execution 시작 조건은 항상 `validated-ready`다.
- `validated-ready`는 구현 blocked가 아니라 dispatchable queue 상태다.
- implementer가 모두 바쁘면 task는 자연스럽게 `validated-ready`에 머문다.
- 리뷰에서 나오는 대부분의 수정 요청은 `blocked`가 아니라 `implementing` 재진입으로 본다.

## 2. Role Selection And Dispatch

이 섹션은 다음 질문을 다룬다.

- 어떤 상태에서 `task-planner`를 붙이는가
- 어떤 상태에서 `wave-dispatcher`를 붙이는가
- 어떤 상태에서 implementer/`code-reviewer`/`compliance-reviewer`/tester를 붙이는가
- 항상 필요한 역할과 선택 역할은 무엇인가

기본 원칙:

- planning layer와 execution layer를 섞지 않는다
- 같은 task에 대해 planning과 execution을 동시에 붙이지 않는다
- `task-planner`는 병렬 pool 가능
- `wave-dispatcher`는 전역 단일 agent일 가능성이 높다
- implementer/`code-reviewer`/`compliance-reviewer`/tester는 wave 기준 병렬 가능

### Required Roles vs Optional Roles

항상 필요한 역할:

- 메인 오케스트레이터
- `task-planner`
- `wave-dispatcher`
- implementer

기본값은 선택 역할:

- `compliance-reviewer`
- tester

기본 review 역할:

- `code-reviewer`
- `compliance-reviewer`

review 기본 원칙:

- `code-reviewer`: 구현 품질, 회귀 위험, plan 준수, 테스트 품질 검토
- `compliance-reviewer`: spec/design/implementation design set 정합성, 범위 일탈, 규칙 위반 검토

운영 기본값:

- `code-reviewer`는 모든 task에 대해 mandatory review pass다
- `compliance-reviewer`는 conditional review pass다
- 아주 단순한 요구사항에서는 `code-reviewer`가 정합성 확인까지 함께 커버할 수 있다

tester는 기본적으로 분리하지 않는다. integration test 또는 E2E 작성/실행이 필요할 때만 추가 역할로 붙인다.
implementer는 기본 구현 규칙으로 TDD를 수행한다.

`compliance-reviewer` dispatch is required when user-visible behavior changes, shared contract/CLI/API/schema/persisted state/external interface semantics change, security/privacy/safety/policy-sensitive behavior changes, multiple spec/design docs must agree, broad refactor or scope drift risk exists, data migration/repair/archive behavior changes, or `code-reviewer` marks `compliance_review_required: true`.

Compliance review can be skipped only when the change is narrow and internal, no public or durable state contract changed, no shared interface changed, evidence covers the touched behavior, and code-reviewer explicitly marks `compliance_review_required: false`.

tester dispatch is required when integration/E2E execution is required, cross-flow regression must be verified, environment-specific behavior must be validated, reviewer asks for independent test evidence, or the task changes onboarding, persistence, routing, auth, external IO, or user-critical flows. Tester can be skipped when unit tests cover the change, no integration boundary or cross-flow behavior changed, and code-reviewer does not request independent testing.

Worktree isolation has three modes: `no_worktree`, `external_worktree`, and `future_managed_worktree`. This documentation/runtime repo uses `no_worktree` unless a target product repository provides external git worktrees; cmux role surfaces remain required for visible role separation.

### Dispatch Table

- `draft`
  - 대상 역할: 없음
  - 메인 오케스트레이터가 task를 큐에서 관리한다.
  - 관련 문서 조각이 준비되면 `task-planner`에 배정 가능하다.

- `planning`
  - 대상 역할: `task-planner`
  - 같은 task에는 planner 하나만 붙인다.
  - planner lease가 살아 있는 동안 다른 planner 재배정 금지다.

- `planned`
  - 대상 역할: 없음
  - 메인 오케스트레이터가 plan quality를 검토한다.
  - plan이 executor-ready가 아니면 같은 planner 또는 새 planner에게 수정 요청 가능하다.

- `wave-ready`
  - 대상 역할: `wave-dispatcher`
  - 입력 단위는 단일 task가 아니라 `plan set`이다.
  - 여러 task를 개별적으로 implementer에게 보내면 안 된다.

- `validated-ready`
  - 대상 역할: implementer
  - 이 상태는 dispatch queue다.
  - implementer capacity가 없으면 task는 이 상태에 그대로 머문다.
  - active owner는 없다.

- `implementing`
  - 대상 역할: implementer
  - 구현 lease를 가진 implementer 하나만 유지한다.
  - 같은 task에 reviewer나 다른 implementer를 동시에 붙이지 않는다.

- `reviewing`
  - 대상 역할: `code-reviewer`, `compliance-reviewer`
  - reviewer chain이 끝날 때까지 implementer lease는 종료된 상태로 본다.
  - 같은 시점에는 현재 review pass 하나만 active owner를 가진다.
  - 단, 빠른 수정 루프를 위해 같은 implementer로 즉시 복귀시키는 것은 허용한다.

- `done`
  - 대상 역할: 없음
  - 종료 상태다.

- `blocked`
  - 대상 역할: 없음
  - 외부 입력, 설계 수정, 환경 문제 등 blocker 해소가 먼저다.
  - blocked 상태를 worker parking lot처럼 쓰지 않는다.

### When To Spawn `task-planner`

`task-planner`는 아래를 만족할 때만 붙인다.

- task 상태가 `draft`다
- 관련 문서 조각이 준비됐다
- 해당 task ownership을 대략이라도 식별할 수 있다
- 같은 task를 다른 planner가 점유 중이 아니다

메인 오케스트레이터는 `task-planner`에 넘기기 전에 최소 아래를 확인한다.

- task 범위가 한 planner가 다룰 수 있을 정도로 잘려 있는가
- 관련 없는 문서를 같이 넘기고 있지 않은가
- 출력 계약이 `plan-schema`로 고정되어 있는가

`task-planner` 병렬화 기준:

- 서로 다른 task면 병렬 가능
- shared contract 변경 가능성이 높은 task는 planner 단계에서도 병렬 수를 보수적으로 줄일 수 있다

### When To Spawn `wave-dispatcher`

`wave-dispatcher`는 아래 조건이 모였을 때만 붙인다.

- 하나 이상의 task가 `wave-ready`다
- 각 task에 executor-ready `plan`이 있다
- ownership, dependency, verification 정보가 최소 수준 이상 있다

`wave-dispatcher`는 전역 planning 역할이므로 기본적으로 단일 agent로 본다.

이유:

- 병렬성 강등/승격 판단은 task 단위가 아니라 plan set 단위에서 이뤄진다
- ownership 충돌과 shared contract 변경을 전역 시야에서 봐야 한다

### When To Dispatch Implementer

implementer는 아래를 모두 만족할 때만 붙인다.

- task 상태가 `validated-ready`다
- 승인된 `plan`이 있다
- ownership 경계가 문서화돼 있다
- 최소 검증 명령이 있다
- implementer capacity가 있다

배정 규칙:

- 기본 단위는 task다
- 같은 wave 안에서도 ownership 충돌이 없을 때만 병렬 배정한다
- implementer가 부족하면 우선순위 높은 task부터 `validated-ready` 큐에서 꺼낸다

재배정 규칙:

- implementer가 죽었거나 lease가 만료되면 task를 `validated-ready`로 되돌린다
- 단순 대기 상황 때문에 `blocked`로 옮기지 않는다

### When To Dispatch Reviewers

review phase는 기본적으로 `code-reviewer` pass를 포함한다.

1. `code-reviewer`
2. `compliance-reviewer` if needed

각 reviewer는 아래 조건에서 붙인다.

- task 상태가 `reviewing`이다
- 구현 결과와 verification 결과가 제출됐다
- 현재 review pass에 필요한 문서와 결과물이 준비됐다

운영 기본값:

- `code-reviewer`는 기본 review pass다
- `compliance-reviewer`는 필요 조건이 만족될 때만 추가한다
- 아주 작은 low-risk change에서는 `code-reviewer`가 정합성 확인까지 커버할 수 있다

각 reviewer의 초점:

- `code-reviewer`
  - 구현이 plan을 따르는지
  - 코드 품질과 회귀 위험이 허용 가능한지
  - 테스트가 충분한지
- `compliance-reviewer`
  - 결과가 spec/design/implementation design set과 맞는지
  - 범위를 넘는 변경이 없는지
  - 금지 패턴이나 운영 규칙 위반이 없는지

`compliance-reviewer`를 붙여야 하는 조건:

- 사용자 가시 동작이 바뀐다
- shared contract 또는 외부 인터페이스가 바뀐다
- spec/design/implementation design set의 여러 제약을 동시에 만족해야 한다
- 범위 일탈 위험이 있다
- 보안, 정책, 규칙, 운영 제약 준수가 중요하다
- task 설명이 간단하지 않거나 요구사항 해석 여지가 있다

`compliance-reviewer`를 생략할 수 있는 조건:

- 요구사항이 아주 단순하다
- 변경 범위가 작고 로컬하다
- spec/design 정합성을 따로 해석할 여지가 거의 없다
- `code-reviewer`가 범위 일탈이나 규칙 위반 가능성이 낮다고 판단했다

리뷰 결과에 따른 복귀 규칙:

- 같은 plan 범위 수정이면 `implementing`
- 재배정 가능한 구현 큐로 돌릴 필요가 있으면 `validated-ready`
- plan 또는 ownership 재검토가 필요하면 `planned`
- 외부 개입이 필요하면 `blocked`

pass 전환 규칙:

- `code-reviewer` 통과 후 필요 조건이 있으면 `compliance-reviewer`로 넘긴다
- `code-reviewer` 통과 후 필요 조건이 없으면 바로 `done`으로 종료 가능하다
- `code-reviewer`에서 수정 요청이 나오면 implement 단계로 복귀한다
- `compliance-reviewer`에서 수정 요청이 나오면 implement 단계 또는 planning 단계로 복귀한다

### Tester Position

현재 초안에서는 tester를 독립 필수 역할로 두지 않는다.

- implementer가 기본 검증을 수행한다
- implementer는 unit-level TDD를 기본 구현 규칙으로 수행한다
- `code-reviewer`와 `compliance-reviewer`가 검증 결과를 읽고 추가 검증 필요 여부를 판단한다
- 필요한 경우에만 tester를 별도 역할로 분리한다

tester를 분리해야 하는 조건:

- integration test 작성 또는 실행이 필요하다
- E2E 작성 또는 실행이 필요하다
- 실행 환경이 무겁거나 오래 걸린다
- 기능 구현과 검증을 다른 owner가 보는 편이 더 안전하다

### Lease And Recovery Rules

dispatch는 단순 spawn이 아니라 lease 관리와 함께 간다.

- `planning`: planner lease 필요
- `implementing`: implementer lease 필요
- `reviewing`: current review pass lease 필요

회수 규칙:

- agent 종료 또는 lease 만료가 감지되면 메인 오케스트레이터가 owner를 회수한다
- `planning` 중 회수되면 보통 `draft` 또는 `planning` 재배정 후보로 돌린다
- `implementing` 중 회수되면 `validated-ready`로 되돌리는 것을 기본으로 한다
- `reviewing` 중 회수되면 현재 pass를 같은 review type으로 재배정하거나 `implementing` 복귀 중 하나를 선택한다

### Dispatch Anti-Patterns

금지 또는 지양:

- `planned` 상태 task를 implementer에게 먼저 보내는 것
- `validated-ready`가 아닌 task를 execution에 투입하는 것
- review chain의 피드백 대부분을 `blocked`로 올리는 것
- implementer가 부족하다는 이유만으로 task를 `blocked` 처리하는 것
- 같은 task에 planner와 implementer를 동시에 붙이는 것
- terminal output만 보고 상태를 바꾸는 것

## 3. Role Transfer Contracts

이 섹션은 agent 간 canonical artifact를 다룬다.

후보:

- `task-planner` input contract
- `task-planner` output contract
- `wave-dispatcher` input contract
- `wave-dispatcher` output contract
- implementer input contract
- `code-reviewer` input contract
- `compliance-reviewer` input contract

정리할 질문:

- `task-planner` 입력 묶음은 정확히 무엇인가
- `task-planner` 출력에서 메인이 꼭 읽어야 하는 필드는 무엇인가
- `wave-dispatcher`가 받는 입력은 `plan set`만으로 충분한가
- implementer/`code-reviewer`/`compliance-reviewer`/tester 입력은 어느 수준까지 canonicalize할 것인가
- 각 역할의 출력이 다음 역할 입력으로 넘어갈 때 필수 보존 필드는 무엇인가

## 4. cmux Operation Layer

`cmux`는 source of truth가 아니라 role worker를 깨우고 화면 증거를 수집하는 운영 레이어다.

Source of truth는 `.moondex/state` 아래의 task, role identity/status, dispatch, mailbox, evidence 기록이다. 터미널 출력만으로 task 완료, dispatch 전달, review 승인 여부를 확정하지 않는다.

운영 규칙:

- role별 surface를 기본 단위로 둔다: orchestrator, implementer, `code-reviewer`, 필요 시 `compliance-reviewer`와 tester.
- worker는 `role register-current`로 현재 `cmux identify`의 `caller.surface_ref`를 role identity에 등록한다.
- orchestrator는 `moondex dispatch <role> <task-id>`로 dispatch request를 만들고, role identity에 surface가 있으면 `cmux send`로 shell-safe trigger를 전송한다.
- dispatch `notified`는 wake-up transport 성공만 뜻한다. worker가 실제로 inbox를 읽었음을 증명하려면 `ack-dispatch`가 필요하고, 이때 request가 `delivered`가 된다.
- worker output은 mailbox에 남긴다. `write-mailbox` body는 kind별 JSON object string schema를 통과해야 하며, orchestrator/reviewer는 `consume-mailbox-for-task`로 task-scoped message를 소비한다.
- retry는 같은 request id에 대해 `retry-dispatch`로만 수행한다. 최신 role identity surface를 다시 resolve하며, request별 retry는 최대 3회다. 3회를 넘기면 전송하지 않고 `last_reason = retry_exhausted`로 실패 상태를 남긴다.
- `cmux send` 전에는 `cmux tree --json`으로 target surface 존재를 확인한다. invalid surface가 현재 surface로 fallback되는 동작을 막기 위해 send 결과의 `OK surface:<id>`도 요청 surface와 일치해야 한다.
- `cmux capture`는 terminal evidence를 `.moondex/state/evidence/`에 저장하는 보조 증거다. evidence는 상태 전이 자체를 대체하지 않는다.
- `cmux`가 없는 환경에서는 dispatch request와 mailbox/state API만 사용한다. 이 경우 request는 `surface_ref_missing`으로 `pending`에 남고, worker가 직접 state API를 확인해 ACK와 mailbox write를 수행한다.

### Validation Mode Guardrails

Moondex runtime 자체가 product 구현 성공보다 운영 모델 충실도를 우선한다.

따라서 아래를 기본 규칙으로 둔다.

- Moondex 검증 모드에서는 먼저 `cmux` 작업면을 만든다.
  - 최소 구성:
    - orchestrator pane
    - implementer pane
    - reviewer pane
    - 필요 시 test pane
- implementer와 reviewer의 왕복 루프가 실제로 발생해야 “execution layer 검증”으로 인정한다.
- 메인 오케스트레이터는 role dispatch, 상태 전이, role transfer contract 확인에 집중한다.
- product code 수정은 검증의 부산물이지 1차 목적이 아니다.
- `spawn_agent`는 Moondex 본래 runtime 경로로 사용하지 않는다.
- 역할 실행은 role별 터미널 작업면 dispatch를 기본으로 한다.

금지 규칙:

- 테스트를 빨리 통과시키는 것을 이유로 Moondex 검증 목표를 바꾸지 않는다.
- implementer 없이 메인 에이전트가 직접 product fix를 진행하고 이를 Moondex 실행으로 간주하지 않는다.
- reviewer 왕복 없이 “한 번 수정 + 한 번 테스트”만으로 멀티에이전트 검증이 끝났다고 보지 않는다.

## Next Discussion Order

이 문서를 기준으로 다음 순서로 논의한다.

1. state machine 확정
2. role selection / dispatch 규칙
3. role transfer contract
4. `cmux` 운영 규칙
