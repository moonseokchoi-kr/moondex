# Wave Plan

```yaml
wave_plan_id: WAVE-app-bootstrap-and-theme-raw-replan
feature_name: app-bootstrap-and-theme-raw-replan
source_documents:
  spec: /Users/moon/Workspace/money_track/docs/sdd/spec/2026-04-15-app-bootstrap-and-theme.md
  design_arch: /Users/moon/Workspace/money_track/docs/sdd/design/arch/2026-04-15-app-bootstrap-and-theme.md
  design_api: /Users/moon/Workspace/money_track/docs/sdd/design/api/2026-04-15-app-bootstrap-and-theme.md
  design_ui: /Users/moon/Workspace/money_track/docs/sdd/design/ui/2026-04-15-app-bootstrap-and-theme.md
planning_date: 2026-04-26
planning_mode: raw-input-first-planner-validated
comparison_target: /Users/moon/Workspace/money_track/docs/sdd/task/app-bootstrap-and-theme/
```

## Planning Summary

- 전체 구현 전략: foundation bootstrap/theme -> shared visual + shell contracts -> screen implementation -> cross-feature coupling tasks -> final regression 순서로 간다.
- 이번 replan의 핵심 차이:
  - navigation shell, onboarding gate, Vault redirect, reset return path를 별도 shared-contract task로 분리했다.
  - final validation task는 단순 E2E가 아니라 review escalation 판단 자료까지 포함한다.
  - task 단계에서는 병렬 가능해 보이던 항목 중 일부를 plan 검토 후 직렬로 강등했다.
- 코드베이스 핵심 제약:
  - `main.dart` composition root 선행 필요
  - 전역 theme token authority가 먼저 있어야 후속 screen 작업에서 hardcoded style drift를 막을 수 있다
  - Transactions는 DB-level pagination을 반드시 사용해야 한다
  - Home / Quick Expense / Settings / Onboarding은 route gate와 invalidation contract를 공유한다
- 주요 가정:
  - raw input 문서만으로도 task/plan/wave를 복원할 수 있다
  - 기존 `money_track` task 문서는 비교 기준일 뿐 source of truth가 아니다
  - reviewer/tester dispatch 판단은 plan 검토 결과를 기준으로 내려진다

## Task And Plan List

| Task | Plan | Goal Summary | Owner Role | Priority |
|------|------|--------------|------------|----------|
| T-01 | P-T01 | bootstrap DB and seed default categories | implementer | high |
| T-02 | P-T02 | establish global theme token authority | implementer | high |
| T-03 | P-T03 | centralize category icon/color mapping | implementer | medium |
| T-04 | P-T04 | fix shell routing, onboarding gate, Vault redirect, reset return path contracts | implementer | high |
| T-05 | P-T05 | redesign Home screen around canonical hierarchy | implementer | high |
| T-06 | P-T06 | implement Transactions with DB-level paging | implementer | high |
| T-07 | P-T07 | implement Quick Expense modal and Home invalidation | implementer | high |
| T-08 | P-T08 | implement onboarding 3-step flow and salary day setup | implementer | high |
| T-09A | P-T09A | stabilize category management read/list composition | implementer | medium |
| T-09B | P-T09B | implement category add/edit dialog flow | implementer | medium |
| T-09C | P-T09C | implement category delete flow and CRUD regression | implementer | medium |
| T-10 | P-T10 | implement settings edit/reset flows | implementer | high |
| T-11 | P-T11 | run cross-flow regression and review escalation validation | implementer | high |

## Dependency Graph

```text
T-01 -> T-04
T-02 -> T-03
T-02 -> T-04
T-03 -> T-05
T-03 -> T-06
T-03 -> T-07
T-03 -> T-09A
T-04 -> T-05
T-04 -> T-06
T-04 -> T-08
T-04 -> T-09A
T-04 -> T-10
T-05 -> T-07
T-08 -> T-10
T-09A -> T-09B
T-09A,T-09B -> T-09C
T-01,T-02,T-03,T-04,T-05,T-06,T-07,T-08,T-09A,T-09B,T-09C,T-10 -> T-11
```

### Notes On Dependency Downgrades/Upgrades

- task set 기준으로 T-10은 T-08에 직접 의존하지 않는 것처럼 보일 수 있었지만, plan 검토 후 `reset -> onboarding return path` 때문에 `T-08 -> T-10` 의존성을 명시했다.
- T-04를 별도 shell contract task로 분리하면서, Home/Transactions/Onboarding/Settings는 개별 화면 task 전에 공통 navigation semantics를 먼저 확정하게 되었다.
- T-07은 단순 modal task가 아니라 Home invalidation contract를 포함하므로 `T-05 -> T-07` 직렬 유지가 필요하다.

### Blocked Conditions

- T-03 blocked until theme token authority is usable enough to align category colors.
- T-04 blocked until composition root and global theme entrypoint are stabilized.
- T-05/T-06/T-09A blocked until shared shell and shared category contracts are available.
- T-09B blocked until T-09A read/list composition is stable.
- T-09C blocked until T-09A/T-09B establish screen and add/edit baseline.
- T-10 blocked until onboarding semantics from T-08 are stable enough to define reset return behavior.
- T-11 blocked until all feature and shared-contract tasks are complete.

## Wave Groups

- Wave 1:
  - T-01 / P-T01
  - T-02 / P-T02
  - 병렬 근거:
    - `main.dart`/database bootstrap와 `lib/core/theme/`은 write surface가 분리된다.
    - 둘 다 foundation task지만 직접 파일 충돌은 낮다.
  - 주의:
    - T-02가 app entrypoint (`lib/app/app.dart`)를 건드리므로 T-01의 startup wiring과 merge 순서 확인 필요

- Wave 2:
  - T-03 / P-T03
  - T-04 / P-T04
  - 병렬 근거:
    - category visual contract와 shell/routing contract는 서로 다른 shared module을 중심으로 변경한다.
    - 둘 다 foundation 이후의 shared contract지만 direct write overlap은 작다.
  - 주의:
    - app-wide semantics를 동시에 바꾸므로 merge 시 app startup, route shell, theme/category import cohesion 점검 필요

- Wave 3:
  - T-05 / P-T05
  - T-06 / P-T06
  - T-08 / P-T08
  - T-09A / P-T09A
  - 병렬 근거:
    - feature directory ownership이 분리된다.
    - T-03/T-04가 선행돼 visual contract와 route shell contract가 고정된다.
  - 직렬 강등된 항목:
    - T-10은 원래 T-08과 병렬 가능 후보였지만, reset -> onboarding return semantics 때문에 다음 wave로 강등한다.
  - 주의:
    - T-08은 route gate semantics를 소비하므로 shell contract drift가 있으면 먼저 멈춰야 한다.

- Wave 4:
  - T-07 / P-T07
  - T-09B / P-T09B
  - T-10 / P-T10
  - 병렬 근거:
    - T-07은 Home coupling, T-09B는 category add/edit dialog, T-10은 Settings/reset semantics 중심이라 주 write surface가 분리된다.
    - T-07은 T-05 완료 후, T-09B는 T-09A 완료 후, T-10은 T-08 완료 후 시작할 수 있다.
  - 주의:
    - 셋 다 route/invalidation side effect를 가질 수 있으므로 merge 후 shell/category regression check가 필요하다.

- Wave 5:
  - T-09C / P-T09C
  - 직렬 이유:
    - category delete와 CRUD regression은 T-09A/T-09B 결과 위에서만 안전하게 고정할 수 있다.

- Wave 6:
  - T-11 / P-T11
  - 직렬 이유:
    - 전체 cross-flow contract 검증과 review escalation note는 모든 prior task 결과를 입력으로 받아야 한다.

## Ownership Map

| Task | Allow | Deny | Shared Contract Change |
|------|-------|------|------------------------|
| T-01 | `lib/main.dart`, `lib/application/providers/database_provider.dart`, `lib/data/database/`, `test/data/database/` | `lib/features/`, `lib/core/theme/` | true |
| T-02 | `lib/core/theme/`, `lib/app/app.dart`, `pubspec.yaml`, theme tests | feature screen broad rewrites | true |
| T-03 | `lib/core/category/`, `test/core/category/` | feature presentation modules | true |
| T-04 | `lib/core/routing/`, shell-level entry files, routing tests | feature-internal widget trees | true |
| T-05 | `lib/features/home/` | `lib/features/transaction_history/`, `lib/features/quick_expense/`, shell routing files | false |
| T-06 | `lib/features/transaction_history/` | `lib/features/home/`, `lib/features/quick_expense/` | false |
| T-07 | `lib/features/quick_expense/` | `lib/features/onboarding/`, `lib/features/cycle_management/` | false |
| T-08 | `lib/features/onboarding/`, onboarding application logic | `lib/features/cycle_management/` | true |
| T-09A | `lib/features/category_management/presentation/screens/`, `lib/features/category_management/presentation/widgets/`, `lib/application/providers/category_providers.dart` | category dialogs, home, transaction history | false |
| T-09B | add/edit dialog, icon picker, category screen add/edit wiring | delete dialog, home, transaction history | false |
| T-09C | delete dialog, delete wiring, category integration tests | default section, settings flows | false |
| T-10 | `lib/features/cycle_management/`, settings application logic | `lib/features/onboarding/` screen internals | true |
| T-11 | `test/`, finder updates, polish notes across touched paths | broad product scope expansion | false |

### Conflict Notes

- T-01/T-02는 서로 다른 핵심 파일을 건드리지만 app startup surface에서 만난다.
- T-04는 shell contract를 바꾸므로 downstream feature task와 같은 wave에 두지 않는다.
- T-08/T-10은 온보딩/리셋 semantics를 공유하므로 write paths가 달라도 semantic conflict risk가 높다.
- T-09A/B/C는 같은 feature를 나눠 가진 직렬 cluster라, 병렬 구현보다 handoff 품질이 더 중요하다.
- T-11은 broad write set을 갖지만 final wave로 고정해 충돌을 피한다.

## Verification Plan

### Task-Level Verification

- T-01: initializer first-run/re-run/error behavior
- T-02: theme token mapping and theme build smoke
- T-03: category mapping coverage and fallback
- T-04: routing and tab preservation tests
- T-05: Home render, major section visibility, CTA/navigation
- T-06: paging, scroll load, filter path
- T-07: quick expense 3-step flow, save, Home refresh
- T-08: onboarding flow, salary day persistence, route gate
- T-09A: category read/list composition
- T-09B: add/edit dialog flow and refresh
- T-09C: delete confirm/cancel and CRUD regression
- T-10: settings salary day change, permission state, reset return path
- T-11: integration matrix + escalation note

### Wave-Level Verification

- Wave 1: app boots with initialized DB and global theme enabled
- Wave 2: shell routing and shared category visuals are usable by downstream features
- Wave 3: Home/Transactions/Onboarding/Categories read path compile and navigate independently under the shared shell
- Wave 4: quick expense invalidates Home correctly, category add/edit refreshes, settings reset returns to onboarding deterministically
- Wave 5: category delete and CRUD regression are locked
- Wave 6: full cross-flow regression suite and review escalation summary

### Final Integration Verification

- bootstrap -> onboarding -> home
- home -> quick expense -> home refresh
- home -> transactions pagination path
- categories read/add/edit/delete after seeded defaults
- settings -> reset -> onboarding -> home re-entry
- route shell tab preservation through feature navigation

## Risk Notes

- 충돌 위험:
  - startup wiring vs app theme wiring at app entry
  - shell contract drift affecting multiple features
  - onboarding/reset semantic mismatch between T-08 and T-10
  - Home invalidation race in T-07
- shared contract 위험:
  - appDatabase provider injection
  - route gate and shell navigation semantics
  - category visual mapping source-of-truth
  - reset return path
- 테스트 누락 위험:
  - tab preservation
  - reset 이후 재진입 path
  - transactions paging regression
  - quick expense save 후 stale Home state
- 후속 조치 필요 사항:
  - raw-input-based `compliance_review_required` checklist를 별도 artifact로 뽑기
  - old money_track task set과 새 task/plan/wave의 차이를 비교하는 review 문서 작성
  - `T-04` shell contract를 payload 수준의 role transfer contract 예시로 내리기
