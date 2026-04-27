# T-09 Split Replan

```yaml
parent_task: T-09
reason: repeated task-planner hangs
date: 2026-04-26
source_task_set: /Users/moon/Workspace/codex-moon-harness/docs/examples/money-track-app-bootstrap-theme-raw-replan/task-set.md
```

## Why Split

- 원래 `T-09`는 아래를 한 task에 같이 묶고 있었다.
  - categories screen read/list rendering
  - add/edit dialog mutation flow
  - delete confirmation + destructive mutation
  - mutation 후 list invalidation
  - integration coverage
- 실제 planner dispatch에서는 이 범위가 너무 넓어 반복적으로 hung 됐다.
- 현재 코드 구조도 이미 read/list와 add/edit/delete entry가 느슨하게 분리돼 있다.
  - `categories_screen.dart`
  - `default_categories_section.dart`
  - `custom_categories_section.dart`
  - `add_edit_category_dialog.dart`
  - `delete_confirmation_dialog.dart`

## Split Tasks

### T-09A Category Management Screen Read Model And Section Composition

- Goal: 기본/커스텀 카테고리 section 구분과 categories screen의 read path를 안정화한다.
- Non-Goals:
  - add/edit/delete mutation 수행
  - settings/reset flow
- Dependencies: `T-01`, `T-02`, `T-03`, `T-04`
- Scope:
  - `lib/features/category_management/presentation/screens/categories_screen.dart`
  - `lib/features/category_management/presentation/widgets/default_categories_section.dart`
  - `lib/features/category_management/presentation/widgets/custom_categories_section.dart`
  - `application/providers/category_providers.dart`
- Success Conditions:
  - default/custom section 구분이 안정적으로 렌더된다.
  - screen이 `categoriesProvider` read path만으로 구성된다.
  - empty/error/list state가 section contract를 깨지 않는다.

### T-09B Category Add/Edit Dialog Flow

- Goal: custom category add/edit dialog를 구현하고 mutation 성공 후 category list refresh contract를 고정한다.
- Non-Goals:
  - delete flow
  - home recent transactions UI
- Dependencies: `T-09A`
- Scope:
  - `lib/features/category_management/presentation/dialogs/add_edit_category_dialog.dart`
  - `lib/features/category_management/presentation/widgets/icon_color_picker.dart`
  - `categories_screen.dart`의 add/edit entry wiring
  - `addCategoryProvider`, `editCategoryProvider`
- Success Conditions:
  - custom category add/edit dialog가 동작한다.
  - 기본 카테고리에는 edit path가 열리지 않는다.
  - mutation 후 `categoriesProvider` invalidation이 보장된다.

### T-09C Category Delete Flow, Invalidation, And CRUD Regression

- Goal: custom category delete confirmation과 destructive mutation 후 refresh/integration regression을 고정한다.
- Non-Goals:
  - settings reset flow
  - category visual contract 자체 재설계
- Dependencies: `T-09A`, `T-09B`
- Scope:
  - `lib/features/category_management/presentation/dialogs/delete_confirmation_dialog.dart`
  - `categories_screen.dart`의 delete wiring
  - category management integration scenarios
- Success Conditions:
  - delete는 custom category에 대해서만 수행된다.
  - confirm/cancel path가 모두 안정적이다.
  - add/edit/delete 전체 CRUD path의 refresh regression이 test로 고정된다.

## Expected Benefit

- planner가 read path와 mutation path를 분리해서 더 짧은 탐색으로 끝낼 수 있다.
- implementer ownership도 더 명확해진다.
- `T-09C`에서만 integration/test burden을 집중시켜, 나머지 두 task는 executor-ready detail을 더 빨리 만들 수 있다.
