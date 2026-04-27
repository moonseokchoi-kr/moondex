# Money Track Example

이 예시는 `/Users/moon/Workspace/money_track/docs/sdd`의 `app-bootstrap-and-theme` 문서를 기준으로 우리 하네스의 `task -> plan -> wave` 모델을 적용한 샘플이다.

## Source Documents

- spec: `/Users/moon/Workspace/money_track/docs/sdd/spec/2026-04-15-app-bootstrap-and-theme.md`
- arch: `/Users/moon/Workspace/money_track/docs/sdd/design/arch/2026-04-15-app-bootstrap-and-theme.md`
- ui: `/Users/moon/Workspace/money_track/docs/sdd/design/ui/2026-04-15-app-bootstrap-and-theme.md`
- context: `/Users/moon/Workspace/money_track/docs/sdd/context/2026-04-15-app-bootstrap-and-theme.md`
- existing task reference: `/Users/moon/Workspace/money_track/docs/sdd/task/app-bootstrap-and-theme/*.md`

## Important Assumption

`money_track`에는 현재 별도의 `develop/` 문서가 없다.

이 예시에서는 아래 문서 조합을 `implementation design set`으로 간주했다.

- arch
- context
- API/use case/provider 정보
- 기존 task 문서에 이미 적힌 구현 전략

즉 이 예시는 완전한 원문 입력이 아니라, 실제 코드베이스 planning에 필요한 정보를 재구성한 샘플이다.

## Outputs

- task set: [task-set.md](/Users/moon/Workspace/codex-moon-harness/docs/examples/money-track-app-bootstrap-theme/task-set.md)
- plan set: [plan-set.md](/Users/moon/Workspace/codex-moon-harness/docs/examples/money-track-app-bootstrap-theme/plan-set.md)
- wave plan: [wave-plan.md](/Users/moon/Workspace/codex-moon-harness/docs/examples/money-track-app-bootstrap-theme/wave-plan.md)
- orchestration simulation: [orchestration-simulation.md](/Users/moon/Workspace/codex-moon-harness/docs/examples/money-track-app-bootstrap-theme/orchestration-simulation.md)

## Why This Example

이 feature는 다음을 모두 포함한다.

- foundation task
- shared theme/core module
- 다수 화면 재설계
- provider/use case 추가
- 병렬 실행 가능 영역과 직렬 실행 필요 영역

그래서 `task -> plan -> wave` 분리를 검증하기에 적합하다.
