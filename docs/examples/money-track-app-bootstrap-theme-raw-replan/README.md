# Money Track Raw Replan Example

이 예시는 `money_track`의 기존 task 문서를 재사용하지 않고, raw input 문서만 기준으로 `task -> plan -> wave`를 다시 생성해 보기 위한 비교용 샘플이다.

## Primary Inputs

- spec: `/Users/moon/Workspace/money_track/docs/sdd/spec/2026-04-15-app-bootstrap-and-theme.md`
- architecture design: `/Users/moon/Workspace/money_track/docs/sdd/design/arch/2026-04-15-app-bootstrap-and-theme.md`
- API contract: `/Users/moon/Workspace/money_track/docs/sdd/design/api/2026-04-15-app-bootstrap-and-theme.md`

보조 참고:

- UI design: `/Users/moon/Workspace/money_track/docs/sdd/design/ui/2026-04-15-app-bootstrap-and-theme.md`

## Comparison Target

기존 산출물:

- existing tasks: `/Users/moon/Workspace/money_track/docs/sdd/task/app-bootstrap-and-theme/*.md`
- prior harness example: [money-track-app-bootstrap-theme](/Users/moon/Workspace/codex-moon-harness/docs/examples/money-track-app-bootstrap-theme/README.md)

## Outputs In This Folder

- task set: [task-set.md](/Users/moon/Workspace/codex-moon-harness/docs/examples/money-track-app-bootstrap-theme-raw-replan/task-set.md)
- plan set: [plan-set.md](/Users/moon/Workspace/codex-moon-harness/docs/examples/money-track-app-bootstrap-theme-raw-replan/plan-set.md)
- wave plan: [wave-plan.md](/Users/moon/Workspace/codex-moon-harness/docs/examples/money-track-app-bootstrap-theme-raw-replan/wave-plan.md)
- planner dispatch review: [task-planner-dispatch-review.md](/Users/moon/Workspace/codex-moon-harness/docs/examples/money-track-app-bootstrap-theme-raw-replan/task-planner-dispatch-review.md)
- category management split note: [t09-split-replan.md](/Users/moon/Workspace/codex-moon-harness/docs/examples/money-track-app-bootstrap-theme-raw-replan/t09-split-replan.md)
- execution test review: [execution-test-review.md](/Users/moon/Workspace/codex-moon-harness/docs/examples/money-track-app-bootstrap-theme-raw-replan/execution-test-review.md)

## Intent

이 예시의 목적은 세 가지다.

1. raw input만으로도 task 경계가 충분히 선명하게 나오는지 확인한다.
2. 기존 task 문서와 비교해 dependency, ownership, cross-feature contract 분리가 개선됐는지 본다.
3. 이후 `plan set`과 `wave plan`을 만들 때 source-of-truth를 raw input에만 두는 흐름을 검증한다.

## Validation Status

- 현재 `task-set / plan-set / wave-plan`은 실제 `task-planner` dispatch 결과를 반영한 교정본이다.
- 특히 category management는 원래 단일 `T-09`로는 planner-friendly 하지 않았고, 검증 후 `T-09A/B/C`로 공식 분해되었다.
