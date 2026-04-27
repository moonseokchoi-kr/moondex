# Task Set

```yaml
feature_name: app-bootstrap-and-theme-raw-replan
source_spec: /Users/moon/Workspace/money_track/docs/sdd/spec/2026-04-15-app-bootstrap-and-theme.md
source_design_arch: /Users/moon/Workspace/money_track/docs/sdd/design/arch/2026-04-15-app-bootstrap-and-theme.md
source_design_api: /Users/moon/Workspace/money_track/docs/sdd/design/api/2026-04-15-app-bootstrap-and-theme.md
source_design_ui: /Users/moon/Workspace/money_track/docs/sdd/design/ui/2026-04-15-app-bootstrap-and-theme.md
comparison_target: /Users/moon/Workspace/money_track/docs/sdd/task/app-bootstrap-and-theme/
planning_mode: raw-input-first-planner-validated
```

## Replan Notes

- 이 task set은 기존 `money_track` task 문서를 source of truth로 삼지 않는다.
- `spec`, `design/arch`, `design/api`를 우선 입력으로 보고, 화면별 acceptance를 구체화할 때만 `design/ui`를 보조 참고한다.
- 기존 분해보다 개선하려는 핵심은 cross-feature contract를 별도 task로 분리하는 점이다.
- 특히 route gate, bottom navigation shell, Vault redirect, reset -> onboarding return path 같은 공통 동작은 개별 화면 task에 흩어두지 않는다.
- planner dispatch 검증 결과, category management는 단일 `T-09`보다 `T-09A/B/C` 분해가 더 안정적이었다.

## T-01 Composition Root And Database Bootstrap

- Goal: `main()`에서 AppDatabase를 초기화하고 기본 카테고리 16개를 idempotent하게 시드하며, `ProviderScope` override 기반의 composition root를 고정한다.
- Non-Goals:
  - 전역 theme 적용
  - feature screen 레이아웃 재설계
  - reset data flow 구현
- Dependencies: none
- Scope Notes:
  - 대상: `main.dart`, `lib/application/providers/database_provider.dart`, `lib/data/database/`, category initialization entry path
  - 이유: 모든 후속 feature가 DB availability와 default categories 존재를 전제로 한다.
- Success Conditions:
  - 첫 실행 시 기본 카테고리 16개가 시드된다.
  - 재실행 시 중복 삽입이 발생하지 않는다.
  - 초기화 오류가 앱 전체 startup fatal로 번지지 않는다.
  - 후속 task가 사용할 수 있는 injected database contract가 고정된다.

## T-02 Global Theme Token Infrastructure

- Goal: Stitch 디자인 토큰을 `lib/core/theme/`의 단일 authority로 내리고, `MaterialApp`이 이를 전역 theme로 사용하도록 고정한다.
- Non-Goals:
  - 개별 feature 화면의 pixel-level 레이아웃 구현
  - category icon/color mapping
- Dependencies: none
- Scope Notes:
  - 대상: `lib/core/theme/`, `lib/app/app.dart`, `pubspec.yaml`
  - 이유: 이후 UI task들이 hardcoded color/font 없이 같은 시각 계약을 상속해야 한다.
- Success Conditions:
  - `ColorScheme`, `TextTheme`, `ThemeExtension`, component theme entrypoint가 존재한다.
  - `google_fonts` Inter 기반 typography가 전역 theme에 연결된다.
  - 새로 건드리는 UI 코드에서 theme token 경로가 source of truth가 된다.

## T-03 Shared Category Visual Contract

- Goal: category ID를 icon/background color로 해석하는 shared mapping과 fallback 규칙을 중앙 모듈로 확정한다.
- Non-Goals:
  - category CRUD UI
  - feature별 consumer 화면 구현
- Dependencies: T-02
- Scope Notes:
  - 대상: `lib/core/category/`, mapping tests
  - 이유: Home, Transactions, Quick Expense, Categories가 동일한 시각 규칙을 공유해야 한다.
- Success Conditions:
  - 기본 카테고리 16개 mapping이 모두 정의된다.
  - custom category fallback이 명시된다.
  - 후속 feature가 동일 import 경로로 mapping을 소비할 수 있다.

## T-04 App Shell, Navigation, And Route Gate Contracts

- Goal: onboarding redirect, bottom navigation shell, Vault placeholder routing, settings/categories 진입 규칙을 공통 route contract로 고정한다.
- Non-Goals:
  - 각 feature 화면의 상세 widget tree 구현
  - salary day 저장 로직 자체 구현
- Dependencies: T-01, T-02
- Scope Notes:
  - 대상: `lib/core/routing/`, app shell wiring, bottom navigation state preservation contract
  - 이유: 홈/거래/설정/온보딩이 공유하는 navigation semantics를 화면 task마다 중복 정의하면 충돌이 생긴다.
- Success Conditions:
  - onboarding completion 전후 redirect rule이 문서와 코드에서 같은 의미를 가진다.
  - BottomNav 4-tab shell과 Vault redirect contract가 고정된다.
  - 설정에서 reset 후 onboarding으로 돌아가는 경로를 후속 task가 재사용 가능하다.

## T-05 Home Screen Redesign

- Goal: Stitch canonical 기준의 Home 화면을 구현하고, cycle/budget/recent transaction/unclassified banner/CTA를 하나의 coherent screen으로 연결한다.
- Non-Goals:
  - Quick Expense modal 내부 단계 구현
  - Transactions 전체 화면 구현
- Dependencies: T-01, T-02, T-03, T-04
- Scope Notes:
  - 대상: `lib/features/home/`
  - 이유: 앱의 핵심 landing screen이며 CTA와 banner가 다른 feature 진입 계약을 드러낸다.
- Success Conditions:
  - hero metric, 2x2 grid, unclassified banner, recent transactions, CTA bar가 canonical hierarchy에 맞게 렌더된다.
  - cycle/budget/recent transaction data shape가 provider 단에서 안정화된다.
  - quick expense, transactions, settings/navigation entry point가 shell contract와 맞게 연결된다.

## T-06 Transactions Screen And Paging Contract

- Goal: 날짜 그룹핑과 DB-level pagination을 갖는 Transactions 화면을 구현한다.
- Non-Goals:
  - Quick Expense 입력 플로우
  - category CRUD dialog
- Dependencies: T-01, T-02, T-03, T-04
- Scope Notes:
  - 대상: `lib/features/transaction_history/`
  - 이유: spec과 arch가 명시한 LIMIT/OFFSET paging contract를 별도 feature task로 검증해야 한다.
- Success Conditions:
  - in-memory sublist가 아닌 DB-level paging이 동작한다.
  - 날짜 그룹 헤더와 행 레이아웃이 canonical 요구사항을 만족한다.
  - empty state, scroll load, filter/search entry path가 깨지지 않는다.

## T-07 Quick Expense Modal And Home Invalidation

- Goal: amount -> category -> confirmation 3-step modal을 구현하고 저장 후 home state invalidation 계약을 완성한다.
- Non-Goals:
  - onboarding flow
  - settings reset flow
- Dependencies: T-01, T-02, T-03, T-04, T-05
- Scope Notes:
  - 대상: `lib/features/quick_expense/`
  - 이유: modal 자체는 독립 feature지만 save 후 home refresh coupling이 명시적 계약이다.
- Success Conditions:
  - 3-step state machine과 step indicator가 안정적으로 동작한다.
  - category recent-use, confirmation, memo 입력 흐름이 연결된다.
  - 저장 완료 후 home provider invalidation이 보장된다.

## T-08 Onboarding Flow And Salary Day Setup

- Goal: permission -> salary day -> completion 3-step onboarding과 cycle creation semantics를 구현한다.
- Non-Goals:
  - settings 화면에서의 salary day 변경
  - category management
- Dependencies: T-01, T-02, T-04
- Scope Notes:
  - 대상: `lib/features/onboarding/`, onboarding completion persistence, salary day setup use case
  - 이유: first-run gate와 cycle 생성은 별도 user journey이며 app shell contract와 직접 연결된다.
- Success Conditions:
  - onboarding step state와 completion persistence가 동작한다.
  - salary day 저장 시 cycle 생성/갱신 semantics가 고정된다.
  - route gate가 onboarding 상태와 일치한다.

## T-09A Category Management Screen Read Model And Section Composition

- Goal: 기본/커스텀 카테고리 section 구분과 categories screen의 read path를 안정화한다.
- Non-Goals:
  - add/edit/delete mutation 수행
  - settings reset flow
- Dependencies: T-01, T-02, T-03, T-04
- Scope Notes:
  - 대상: `lib/features/category_management/presentation/screens/`, `lib/features/category_management/presentation/widgets/`, `lib/application/providers/category_providers.dart`
  - 이유: category management의 read/list contract를 mutation flow와 분리해야 planner와 implementer 모두 더 안정적으로 처리할 수 있다.
- Success Conditions:
  - default/custom section 구분이 안정적으로 렌더된다.
  - `categoriesProvider` read path만으로 화면 구성이 설명된다.
  - loading/error/empty/list state가 section contract를 깨지 않는다.

## T-09B Category Add/Edit Dialog Flow

- Goal: custom category add/edit dialog를 구현하고 mutation 성공 후 category list refresh contract를 고정한다.
- Non-Goals:
  - delete flow
  - home recent transactions UI
- Dependencies: T-09A
- Scope Notes:
  - 대상: `lib/features/category_management/presentation/dialogs/add_edit_category_dialog.dart`, `icon_color_picker.dart`, `categories_screen.dart`, add/edit provider wiring
  - 이유: add/edit는 read/list보다 비동기 dialog lifecycle과 refresh semantics가 더 중요해서 별도 task로 분리한다.
- Success Conditions:
  - custom category add/edit dialog가 동작한다.
  - 기본 카테고리에는 edit path가 열리지 않는다.
  - mutation 후 `categoriesProvider` invalidation이 보장된다.

## T-09C Category Delete Flow, Invalidation, And CRUD Regression

- Goal: custom category delete confirmation과 destructive mutation 후 refresh/integration regression을 고정한다.
- Non-Goals:
  - settings reset flow
  - category visual contract 재설계
- Dependencies: T-09A, T-09B
- Scope Notes:
  - 대상: `delete_confirmation_dialog.dart`, delete wiring, category management integration scenarios
  - 이유: delete는 destructive flow이고, CRUD regression까지 같이 묶어야 실제 관리 화면 안정성을 검증할 수 있다.
- Success Conditions:
  - delete는 custom category에 대해서만 수행된다.
  - confirm/cancel path가 모두 안정적이다.
  - add/edit/delete 전체 CRUD path의 refresh regression이 test로 고정된다.

## T-10 Settings Screen, Salary Day Change, And Reset Return Path

- Goal: settings 화면에서 salary day 변경, notification permission 상태, reset data 후 onboarding 복귀 semantics를 구현한다.
- Non-Goals:
  - onboarding step UI 자체 구현
  - quick expense modal
- Dependencies: T-01, T-02, T-04
- Scope Notes:
  - 대상: `lib/features/cycle_management/`, salary day change flow, reset data use case
  - 이유: settings는 별도 화면이지만 onboarding/cycle/category reset semantics와 강하게 연결된다.
- Success Conditions:
  - salary day change dialog와 persistence가 동작한다.
  - notification permission 상태가 일관되게 표시된다.
  - reset data 수행 후 onboarding route gate와 다시 연결된다.
  - full end-to-end reset verification을 위해 T-08과 합쳐 검증할 수 있는 산출물이 남는다.

## T-11 Cross-Flow Validation, Review Escalation, And Regression

- Goal: F1-F10 전체를 통합 검증하고, code review/compliance review/tester가 필요한 지점을 정리하며 regression confidence를 확보한다.
- Non-Goals:
  - 신규 product feature 추가
  - architecture 방향 변경
- Dependencies: T-01, T-02, T-03, T-04, T-05, T-06, T-07, T-08, T-09A, T-09B, T-09C, T-10
- Scope Notes:
  - 대상: `test/`, integration scenarios, final polish, review notes
  - 이유: route gate, invalidation, paging, reset path처럼 cross-feature contract는 마지막 통합 검증 없이는 안전하지 않다.
- Success Conditions:
  - bootstrap -> onboarding -> home path가 통과한다.
  - home -> quick expense -> home refresh path가 통과한다.
  - transactions paging, category CRUD, settings reset path가 통과한다.
  - review chain에서 `compliance_review_required`가 필요한 task와 code-only로 끝나는 task가 구분 가능하다.

## Why This Decomposition Is Different

- 기존 generated task보다 `T-04 App Shell, Navigation, And Route Gate Contracts`를 별도 task로 분리했다.
- 이 분해는 onboarding redirect, Vault redirect, reset -> onboarding return path를 화면별 구현 task에 흩뿌리지 않기 위한 것이다.
- `T-11`은 단순 E2E 묶음이 아니라 cross-flow contract 검증과 review escalation 판단까지 포함한다.
- `T-09`는 실제 planner dispatch 검증 후 `T-09A/B/C`로 분해해 공식 task set에 반영했다.
- 따라서 이후 `plan set`에서는 screen task뿐 아니라 shared contract task의 ownership과 merge order를 더 명확히 드러낼 수 있다.
