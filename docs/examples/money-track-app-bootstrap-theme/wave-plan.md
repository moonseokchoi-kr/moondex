# Wave Plan

```yaml
wave_plan_id: WAVE-app-bootstrap-and-theme
feature_name: app-bootstrap-and-theme
source_documents:
  spec: /Users/moon/Workspace/money_track/docs/sdd/spec/2026-04-15-app-bootstrap-and-theme.md
  design_arch: /Users/moon/Workspace/money_track/docs/sdd/design/arch/2026-04-15-app-bootstrap-and-theme.md
  design_ui: /Users/moon/Workspace/money_track/docs/sdd/design/ui/2026-04-15-app-bootstrap-and-theme.md
  develop_proxy: arch + context + existing task docs
planning_date: 2026-04-21
```

## Planning Summary

- 전체 구현 전략: foundation -> shared UI system -> shared category mapping -> feature screens -> cross-feature modal coupling -> final E2E 순서로 간다.
- 코드베이스 핵심 제약:
  - `main.dart` composition root 패턴 필요
  - hardcoded color/font 금지
  - transaction list는 DB-level pagination 필요
  - home와 quick expense는 save 후 invalidation coupling 존재
- 주요 가정:
  - 별도 단일 `develop` 문서는 없으므로 arch/context/task 문서에서 implementation design set을 복원한다.
  - single codebase owner지만, 문서상 parallel-safe 영역은 wave로 구분한다.

## Task And Plan List

| Task | Plan | Goal Summary | Owner Role | Priority |
|------|------|--------------|------------|----------|
| T-01 | P-T01 | bootstrap DB and seed default categories | implementer | high |
| T-02 | P-T02 | establish global theme system | implementer | high |
| T-03 | P-T03 | centralize category icon/color mapping | implementer | medium |
| T-04 | P-T04 | redesign home screen | implementer | high |
| T-05 | P-T05 | redesign transactions with pagination | implementer | high |
| T-06 | P-T06 | implement quick expense 3-step modal | implementer | high |
| T-07 | P-T07 | redesign onboarding flow | implementer | medium |
| T-08 | P-T08 | implement category management UI | implementer | medium |
| T-09 | P-T09 | redesign settings screen | implementer | medium |
| T-10 | P-T10 | run E2E validation and polish | reviewer/tester | high |

## Dependency Graph

```text
T-01 -> T-02 -> T-03
T-01 -> T-07
T-01 -> T-09
T-03 -> T-04
T-03 -> T-05
T-03 -> T-08
T-04 -> T-06
T-01,T-02,T-03,T-04,T-05,T-06,T-07,T-08,T-09 -> T-10
```

### Blocked Conditions

- T-02 blocked until DB/bootstrap entry path is stabilized enough to wire app theme cleanly.
- T-04/T-05/T-08 blocked until theme and category mapping are available.
- T-06 blocked until home CTA contract is settled.
- T-10 blocked until all feature tasks are complete.

## Wave Groups

- Wave 1:
  - T-01 / P-T01
  - 이유: 모든 후속 작업의 foundation

- Wave 2:
  - T-02 / P-T02
  - 이유: 후속 UI 작업의 공통 스타일 계약

- Wave 3:
  - T-03 / P-T03
  - 이유: category visuals shared dependency

- Wave 4:
  - T-04 / P-T04
  - T-05 / P-T05
  - T-07 / P-T07
  - T-08 / P-T08
  - T-09 / P-T09
  - 병렬 근거:
    - 서로 다른 feature 디렉터리 ownership
    - theme/category mapping이 선행 완료됨
  - 주의:
    - T-07, T-09는 shared onboarding/reset semantics가 있어 merge 시 route guard 충돌 확인 필요

- Wave 5:
  - T-06 / P-T06
  - 직렬 이유:
    - home CTA contract와 invalidation target이 T-04 결과에 직접 의존

- Wave 6:
  - T-10 / P-T10
  - 직렬 이유:
    - 전체 흐름 통합 검증

## Ownership Map

| Task | Allow | Deny | Shared Contract Change |
|------|-------|------|------------------------|
| T-01 | `lib/main.dart`, `lib/application/providers/database_provider.dart`, `lib/data/database/` | `lib/features/` | true |
| T-02 | `lib/core/theme/`, `lib/app/app.dart`, `pubspec.yaml` | feature screen internals | true |
| T-03 | `lib/core/category/` | feature presentation modules | true |
| T-04 | `lib/features/home/` | `lib/features/transaction_history/`, `lib/features/quick_expense/` | false |
| T-05 | `lib/features/transaction_history/` | `lib/features/home/` | false |
| T-06 | `lib/features/quick_expense/` | unrelated feature dirs | false |
| T-07 | `lib/features/onboarding/` | `lib/features/cycle_management/` | true |
| T-08 | `lib/features/category_management/` | `lib/features/home/` | false |
| T-09 | `lib/features/cycle_management/` | `lib/features/onboarding/` | true |
| T-10 | `test/` | product feature expansion | false |

## Verification Plan

### Task-Level Verification

- T-01: DB initialization unit/integration
- T-02: theme token tests + analyze
- T-03: category mapping unit tests
- T-04: home render/navigation test
- T-05: pagination and grouping test
- T-06: 3-step modal flow test
- T-07: onboarding flow test
- T-08: category CRUD flow test
- T-09: settings change/reset flow test
- T-10: integration_test suite + regression report

### Wave-Level Verification

- Wave 1: first-run bootstrap sanity
- Wave 2: theme applied without regressions
- Wave 3: category visuals render across at least one consumer
- Wave 4: feature screens compile and navigate independently
- Wave 5: quick expense updates home state correctly
- Wave 6: cross-flow E2E verification

### Final Integration Verification

- bootstrap -> onboarding -> home
- home -> quick expense -> home refresh
- home -> transactions
- home/settings/onboarding reset path
- categories CRUD stability after seeded categories

## Risk Notes

- 충돌 위험: route guard, provider invalidation, shared theme token rollout
- shared contract 위험: appDatabase provider wiring, home data shape, reset/onboarding semantics
- 테스트 누락 위험: finder updates after redesign
- 후속 조치:
  - implementation design set을 더 기계적으로 묶는 입력 포맷 정의
  - task-level plan generator가 ownership을 자동 추론할 수 있도록 코드베이스 스캔 규칙 보강
