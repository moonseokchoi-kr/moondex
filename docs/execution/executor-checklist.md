# Executor Checklist

이 문서는 Codex가 planning을 마친 뒤 execution 단계에서 따르는 최소 실행 체크리스트다.

## Before Coding

- task의 goal과 non-goals를 다시 확인한다
- 대응하는 plan의 ownership, contracts, tests를 확인한다
- wave 순서를 확인한다
- ownership 범위를 확인한다
- 수정 금지 범위를 확인한다
- acceptance criteria와 tests를 확인한다
- verification commands를 확인한다

## During Coding

- task ownership 범위 밖 변경은 피한다
- 승인된 wave 안에서는 큰 블로커가 없으면 사용자에게 묻지 않고 계속 진행한다
- repo conventions, plan fallback, tests로 결정 가능한 구현 세부는 직접 판단한다
- shared contract 변경이 필요해지면 low-interruption policy 기준으로 high-impact blocker인지 먼저 판단한다
- 설계 보완이 필요해도 task/plan/wave 범위 안에서 해결 가능하면 계속 진행하고 mailbox/status로 보고한다
- 범위를 넓히지 않는다

## When To Stop

- [low-interruption-policy.md](/Users/moon/Workspace/moondex/docs/execution/low-interruption-policy.md)의 high-impact blocker 조건에 해당할 때만 사용자 판단을 요청한다
- 그 외에는 mailbox `status` 또는 `result`로 진행 상황을 남기고 implementation을 계속한다

## Before Closing

- acceptance criteria를 하나씩 확인한다
- 필요한 테스트를 실행한다
- verification commands를 기록한다
- planning 산출물(task/plan/wave) 대비 실제 구현 차이를 보고한다
- 남은 리스크와 follow-up 필요 사항을 정리한다
