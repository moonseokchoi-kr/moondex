# Task Planner Agent

이 문서는 `task -> plan` 변환을 담당하는 전용 planner agent의 역할과 계약을 정의한다.

핵심 결정:

- `plan`은 메인 에이전트가 일반 프롬프트로 직접 쓰지 않는다.
- 각 `task`는 전용 planner agent에 전달된다.
- planner agent는 `.agents/skills/task-planner/SKILL.md`의 `task-planner` 스킬을 사용해 `plan mode` 수준의 문서를 작성한다.
- 실제 Codex 커스텀 에이전트 엔트리는 [.codex/agents/task-planner.toml](/Users/moon/Workspace/codex-moon-harness/.codex/agents/task-planner.toml)이다.
- 이 agent는 planning layer에 속하며 implementer와 같은 단계에서 동작하지 않는다.

## Why This Exists

일반 프롬프트만으로는 아래가 안정적으로 나오기 어렵다.

- step-driven execution steps
- 순서 이유
- checkpoints
- blocked 조건
- fallback
- verification commands

또한 task 분해 컨텍스트와 plan 상세화 컨텍스트를 분리하지 않으면 메인 컨텍스트가 쉽게 오염된다.

이 planner agent의 목표는 "가장 긴 plan"이 아니라 "executor가 바로 시작 가능한 최소 충분 계획"이다.

## Role Split

- 메인 에이전트:
  - 입력 문서 묶음을 읽는다
  - task set을 만든다
  - 각 task를 planner agent에 배정한다
  - 반환된 plan들을 읽고 `wave-dispatcher` 단계로 넘긴다

- task-planner planner agent:
  - 하나의 task만 책임진다
  - 관련 문서 조각만 읽는다
  - `task-planner` 스킬을 실행한다
  - [plan-schema.md](/Users/moon/Workspace/codex-moon-harness/docs/contracts/plan-schema.md) 형태의 plan 하나를 반환한다

- implementer:
  - `validated ready`가 된 task만 받는다
  - task-planner와 같은 task를 동시에 처리하지 않는다

## Input Contract

planner agent 입력은 최소한 아래를 포함한다.

- task 문서 하나
- 관련 spec 조각
- 관련 design set 조각
- 관련 implementation design set 조각
- 현재 코드베이스에서 해당 task와 직접 관련된 경로 정보
- 출력 계약: [plan-schema.md](/Users/moon/Workspace/codex-moon-harness/docs/contracts/plan-schema.md)

중요:

- 관련 없는 task 전체를 넘기지 않는다
- 전체 spec/design를 무조건 통째로 넘기지 않는다
- 해당 task를 plan하는 데 필요한 조각만 준다

## Output Contract

planner agent는 아래를 만족하는 plan 하나를 반환해야 한다.

- task 목표를 구현 관점으로 재서술
- ownership이 명시됨
- execution steps가 있음
- 각 step의 순서 이유가 있음
- checkpoints와 blocked 조건이 있음
- fallback 또는 rollback이 있음
- acceptance criteria가 검증 가능함
- test requirements와 verification commands가 있음
- 첫 step와 첫 검증 명령이 바로 실행 가능함
- 병렬 가능 여부가 provisional인지, 실제로 직렬 강등 가능성이 있는지 드러나야 함

## Hard Rules

- task 범위를 확장하지 않는다
- 상위 설계를 다시 쓰지 않는다
- wave를 직접 구성하지 않는다
- 모호한 표현을 남기지 않는다
- executor가 추가 설계 없이 바로 구현을 시작할 수 있어야 한다
- codebase facts를 추측으로 채우지 않는다
- 과도한 micro-step 나열을 하지 않는다

## Failure Modes

planner agent는 아래 경우 명시적으로 실패를 반환해야 한다.

- task 경계가 모호함
- ownership을 결정할 정보가 부족함
- 입력 문서 조각 사이에 충돌이 있음
- verification command를 정할 수 없을 정도로 실행 정보가 부족함
- 코드베이스를 봐도 첫 step를 결정할 수 없음
- 동일한 shared contract나 테스트 인프라 충돌 때문에 병렬성 판단을 안전하게 못 내리는 경우

권장 상태값:

- `DONE`
- `NEEDS_CONTEXT`
- `BLOCKED`

## Future Extension

이 패턴은 이후 `wave-dispatcher`와 execution agent에도 이어진다.

- `task-planner` planner agent: task -> plan
- `wave-dispatcher` planning agent: task/plan -> wave
- implementer/`code-reviewer`/`compliance-reviewer`/tester: `validated ready task` 또는 구현 결과를 소비
- 운영 중에는 `cmux` 같은 멀티플렉서로 여러 agent 세션을 분리해 모니터링할 수 있다
