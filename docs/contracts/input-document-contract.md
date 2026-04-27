# Input Document Contract

이 문서는 Codex planning 단계에 들어오기 전에 외부에서 제공되어야 하는 입력 문서 계약을 정의한다.

입력은 보통 한 문서씩 오지 않는다. 실제로는 아래 묶음으로 들어온다고 가정한다.

- `spec`
- `design set`
- `implementation design set`

Codex는 이 입력 묶음을 받아 task, plan, wave를 생성한다.

## 1. Spec

`spec`은 기능의 목적과 요구사항을 정의한다.

최소 포함 요소:

- 문제 정의
- 목표
- 비목표
- 사용자 또는 시스템 시나리오
- 기능 요구사항
- acceptance criteria
- open questions

`spec`이 답해야 하는 질문:

- 왜 이 기능을 만드는가
- 무엇이 완성 조건인가
- 무엇은 이번 범위가 아닌가

## 2. Design Set

`design set`은 구조와 계약을 정의하는 문서 묶음이다.

최소 포함 요소:

- 아키텍처 경계
- 모듈 책임
- 데이터 흐름
- 주요 타입 또는 API 계약
- 실패 시나리오
- 테스트 전략

대표 예:

- `arch`
- `ui`
- `api`
- `data model`

`design set`이 답해야 하는 질문:

- 어디에 넣는가
- 어떤 경계를 지켜야 하는가
- 어떤 계약을 깨면 안 되는가

## 3. Implementation Design Set

단일 `develop` 문서가 항상 있는 것은 아니다.

실제로는 구현 직전의 기술적 제약과 전략이 아래처럼 여러 문서에 분산돼 들어올 수 있다.

- `arch`의 구현 전략 섹션
- `api` 계약 상세
- `context`
- 기존 task 초안
- provider/use case/repository 설계 메모

이 Moondex는 이를 합쳐 `implementation design set`으로 취급한다.

최소 포함 요소:

- 대상 모듈 또는 레이어
- 구현 전략
- 유지해야 할 기존 인터페이스
- 예상 리스크
- 테스트 접근 방식
- 성능/보안/호환성 제약
- 구현 순서에 대한 힌트

`implementation design set`이 답해야 하는 질문:

- 구현은 어떤 레이어를 중심으로 진행해야 하는가
- 어떤 기술적 제약을 지켜야 하는가
- task 분해 시 어떤 경계를 기준으로 삼아야 하는가

## Input Completeness Rule

Codex planning을 시작하려면:

- `spec`이 완성 조건을 정의해야 한다
- `design set`이 구조와 계약을 정의해야 한다
- `implementation design set`이 구현 전략과 제약을 정의해야 한다

이 중 하나라도 비어 있으면 planning 품질이 떨어지고, task 분해가 추측 기반이 된다.

## Output Link

이 입력 계약을 바탕으로 Codex는 아래 산출물을 만든다.

- task
- executor-ready plan
- wave
