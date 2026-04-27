# Execution Test Review

```yaml
feature_name: app-bootstrap-and-theme-raw-replan
review_date: 2026-04-26
review_scope: actual flutter test execution against /Users/moon/Workspace/money_track
```

## Summary

- 실제 `flutter test`를 돌려 planning 산출물을 현재 `money_track` 코드베이스에 대입해 봤다.
- 초기 상태에서는 `T-01`, `T-07`, `T-09A`, `T-09B`, `T-09C`, `T-10`이 codegen/schema drift 때문에 컴파일 단계에서 막혔다.
- 실제 구현 단계에서 `flutter pub run build_runner build --delete-conflicting-outputs`를 실행해 `freezed`, `drift`, `riverpod` 생성물을 복구했다.
- 복구 후 `T-01`, `T-02`, `T-03`, `T-05`, `T-06`, `T-07`, `T-08`, `T-09A`, `T-09B`, `T-09C`, `T-10`은 현재 있는 최소 검증 자산 기준으로 통과했다.
- `T-04`, `T-11`은 현재 repo에 task 전용 테스트 타깃이 없다.

## Task Results

| Task | Test Command | Result | Notes |
| --- | --- | --- | --- |
| `T-01` | `flutter test test/data/database/database_initializer_test.dart` | pass | codegen 복구 후 pass |
| `T-02` | `flutter test test/core/theme/theme_data_test.dart` | pass | theme token/task contract는 현재 테스트 자산 기준 통과 |
| `T-03` | `flutter test test/core/category/category_icon_mapping_test.dart` | pass | shared category visual contract 통과 |
| `T-04` | n/a | gap | `test/core/routing` 없음 |
| `T-05` | `flutter test test/features/home/home_widgets_test.dart` | pass | home widget smoke는 통과 |
| `T-06` | `flutter test test/data/repositories/transaction_repository_impl_test.dart` | pass | repository/paging 레벨 검증만 있음 |
| `T-07` | `flutter test test/domain/usecases/create_quick_expense_usecase_test.dart` | pass | codegen 복구 후 pass |
| `T-08` | `flutter test test/domain/usecases/set_salary_day_usecase_test.dart` | pass | salary day/cycle semantics usecase 레벨 통과 |
| `T-09A` | `flutter test test/domain/usecases/get_categories_usecase_test.dart` | pass | codegen 복구 후 pass |
| `T-09B` | `flutter test test/domain/usecases/add_category_usecase_test.dart` | pass | codegen 복구 후 pass |
| `T-09C` | `flutter test test/domain/usecases/delete_category_usecase_test.dart` | pass | codegen 복구 후 pass |
| `T-10` | `flutter test test/features/cycle_management/presentation/screens/settings_screen_test.dart` | pass | codegen 복구 후 settings test pass, `reset_data_usecase_test`도 pass |
| `T-11` | n/a | gap | `integration_test/` 없음 |

## Findings

1. High: 실제 구현 첫 단계는 기능 코드 수정이 아니라 codegen 복구였다. [category.dart](/Users/moon/Workspace/money_track/lib/domain/entities/category.dart:19)와 생성물 사이의 mismatch, drift schema 생성물 누락, riverpod part 누락이 한 번에 묶여 있어서, 이 레이어를 복구하지 않으면 task-level execution 검증이 불가능했다.

2. High: codegen 복구 후 `T-10` 자체 blocker는 사라졌다. settings widget test와 reset/salary-day usecase test가 모두 통과했으므로, 현재 계획 기준에서 `T-10`은 “implementation-blocked” 상태가 아니라 “더 깊은 journey test가 없을 뿐 기본 task 경로는 실행 가능” 상태로 보는 게 맞다.

3. Medium: `T-04`와 `T-11`은 여전히 coverage gap이다. 이 둘은 기존 구현과의 부정합보다 단순히 현재 repo에 routing/integration 타깃이 비어 있다는 문제가 더 크다.

4. Medium: `T-06`과 `T-08`은 가장 가까운 repository/usecase 테스트는 통과했지만, screen/journey 레벨 readiness는 아직 입증되지 않았다. Transactions는 repository paging까지만, onboarding/settings는 salary day usecase까지만 확인된 상태다.

## Plan Corrections

- `plan-set.md`의 최소 검증 명령을 현재 실제로 존재하는 테스트 파일 기준으로 교정했다.
- `T-04`와 `T-11`에는 현재 coverage gap을 명시했다.
- category cluster는 `T-09A/B/C` 각각에 대해 실제 실행 가능한 테스트를 연결했다.

## Recommended Next Fix Order

1. `T-04` routing shell 검증용 `test/core/routing` 타깃을 추가한다.
2. `T-11` cross-flow 검증용 `integration_test/` 타깃을 추가한다.
3. Transactions, onboarding/settings에 screen/journey 레벨 테스트를 보강한다.
