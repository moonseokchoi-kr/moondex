# Stack-Aware Team Composition

Moondex team designer는 플러그인이 설치된 대상 프로젝트의 기술 스택을 읽고, 프로젝트별 팀 설정을 생성한다.

## Source Of Truth

팀 설정과 런타임 상태는 분리한다.

```text
.moondex/team/   # committed project configuration
.moondex/state/  # uncommitted runtime state
```

`.moondex/team/`은 Moondex CLI가 나중에 읽을 durable config다. `.moondex/state/`는 task, role, mailbox, dispatch, event log가 들어가는 runtime source of truth다.

## Generated Layout

대상 프로젝트에 생성되는 기본 구조:

```text
.moondex/team/
  stack-profile.json
  team-spec.json
  README.md
  verification-plan.md
  members/
    implementer.md
    code-reviewer.md
    compliance-reviewer.md
    tester.md
_workspace/moondex-team/
  role-selection-matrix.md
  generation-notes.md
```

`members/`에는 선택된 role 또는 사용할 수 있는 role만 둔다. 특정 role이 아직 팀에 포함되지 않으면 `team-spec.json`의 escalation rule과 `README.md`에 추가 조건을 남긴다.

## Gitignore Policy

대상 프로젝트가 `.moondex/` 전체를 무시하면 팀 설정도 커밋되지 않는다. 이 경우 아래 형태로 분리한다.

```gitignore
.moondex/*
!.moondex/team/
!.moondex/team/**
.moondex/state/
```

기존 `.moondex/state/` ignore는 유지한다. `.moondex/team/`만 커밋 가능한 설정으로 예외 처리한다.

## Team Selection Policy

최소 팀:

```text
implementer -> code-reviewer
```

추가 조건:

- `compliance-reviewer`: persisted state, schema, API, CLI contract, archive behavior, plugin manifest, policy, cross-role handoff contract.
- `tester`: UI, E2E, external IO, mobile/platform behavior, deployment, installation, user-critical workflow.

기술 전문성은 role 이름이 아니라 `specialist_lenses`로 표현한다.

예:

| Project Signal | Specialist Lenses | Checks |
| --- | --- | --- |
| Rust CLI/runtime | `rust_runtime`, `cli_contract`, `state_audit` | `cargo fmt --check`, `cargo test`, CLI smoke |
| React/Next web UI | `frontend_ui_accessibility`, `browser_e2e` | typecheck, unit test, Playwright screenshot |
| Flutter app | `flutter_widget_platform` | `dart format`, `flutter test`, device smoke |
| Python API/data | `python_api_schema`, `data_pipeline` | `pytest`, fixture/contract smoke |
| Plugin/skill package | `plugin_packaging`, `skill_authoring` | manifest validation, install/discovery smoke |

## v1 Boundary

v1은 skill-driven generation이다. Rust CLI는 아직 생성하거나 적용하지 않는다.

v2 후보:

```bash
moondex api inspect-stack --json
moondex api propose-team --json
moondex api apply-team --input '{"team_spec_path":".moondex/team/team-spec.json"}' --json
```

`inspect-stack`과 `propose-team`은 non-mutating이어야 한다. `apply-team`은 team spec 계약이 실제 프로젝트에서 충분히 검증된 뒤 추가한다.

