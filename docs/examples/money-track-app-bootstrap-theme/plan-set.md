# Plan Set

이 문서는 `task-set.md`의 각 task를 `plan mode` 스타일의 executor-ready 실행계획으로 상세화한 샘플이다.

## P-T01 For T-01 Database Bootstrap

- Ownership:
  - allow: `lib/main.dart`, `lib/application/providers/database_provider.dart`, `lib/data/database/`, `test/data/database/`
  - deny: `lib/features/`
  - shared_contract_change: true
- Inputs/Outputs:
  - input: existing `AppDatabase`, `DatabaseInitializer`
  - output: initialized database instance, seeded default categories, provider override path
  - error: initialization failure should log and continue
- Execution Steps:
  - Step 1: `lib/data/database/database_initializer.dart`의 현재 초기화 경로와 시드 누락 지점을 확인한다.
    - 이유: 시드 로직을 먼저 고정해야 `main.dart` wiring 변경 범위를 줄일 수 있다.
    - 완료 기준: initialize 반환값과 first-run 판정 전략이 정리됨.
  - Step 2: `lib/application/providers/database_provider.dart`를 추가하고 override 포인트를 정의한다.
    - 이유: composition root와 provider injection 경계를 먼저 고정해야 한다.
    - 완료 기준: appDatabaseProvider가 main에서 override 가능한 상태.
  - Step 3: `lib/main.dart`에서 AppDatabase 생성 -> initialize 호출 -> ProviderScope override 순으로 배치한다.
    - 이유: startup 순서가 이 task의 핵심 계약이기 때문이다.
    - 완료 기준: graceful error handling 포함한 startup path 완성.
  - Step 4: `test/data/database/database_initializer_test.dart`로 first-run / re-run 시드 동작을 검증한다.
    - 이유: 중복 삽입 방지와 non-fatal 계약을 최종 확인해야 한다.
    - 완료 기준: 시드 관련 테스트 통과.
- Checkpoints/Fallbacks:
  - checkpoint: DB initialize 결과가 `Future<bool>`로 노출되는지 확인
  - blocked: 기존 initializer가 side-effect가 너무 커서 분리 불가능한 경우
  - fallback: main wiring 전, initializer contract만 먼저 확정하고 adapter layer를 둔다
- Acceptance:
  - first run seeds 16 categories
  - subsequent runs avoid duplicates
  - app startup remains non-fatal on init error
- Tests:
  - unit: initializer seeds exactly once
  - integration: first launch category availability
- Verification:
  - minimum: `flutter test test/data/database/database_initializer_test.dart`
  - full: `flutter analyze && flutter test`

## P-T02 For T-02 Global Theme Infrastructure

- Ownership:
  - allow: `lib/core/theme/`, `lib/app/app.dart`, `pubspec.yaml`
  - deny: `lib/features/**/screens/`
  - shared_contract_change: true
- Inputs/Outputs:
  - input: Stitch token definitions, Material 3 theme entrypoint
  - output: centralized theme data, Inter font wiring
  - error: missing dependency or token mismatch should fail fast in analyze/test
- Execution Steps:
  - Step 1: `.stitch/DESIGN.md`와 UI spec에서 색상/타이포/컴포넌트 토큰을 표로 추출한다.
  - Step 2: `lib/core/theme/`에 color scheme, text theme, theme extension, component theme를 분리 작성한다.
  - Step 3: `lib/app/app.dart`에 `buildMoneyTrackTheme()`를 연결한다.
  - Step 4: 새로 건드리는 feature 파일에서 hardcoded color/font를 theme 참조로 치환한다.
- Checkpoints/Fallbacks:
  - checkpoint: `pubspec.yaml`의 `google_fonts` 의존성 정상 resolve
  - blocked: 기존 화면이 theme 상속을 끊는 구조인 경우
  - fallback: full migration 전이라도 touched files에서만 hardcoded 제거를 강제
- Acceptance:
  - no new hardcoded color/font in touched files
  - MaterialApp uses shared theme
  - google_fonts dependency resolved
- Tests:
  - unit: color/token mapping
  - regression: theme build smoke test
- Verification:
  - minimum: `flutter test test/core/theme`
  - full: `flutter analyze && flutter test`

## P-T03 For T-03 Shared Category Visual Mapping

- Ownership:
  - allow: `lib/core/category/`, `test/core/category/`
  - deny: `lib/features/category_management/presentation/`
  - shared_contract_change: true
- Inputs/Outputs:
  - input: category IDs, design palette
  - output: icon/color resolver with fallback
  - error: unknown category should still resolve via fallback
- Execution Steps:
  - Step 1: spec/UI/design에서 기본 카테고리 16개와 시각 토큰을 확정한다.
  - Step 2: `lib/core/category/category_icon_mapping.dart`에 default mapping과 custom fallback을 작성한다.
  - Step 3: 최소 한 개 consumer에서 import path와 사용 패턴이 맞는지 확인한다.
- Checkpoints/Fallbacks:
  - checkpoint: 모든 default category ID가 unique mapping을 가진다
  - blocked: category ID source of truth가 불명확한 경우
  - fallback: display name 기반 임시 매핑 금지, ID source 먼저 확정
- Acceptance:
  - all 16 default categories mapped
  - custom category fallback works
  - mapping consumable from multiple features
- Tests:
  - unit: mapping coverage and fallback
- Verification:
  - minimum: `flutter test test/core/category`
  - full: `flutter analyze && flutter test`

## P-T04 For T-04 Home Screen Redesign

- Ownership:
  - allow: `lib/features/home/`
  - deny: `lib/features/transaction_history/`, `lib/features/quick_expense/`
  - shared_contract_change: false
- Inputs/Outputs:
  - input: home provider data, category mapping, theme
  - output: redesigned home screen with hero/grid/banner/recent list/CTA
  - error: empty state must render without crash
- Execution Steps:
  - Step 1: `home_provider.dart`에서 화면이 요구하는 data shape를 먼저 고정한다.
  - Step 2: `home_screen.dart`에 AppBar -> Hero -> Grid -> Banner -> Recent -> CTA skeleton을 먼저 세운다.
  - Step 3: `widgets/`로 hero/grid/banner/recent 섹션을 분리한다.
  - Step 4: quick expense/settings/history navigation을 연결한다.
  - Step 5: empty state와 unclassified conditional rendering을 검증한다.
- Checkpoints/Fallbacks:
  - checkpoint: Stitch hierarchy가 코드 레벨 widget tree에 반영됐는지 확인
  - blocked: home provider data shape가 repository 출력과 맞지 않는 경우
  - fallback: UI skeleton 우선, data adapter는 provider에 한정
- Acceptance:
  - Stitch hierarchy visible
  - unclassified banner conditional
  - CTA routes to quick expense/settings
- Tests:
  - widget or E2E: home render and navigation triggers
- Verification:
  - minimum: `flutter test test/features/home`
  - full: `flutter analyze && flutter test`

## P-T05 For T-05 Transactions Screen With Pagination

- Ownership:
  - allow: `lib/features/transaction_history/`
  - deny: `lib/features/home/`
  - shared_contract_change: false
- Inputs/Outputs:
  - input: transaction repository paging interface
  - output: paged date-grouped history screen
  - error: no in-memory sublist shortcut
- Acceptance:
  - DB-level paging
  - date grouping in UI
  - empty state and filter entry path
- Tests:
  - integration/E2E: paging, scroll load, filter path
- Verification:
  - minimum: `flutter test test/features/transaction_history`
  - full: `flutter analyze && flutter test`

## P-T06 For T-06 Quick Expense 3-Step Modal

- Ownership:
  - allow: `lib/features/quick_expense/`
  - deny: `lib/features/onboarding/`
  - shared_contract_change: false
- Inputs/Outputs:
  - input: home CTA entry, category mapping, create expense use case
  - output: 3-step modal with save and home invalidation
  - error: save failure must surface retry path
- Acceptance:
  - step indicator and 3-step progression
  - category selection and confirmation step
  - successful save updates home view
- Tests:
  - E2E: complete modal flow
- Verification:
  - minimum: `flutter test test/features/quick_expense`
  - full: `flutter analyze && flutter test`

## P-T07 For T-07 Onboarding Flow Redesign

- Ownership:
  - allow: `lib/features/onboarding/`
  - deny: `lib/features/cycle_management/`
  - shared_contract_change: true
- Inputs/Outputs:
  - input: notification permission status, salary day picker, cycle creation use case
  - output: onboarding state flow and completion gate
  - error: invalid salary day or permission denial should not crash flow
- Acceptance:
  - permission -> salary day -> completion flow
  - route guard for incomplete onboarding
  - salary day persists and creates cycle
- Tests:
  - E2E: first-run onboarding flow
- Verification:
  - minimum: `flutter test test/features/onboarding`
  - full: `flutter analyze && flutter test`

## P-T08 For T-08 Category Management Screen

- Ownership:
  - allow: `lib/features/category_management/`
  - deny: `lib/features/home/`
  - shared_contract_change: false
- Inputs/Outputs:
  - input: category repo CRUD, icon/color mapping
  - output: categorized list screen with dialogs
  - error: duplicate names and delete confirmation handled
- Acceptance:
  - default vs custom sections
  - add/edit/delete for custom categories only
  - list invalidation after mutation
- Tests:
  - E2E: CRUD flow
- Verification:
  - minimum: `flutter test test/features/category_management`
  - full: `flutter analyze && flutter test`

## P-T09 For T-09 Settings Screen Redesign

- Ownership:
  - allow: `lib/features/cycle_management/`
  - deny: `lib/features/onboarding/`
  - shared_contract_change: true
- Inputs/Outputs:
  - input: current salary day, notification permission state, app info, reset use case
  - output: settings screen with edit/reset flows
  - error: reset requires confirmation and safe redirection
- Acceptance:
  - salary day dialog
  - permission toggle
  - reset data sends user back to onboarding
- Tests:
  - E2E: settings flows
- Verification:
  - minimum: `flutter test test/features/cycle_management`
  - full: `flutter analyze && flutter test`

## P-T10 For T-10 E2E Validation And Polish

- Ownership:
  - allow: `test/`, finder updates across touched features
  - deny: new product feature work
  - shared_contract_change: false
- Inputs/Outputs:
  - input: completed feature flows
  - output: regression status, updated finders, final polish notes
  - error: failing scenarios must produce actionable report
- Acceptance:
  - core app bootstrap -> onboarding -> home path verified
  - home -> quick expense -> home update verified
  - history/categories/settings flows verified
- Tests:
  - E2E + regression suite
- Verification:
  - minimum: `flutter test integration_test`
  - full: `flutter analyze && flutter test && flutter test integration_test`
