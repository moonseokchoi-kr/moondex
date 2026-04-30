# Planning Workflow

이 문서는 Codex가 `spec`, `design set`, `implementation design set`를 받아 task, plan, wave를 생성하는 절차를 정의한다.

중요한 구조적 결정:

- 메인 에이전트는 planning stage 전환, agent 배정, `wave` 확정, 실행 상태 관리를 담당한다.
- `task decomposition`은 `moondex-task-creator` 스킬이 담당한다.
- 각 task의 `plan` 상세화는 전용 `task-planner` planner agent가 담당한다.
- `wave`는 모든 dispatchable task의 `task-planner` 출력 이후에 `moondex-wave-dispatcher` stage에서 확정한다.
- implementer는 `validated ready` 상태의 task만 받는다.
- implementer는 기본 구현 규칙으로 TDD를 수행한다.
- `task-planner`의 역할 정의 엔트리는 `.codex/agents/task-planner.toml`이다.
- planner/implementer/`code-reviewer`/`compliance-reviewer` 역할은 role별 터미널 작업면에서 실행하는 것을 기본으로 한다.
- 작업면 운영은 `cmux` 같은 터미널 멀티플렉서로 수행한다.

## Workflow

1. 입력 문서를 읽는다
- `spec`, `design set`, `implementation design set`를 읽고 요구사항, 구조, 구현 제약을 분리한다

2. 코드베이스를 스캔한다
- 현재 디렉터리 구조
- 주요 모듈 경계
- 테스트 구조
- 변경 파급 가능 영역

3. 구현 전략을 요약한다
- 어떤 레이어를 먼저 바꿔야 하는지
- shared contract 변경이 있는지
- 병렬화가 가능한지

4. task를 분해한다
- `moondex-task-creator`를 사용한다
- 각 task가 단일 목표를 가지도록 분해한다
- 각 task에 non-goals, dependencies, 범위 경계를 부여한다
- runtime 등록용 payload는 deferred enqueue data로만 둔다

5. planning 후보 task를 `task-planner`에 배정한다
- 메인 에이전트는 해당 task와 관련 문서 조각만 추린다
- 전용 `task-planner` planner agent에 입력을 넘긴다
- Codex는 프로젝트 스코프 커스텀 에이전트 `task-planner`를 사용한다
- planner agent는 `task-planner` 스킬을 사용한다
- 서로 독립적인 task의 planner 요청은 병렬로 실행할 수 있다

6. `task-planner`가 각 task를 plan으로 상세화한다
- 각 task에 대해 ownership, contracts, tests, verification을 구체화
- step-driven 실행 순서를 작성한다
- 체크포인트와 blocked 조건을 작성한다
- executor-ready 기준을 만족하도록 plan 작성

7. 메인 에이전트가 `plan`들을 검토한다
- task 수준 병렬 가능 판단을 재검토한다
- shared contract, 수정 파일, 테스트 인프라 충돌 여부를 확인한다
- `plan` 기준으로 병렬 가능 task를 확정하거나 직렬로 강등한다

8. `wave-dispatcher`가 wave를 확정한다
- `moondex-wave-dispatcher`를 사용한다
- 모든 plan이 준비된 plan set을 기준으로 dependency graph를 다시 작성한다
- wave 또는 병렬 그룹을 확정한다
- verification plan을 구성한다

9. planning quality를 점검한다
- task schema 기준 충족 여부 확인
- plan schema 기준 충족 여부 확인
- wave schema 기준 충족 여부 확인
- 불충분하면 planning 단계에서 수정

10. readiness review를 거친다
- READY면 실행 단계로 이동
- REVISION_REQUIRED면 planning 수정
- BLOCKED면 상위 문서 보완 요청

11. execution dispatch를 시작한다
- READY wave task만 runtime에 `create-task`로 등록한다
- implementer는 `validated ready` 상태의 task만 받는다
- implementer는 task 범위 안에서 unit-level TDD를 기본으로 수행한다
- `code-reviewer`는 항상 붙고, `compliance-reviewer`는 필요할 때만 뒤이어 붙는다
- tester는 integration test 또는 E2E 작성/실행이 필요할 때 선택적으로 붙는다
- planning stage와 execution stage는 같은 task에 대해 동시에 진행하지 않는다

12. 멀티 터미널 운영 레이어 위에서 execution을 진행한다
- planner/implementer/`code-reviewer`/`compliance-reviewer` 역할의 실행 화면을 분리한다
- `cmux` 같은 멀티플렉서로 각 세션에 명령을 전송하고 결과를 읽는다
- 이 레이어는 source of truth를 대체하지는 않지만, Moondex runtime에서는 기본 운영 경로다

## Planning Outputs

Codex planning 단계의 공식 산출물:

- task set
- deferred runtime create-task payloads
- executor-ready plan set
- wave plan
- planning notes 또는 risk summary

## Stage Rule

- 기본 경로는 `all tasks -> all plans -> wave approval -> runtime enqueue -> dispatch` 순서를 지킨다.
- 전체 task set 수준에서 task planning은 병렬일 수 있다.
- 단, execution은 항상 `validated ready` 상태의 task만 대상으로 한다.
