# Task Planner Dispatch Review

```yaml
feature_name: app-bootstrap-and-theme-raw-replan
test_type: real-task-planner-dispatch
date: 2026-04-25
source_task_set: /Users/moon/Workspace/moondex/docs/examples/money-track-app-bootstrap-theme-raw-replan/task-set.md
product_repo: /Users/moon/Workspace/money_track
```

## Scope

- 목표: raw input 기준 `task set`을 실제 `task-planner` 서브에이전트에 디스패치하고, planner output 품질과 orchestration failure mode를 확인한다.
- 비목표: 구현 착수, wave execution, 문서 기반 수동 `plan-set.md`를 source of truth로 사용하는 것.

## Result Summary

- `DONE` 회수 성공: `T-01`, `T-02`, `T-03`, `T-04`, `T-05`, `T-06`, `T-07`, `T-08`, `T-10`, `T-11`
- `T-09`는 단일 task로는 회수 실패했지만, 공식 split 이후 `T-09A`, `T-09B`, `T-09C`는 모두 `DONE`으로 회수됐다.
- 1차 대규모 병렬 디스패치에서는 `T-01`, `T-03`, `T-08`, `T-09`, `T-10`, `T-11`이 장시간 탐색 상태에 머물렀다.
- recovery strategy:
  - hung agent close
  - 더 좁은 입력 범위로 fresh `task-planner` 재디스패치
  - `T-01`, `T-03`, `T-08`, `T-11`은 recovery 성공
  - `T-09`는 재시도 후에도 hung 상태로 종료
  - 이후 `T-09A/B/C` split recovery는 모두 성공

## Orchestration Findings

- `task-planner`를 넓은 컨텍스트로 병렬 다수 실행하면 일부 task에서 탐색이 과도하게 길어지는 failure mode가 실제로 발생했다.
- thread limit는 `6`이었고, 완료 agent를 명시적으로 `close_agent` 해야 다음 배치를 태울 수 있었다.
- hung task에 대해 `interrupt` 신호만으로는 종료가 보장되지 않았다.
- recovery에는 아래가 효과적이었다:
  - task별 관련 경로를 강하게 제한
  - task 하나 또는 소수만 재디스패치
  - “지금 결론 내라”는 종료 지시 추가
- 아직 필요한 운영 규칙:
  - planner timeout 기준
  - hung planner close/retry policy
  - retry 시 입력 축소 규칙
  - repeated hung task의 human fallback 규칙

## Plan Quality Findings

### T-01

- planner가 실제 코드에서 `main.dart` composition root는 이미 존재하지만, default category seed source가 `DatabaseInitializer`와 `CategoryRepositoryImpl`에 이중 존재한다고 짚었다.
- 수동 replan보다 bootstrap 책임 단일화와 startup failure handling 일관성에 더 강하게 초점을 맞췄다.

### T-02

- planner가 `lib/app/app.dart` 부재, `main.dart`의 `MaterialApp.router` 직접 소유, theme token 중복 정의를 구체적으로 찾아냈다.
- 수동 replan보다 app shell 분리와 theme authority 정리가 더 선명했다.

### T-03

- planner가 name-based helper가 아니라 `category.id` 기반 중앙 catalog로 계약을 옮겨야 한다고 정리했다.
- default seed set과 visual contract를 같은 catalog로 정렬해야 한다는 점이 수동 replan보다 더 명확했다.

### T-04

- planner가 실제 코드의 `onboarding_complete` vs `onboarding_completed` drift와 `/transactions`의 fake cycle id fallback을 주요 shared-contract 리스크로 잡았다.
- shared contract task로 분리한 판단이 타당하다는 강한 근거가 생겼다.

### T-05

- planner가 Home recent transaction row가 `categoryId`를 name-based visual helper에 넘기는 실제 mismatch를 발견했다.
- 수동 replan의 “screen-ready provider shape” 가설이 코드상 문제와 직접 연결됐다.

### T-06

- planner가 실제 route가 아직 legacy `TransactionsScreen`을 향하고 있다는 점을 잡았다.
- manual wave에서 생각했던 것보다 route swap이 먼저 필요하다는 근거가 생겼다.

### T-07

- planner가 `QuickExpenseFormState.copyWith()` nullable clear bug를 핵심 blocker로 특정했다.
- quick expense에서 Home prefetch coupling 제거도 명확한 구현 포인트로 드러났다.

### T-08

- planner가 onboarding key drift, legacy onboarding 경로 혼재, first-run cycle semantics 정리가 필요하다고 정리했다.
- `T-08`과 `T-10`의 경계를 “first-run setup” vs “settings mutation/reset”으로 나누는 현재 task split이 유효했다.

### T-10

- planner가 notification permission source split, reset에서 cycle 삭제 누락 가능성, onboarding reset/provider invalidation 문제를 구체화했다.
- 수동 replan보다 실제 상태 소스 정리가 더 중요한 선행 단계로 드러났다.

### T-11

- planner가 `integration_test/helpers/app_driver.dart` override가 real flow를 가린다고 판단했다.
- 이는 기존 시뮬레이션 단계에서 놓쳤던 핵심으로, integration runtime 자체가 source of false confidence라는 점을 보여줬다.

## Failed Task

### T-09

- 1차 상태: repeated hung -> shutdown
- 1차 관찰:
  - category management task는 feature 구현, dialog CRUD, list refresh, integration coverage가 한데 묶여 있어 planner 탐색이 길어졌다.
  - 같은 recovery pattern을 써도 `DONE/NEEDS_CONTEXT/BLOCKED`를 안정적으로 반환하지 못했다.
- 1차 해석:
  - `T-09`는 현재 planner skill/prompt 운영으로는 too-broad task였다.

### T-09 Split Recovery

- split 문서: [t09-split-replan.md](/Users/moon/Workspace/moondex/docs/examples/money-track-app-bootstrap-theme-raw-replan/t09-split-replan.md)
- split 결과:
  - `T-09A Category Management Screen Read Model And Section Composition` -> `DONE`
  - `T-09B Category Add/Edit Dialog Flow` -> `DONE`
  - `T-09C Category Delete Flow, Invalidation, And CRUD Regression` -> `DONE`
- 결론:
  - 문제는 category management 자체가 아니라 원래 `T-09`의 granularity였다.
  - 아래 분해는 planner-friendly한 단위로 동작했다.
    - `T-09A`: read/list composition
    - `T-09B`: add/edit mutation flow
    - `T-09C`: delete + regression
  - 따라서 이후 planning/wave 단계에서는 `T-09`를 단일 task로 유지하지 않는 편이 안전하다.

## Comparison To Manual Replan

- 수동 replan의 task boundary는 대체로 유효했다.
- 실제 planner dispatch는 수동 문서보다 더 구체적인 codebase risk를 드러냈다.
- 특히 아래는 실제 dispatch 덕분에 더 선명해졌다.
  - bootstrap seed source duplication
  - onboarding persistence key drift
  - legacy transactions route ownership
  - quick expense state bug
  - integration runtime override가 만드는 false confidence
- 반대로 `T-09`는 단일 task로는 planner-friendly 하지 않았고, `T-09A/B/C`로 분해했을 때는 정상 회수됐다.

## Next Steps

1. 회수된 `DONE` planner outputs를 기준으로 quality/readiness review를 수행한다.
2. reviewed plan set 기준으로 `wave-dispatcher` 단계로 넘어간다.
3. orchestration 문서에 planner timeout/retry/close policy를 운영 규칙으로 추가한다.
