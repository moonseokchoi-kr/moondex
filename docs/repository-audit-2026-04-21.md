# Repository Audit 2026-04-21

이 문서는 `executor-first` 방향을 기준으로 현재 저장소 파일을 평가한 결과다.

판정 기준은 파일명이나 SDD 인상이 아니라 아래 하나다.

`이 파일이 executor 입력 계약, readiness 판단, 실행 안정성에 실제로 기여하는가`

## Summary

### Keep

- `.codex-plugin/plugin.json`
- `.gitignore`
- `README.md`
- `docs/executor-direction.md`

### Remove

- `skills/sdd/SKILL.md`
- `scripts/sdd/init_pipeline.py`
- `scripts/sdd/update_pipeline.py`
- `scripts/sdd/show_pipeline.py`
- `scripts/sdd/check_phase.py`
- `docs/sdd/README.md`
- `docs/sdd/templates/spec-template.md`
- `docs/sdd/templates/task-template.md`
- `docs/sdd/spec/.gitkeep`
- `docs/sdd/context/.gitkeep`
- `docs/sdd/task/.gitkeep`
- `docs/sdd/result/.gitkeep`

## File Decisions

### Keep

#### `.codex-plugin/plugin.json`

- 현재 문제: 플러그인 루트 식별
- 판단: executor 방향과 충돌하지 않음
- 조치: 유지

#### `.gitignore`

- 현재 문제: 로컬 산출물 정리
- 판단: 방향 비의존적
- 조치: 유지

#### `README.md`

- 현재 문제: 저장소 진입 설명
- 판단: 필요하지만 내용은 executor 방향으로 수정 필요
- 조치: 유지 후 재작성

#### `docs/executor-direction.md`

- 현재 문제: 방향 기준 부재
- 판단: 현재 저장소의 핵심 기준 문서
- 조치: 유지 및 이후 변경 시 먼저 갱신

### Remove

#### `skills/sdd/SKILL.md`

- 현재 문제: Codex가 SDD 전체를 주도하는 절차를 설명
- 판단: executor 역할보다 상위 설계 흐름을 전제함
- 조치: 삭제

#### `scripts/sdd/*`

- 현재 문제: phase 상태 머신과 문서 진행 추적
- 판단: 현재 방향의 핵심은 phase 전진이 아니라 task readiness 검증
- 조치: 삭제

#### `docs/sdd/*`

- 현재 문제: spec/design/plan/execute 전체 구조를 Codex 저장소 기본 구조로 고정
- 판단: executor 입력 계약보다 상위 워크플로우 흔적이 강함
- 조치: 삭제

## Replacement Structure

삭제 후 아래 구조를 중심으로 재편한다.

- `docs/contracts/task-schema.md`
- `docs/contracts/plan-schema.md`
- `docs/contracts/wave-schema.md`
- `docs/execution/task-readiness-gate.md`
- `docs/execution/executor-checklist.md`

## Decision Note

`legacy SDD prototype`에서 남길 것은 전체 SDD 스캐폴드가 아니라 아래 개념이다.

- task packet 품질
- dependency와 ownership 명시
- DAG/Wave 기반 병렬 실행 관점
- 결과적으로 executor가 추가 설계 없이 움직일 수 있는 입력 계약
