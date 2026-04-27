# Executor Direction

이 문서는 `moondex`의 현재 방향을 고정하는 살아있는 기준 문서다.

목적은 두 가지다.

1. 우리가 무엇을 만들고 있는지 흔들리지 않게 유지한다.
2. 이후 설계 변경이 생길 때 합의된 기준 위에서 문서를 갱신한다.

## Current Thesis

이 프로젝트는 `SDD 전체를 수행하는 Codex Moondex`가 아니라, 외부에서 정리된 `spec`, `design set`, `implementation design set`를 입력으로 받아 Codex가 `task decomposition`, `task plan 작성`, `wave 구성`, `implementation`을 수행하는 `design-informed multi-agent planner-executor runtime`를 지향한다.

즉, 중심은 상위 설계 생성이 아니라 `로컬 코드베이스에 맞는 실행 계획 수립과 구현 품질`이다.

## Core Position

### 1. Codex의 기본 역할

Codex는 기본적으로 아래를 담당한다.

- 입력 문서(`spec`, `design set`, `implementation design set`)를 읽고 코드베이스를 분석
- 구현 대상 task를 생성
- `task-planner` planning layer가 각 task를 executor-ready 수준의 `plan`으로 상세화
- `wave-dispatcher` planning layer가 plan들을 기준으로 실제 `wave`를 구성
- `validated plan`과 `wave`를 기준으로 구현
- 테스트 추가 및 실행
- spec/design set/implementation design set 대비 불일치 보고
- 구현 결과와 남은 리스크 정리

Codex가 기본적으로 담당하지 않는 것:

- 요구사항 탐색
- 아키텍처 결정
- 제품 수준 우선순위 결정
- 근본적인 설계 의도 변경

## 2. 입력 문서 모델

planning 시작 전에 아래 문서 계층이 존재한다고 가정한다.

- `spec`: 왜 만들고 무엇을 만족해야 하는가
- `design set`: 어디에 어떻게 넣을 것인가를 설명하는 문서 묶음
- `implementation design set`: 구현 전략, 제약, 모듈 경계, 테스트 접근을 설명하는 문서 묶음

핵심 판단:

- `task`, `plan`, `wave`는 외부에서 들어오는 것이 아니라 Codex가 만든다.
- `task`는 무엇을 할지 정의하는 상위 작업 단위다.
- `plan`은 task 하나를 실제로 어떻게 수행할지 적는 executor-ready 문서다.
- `plan`은 일반 프롬프트가 아니라 `task-planner` 스킬을 쓰는 전용 planner agent가 생성하는 것을 기본으로 한다.
- `wave`는 `task`가 아니라 `validated plan set`을 기준으로 확정한다.
- `wave`는 여러 task/plan을 어떤 순서와 병렬성으로 실행할지 정의하는 오케스트레이션 단위다.
- 멀티 에이전트 실행을 하려면 이 요구사항은 더 강해진다.

## 3. Planning Quality Gate

Codex가 만든 `plan`은 최소한 `plan mode` 수준이어야 한다.

최소 필수 정보:

- 목표
- 비목표
- 선행 의존성
- 병렬 실행 가능 여부
- 소유 파일 또는 디렉터리
- 수정 금지 범위
- 입력/출력 계약
- acceptance criteria
- 테스트 요구사항
- 검증 명령어
- 통합 시 주의점

이 정보가 부족하면 Codex는 구현 중 다시 설계를 하게 되고, 이 Moondex의 목표와 충돌한다.

## 4. Team Execution Position

구현을 팀으로 운영하는 것은 가능할 뿐 아니라, 현재 방향에서는 기본 운영 모델에 가깝다. 다만 planning layer와 execution layer를 섞어서는 안 된다.

팀 실행이 타당한 조건:

- task가 적절히 분해돼 있다
- plan이 executor-ready 수준이다
- wave에 dependency graph가 있다
- 파일 또는 모듈 ownership이 명시돼 있다
- 병렬 가능 여부가 문서에 적혀 있다
- shared contract 변경 여부가 드러나 있다

따라서 팀의 성공 여부는 agent 수보다 Codex가 만든 task/plan/wave의 품질에 달린다.

운영 메모:

- planner agent와 execution agent는 서로 다른 레이어다.
- `task-planner`는 planning pool에 속한다.
- `wave-dispatcher`는 `task-planner` 출력 이후에만 동작한다.
- implementer는 `validated ready` 상태의 task만 받는다.
- implementer는 기본 구현 규칙으로 TDD를 수행한다.
- planner agent, implementer agent, mandatory `code-reviewer`, conditional `compliance-reviewer`는 role별 **별도 터미널 작업면**에서 실행되는 것을 기본으로 본다.
- `.codex/agents/*.toml`은 역할 정의에 가깝고, 실제 orchestration은 메인 에이전트가 `cmux` 같은 멀티플렉서 위에서 작업면을 운영하며 담당한다.
- 이 Moondex는 `spawn_agent` 같은 내부 서브에이전트 호출 모델을 기본 runtime으로 채택하지 않는다.
- `cmux` 같은 터미널 멀티플렉서는 단순 모니터링 보조가 아니라, Moondex의 역할 분리와 handoff를 관찰 가능한 형태로 유지하는 기본 운영 레이어다.
- `compliance-reviewer`는 user-visible behavior, shared contract/CLI/API/schema/persisted state/external interface, safety/privacy/security/policy-sensitive behavior, migration/repair/archive behavior, broad refactor, or explicit `compliance_review_required: true` 조건에서 붙인다.
- tester는 integration/E2E, cross-flow regression, environment-specific behavior, independent test evidence, onboarding/persistence/routing/auth/external IO/user-critical flow 변경이 있을 때만 별도 role로 붙인다.

## 5. legacy SDD prototype에서 가져올 것

legacy SDD prototype의 다음 아이디어는 적극적으로 재사용한다.

- 문서가 상태가 되는 구조
- `sdd-taskmaster` 중심의 task decomposition 사고방식
- DAG/Wave 기반 실행 관점
- ownership과 dependency를 문서화하는 방식

하지만 Codex 버전에서는 초점을 다르게 둔다.

- 상위 설계 생성보다 planning 입력 계약을 우선한다
- 자동 훅보다 명시적 planning/execution 규칙을 우선한다
- 전체 SDD 오케스트레이터보다 planning quality gate와 readiness gate를 우선한다

## 6. Near-Term Build Order

현재 우선순위는 아래와 같다.

1. 방향 문서 유지
2. 입력 문서 계약(`spec`, `design set`, `implementation design set`) 정의
3. task schema, plan schema, wave schema 정의
4. `task-planner` 스킬과 planner agent 계약 정의
5. `wave-dispatcher` 역할과 `plan -> wave` 기준 정의
6. planning workflow 정의
7. planning quality gate와 readiness gate 정의 및 `validate-readiness` 실행화
8. Codex 실행 체크리스트와 hook validator 연결

즉 팀 오케스트레이션은 목표일 수 있지만, 첫 번째 구현 대상은 아니다.

## 6.5 Runtime Rule

Moondex runtime은 아래를 기본으로 한다.

- 메인 오케스트레이터는 문서 상태 기준으로 dispatch한다.
- implementer / `code-reviewer` / `compliance-reviewer` / tester는 role별 터미널 작업면을 가진다.
- 작업면 운영은 `cmux` 같은 멀티플렉서로 수행한다.
- 역할 간 handoff와 재작업 루프는 terminal history와 문서 상태를 통해 관찰 가능해야 한다.
- `.codex/hooks`는 contract enforcement entrypoint이고, `.moondex/state/hooks/warnings.json`는 warning-only 결과를 durable하게 남기는 위치다.

금지 규칙:

- Moondex 자체를 `spawn_agent` 중심 구조로 축소하지 않는다.
- 메인 에이전트가 직접 product fix를 수행하고 이를 Moondex 실행으로 간주하지 않는다.
- reviewer 왕복 없이 “수정 후 테스트 통과”만으로 멀티에이전트 실행이 검증됐다고 보지 않는다.

## 7. Working Rules

이 저장소를 수정할 때는 아래 원칙을 따른다.

1. 방향이 바뀌면 이 문서를 먼저 갱신한다.
2. 새 스크립트나 문서는 이 문서의 방향과 맞아야 한다.
3. 입력 문서 계약을 바꾸면 planning 산출물 기준도 함께 수정한다.
4. task schema를 바꾸면 gate 기준도 함께 수정한다.

## 8. Open Questions

아직 결론이 나지 않은 항목:

- implementation design set의 최소 요구사항은 어디까지인가
- task를 얼마나 거칠게 두고, plan에 얼마나 상세를 밀어넣을 것인가
- wave의 정확한 스키마는 무엇인가
- `task-planner` planner agent에 넘길 문서 조각을 얼마나 작게 자를 것인가
- `task` 단계의 병렬 가능 가설을 `plan` 단계에서 어떻게 강등/확정할 것인가
- Codex 팀 실행의 기본 단위를 task로 둘지 wave로 둘지
- native Codex lifecycle hook 자동 연결을 어디까지 안정적으로 기대할 수 있는지
- future managed worktree mode를 Moondex v1 이후에 구현할지

## 9. Update Log

### 2026-04-21

- Codex를 상위 설계 수신형 `planner-executor`로 두는 방향으로 정리
- task, plan, wave를 분리해야 한다는 결론 반영
- `plan`은 전용 `task-planner` 스킬 + planner agent가 생성해야 한다는 방향 반영
- `wave`는 plan 이후에 확정되는 별도 planning stage라는 판단 반영
- implementer는 `validated plan` 이후에만 배정되어야 한다는 판단 반영
- 멀티 에이전트 구현팀은 task/plan/wave 품질이 확보될 때만 유효하다는 판단 반영
- 저장소 파일을 executor-first 기준으로 감사하고, phase 상태 머신/SKILL 기반 SDD 스캐폴드를 제거하기로 결정
- 멀티 에이전트 중심 운영과 터미널 멀티플렉서 기반 모니터링을 수용하는 방향 반영
