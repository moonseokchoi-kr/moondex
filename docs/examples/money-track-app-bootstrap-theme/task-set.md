# Task Set

```yaml
feature_name: app-bootstrap-and-theme
source_spec: /Users/moon/Workspace/money_track/docs/sdd/spec/2026-04-15-app-bootstrap-and-theme.md
source_design_arch: /Users/moon/Workspace/money_track/docs/sdd/design/arch/2026-04-15-app-bootstrap-and-theme.md
source_design_ui: /Users/moon/Workspace/money_track/docs/sdd/design/ui/2026-04-15-app-bootstrap-and-theme.md
source_develop_proxy: arch + context + existing task docs
```

## T-01 Database Bootstrap

- Goal: 앱 시작 시 DB 초기화와 16개 기본 카테고리 시딩을 안정적으로 수행한다.
- Non-Goals: 홈/거래 화면 재설계, theme 적용
- Dependencies: none
- Scope Notes:
  - 대상: `main.dart`, database initializer, database provider
  - 이유: 모든 후속 화면과 category data의 기반
- Success Conditions:
  - 첫 실행 시 시드됨
  - 재실행 시 중복 삽입되지 않음
  - 앱 시작이 non-fatal error에 막히지 않음

## T-02 Global Theme Infrastructure

- Goal: 전역 color, typography, component theme를 central theme module로 정리한다.
- Non-Goals: 개별 화면 pixel-perfect 구현
- Dependencies: T-01
- Scope Notes:
  - 대상: `lib/core/theme/`, `app.dart`, `pubspec.yaml`
  - 이유: 모든 후속 화면의 시각 규칙을 먼저 고정
- Success Conditions:
  - hardcoded color/font 제거 기준 마련
  - MaterialApp에서 공통 theme 사용

## T-03 Shared Category Visual Mapping

- Goal: 카테고리별 icon/background color 매핑을 중앙 모듈로 제공한다.
- Non-Goals: 카테고리 CRUD UI 구현
- Dependencies: T-02
- Scope Notes:
  - 대상: `lib/core/category/`
  - 이유: Home, Transactions, Quick Expense, Categories가 공유 사용
- Success Conditions:
  - 기본 카테고리 16개 매핑
  - custom category fallback 정의

## T-04 Home Screen Redesign

- Goal: Stitch canonical 기준의 홈 화면을 구현한다.
- Non-Goals: 거래 내역 전체 화면, 빠른 입력 modal
- Dependencies: T-01, T-02, T-03
- Scope Notes:
  - 대상: `lib/features/home/`
  - 이유: 가용 예산 중심 hero metric과 recent transaction UX를 독립적으로 검증 가능
- Success Conditions:
  - home provider + widget composition 완성
  - recent transactions, unclassified banner, CTA 연결

## T-05 Transactions Screen With Pagination

- Goal: 날짜 그룹핑과 DB pagination이 들어간 거래 내역 화면을 구현한다.
- Non-Goals: quick expense 입력 플로우
- Dependencies: T-01, T-02, T-03
- Scope Notes:
  - 대상: `lib/features/transaction_history/`
  - 이유: DB-level paging과 history UX를 별도 검증 필요
- Success Conditions:
  - LIMIT/OFFSET 기반 paging
  - date grouping
  - empty state와 filter 진입 지원

## T-06 Quick Expense 3-Step Modal

- Goal: amount -> category -> confirmation 3-step quick expense modal을 구현한다.
- Non-Goals: onboarding, settings
- Dependencies: T-01, T-02, T-03, T-04
- Scope Notes:
  - 대상: `lib/features/quick_expense/`
  - 이유: home CTA에서 진입하고 저장 후 home data invalidation이 필요
- Success Conditions:
  - 3-step 상태 관리
  - 저장 성공 후 home 반영

## T-07 Onboarding Flow Redesign

- Goal: permission, salary day, completion 3-step onboarding flow를 구현한다.
- Non-Goals: settings data reset
- Dependencies: T-01, T-02
- Scope Notes:
  - 대상: `lib/features/onboarding/`
  - 이유: cycle 생성과 첫 실행 가드가 다른 화면과 구분되는 별도 흐름
- Success Conditions:
  - onboarding provider + route gate
  - salary day 저장과 cycle 생성

## T-08 Category Management Screen

- Goal: 기본/커스텀 카테고리 관리 화면과 CRUD dialog를 구현한다.
- Non-Goals: settings 화면
- Dependencies: T-01, T-02, T-03
- Scope Notes:
  - 대상: `lib/features/category_management/`
  - 이유: shared category mapping을 실제 관리 UI와 연결
- Success Conditions:
  - add/edit/delete flow
  - provider invalidation

## T-09 Settings Screen Redesign

- Goal: salary day, notification permission, app info, reset data를 담은 settings 화면을 구현한다.
- Non-Goals: onboarding 자체 구현
- Dependencies: T-01, T-02
- Scope Notes:
  - 대상: `lib/features/cycle_management/`
  - 이유: settings는 onboarding과 연결되지만 별도 user journey를 가진다
- Success Conditions:
  - salary day change dialog
  - reset data -> onboarding reset

## T-10 E2E Validation And Polish

- Goal: F1-F9 범위의 통합 시나리오와 회귀 검증을 수행한다.
- Non-Goals: 신규 기능 추가
- Dependencies: T-01 ~ T-09
- Scope Notes:
  - 대상: `test/`, finder updates, final polish
  - 이유: redesign 후 navigation/finder/regression이 한 번에 깨질 가능성이 높음
- Success Conditions:
  - 핵심 end-to-end 시나리오 통과
  - analyze and regression check 정리
