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
- shared contract 변경이 필요해지면 즉시 task를 blocked로 되돌린다
- 설계 보완이 필요해지면 구현을 멈추고 task/plan/wave와의 불일치를 보고한다
- 범위를 넓히지 않는다

## Before Closing

- acceptance criteria를 하나씩 확인한다
- 필요한 테스트를 실행한다
- verification commands를 기록한다
- planning 산출물(task/plan/wave) 대비 실제 구현 차이를 보고한다
- 남은 리스크와 follow-up 필요 사항을 정리한다
