# Stack Profile Schema

`stack-profile`은 대상 프로젝트의 기술 스택과 실행 표면을 Moondex 팀 구성에 사용할 수 있게 정리한 프로젝트별 계약이다.

기본 저장 위치:

```text
.moondex/team/stack-profile.json
```

`.moondex/team/`은 커밋 가능한 프로젝트 설정이다. `.moondex/state/`는 커밋하지 않는 런타임 상태다.

## Required Fields

```json
{
  "schema_version": "1",
  "project_name": "example",
  "generated_at": "2026-04-29T00:00:00Z",
  "confidence": "high",
  "languages": [],
  "frameworks": [],
  "package_managers": [],
  "test_tools": [],
  "runtime_surfaces": [],
  "contract_surfaces": [],
  "quality_gates": [],
  "detected_files": [],
  "unknown_signals": []
}
```

## Field Semantics

- `schema_version`: 현재는 `"1"`로 고정한다.
- `project_name`: 대상 repository 또는 product 이름.
- `generated_at`: ISO-8601 timestamp.
- `confidence`: `high`, `medium`, `low`, `unknown_with_signals` 중 하나.
- `languages`: Rust, TypeScript, Python, Dart, Go, Java 등.
- `frameworks`: React, Next.js, Flutter, Axum, FastAPI, Django, Spring 등.
- `package_managers`: cargo, npm, pnpm, yarn, pip, poetry, uv, pub, go, maven, gradle 등.
- `test_tools`: `cargo test`, `vitest`, `playwright`, `flutter test`, `pytest` 등.
- `runtime_surfaces`: `cli`, `web_ui`, `mobile_ui`, `api`, `worker`, `plugin`, `skill`, `mcp_server` 등.
- `contract_surfaces`: schema, migration, API route, CLI command, persisted state, archive format, plugin manifest 등.
- `quality_gates`: formatter, linter, typecheck, unit test, E2E, screenshot, install smoke 등.
- `detected_files`: profile 판단에 사용한 파일 경로.
- `unknown_signals`: 감지는 됐지만 해석하지 못한 파일, 명령, framework hint.

## Detection Guidance

우선 읽을 파일:

- `Cargo.toml`
- `package.json`
- `pnpm-lock.yaml`, `yarn.lock`, `package-lock.json`
- `pubspec.yaml`
- `pyproject.toml`
- `go.mod`
- `pom.xml`, `build.gradle`
- `.codex-plugin/plugin.json`
- `skills/*/SKILL.md`

manifest 이름만으로 결론을 내리지 않는다. script, dependency, directory shape, existing docs, test commands를 함께 본다.

## Example

```json
{
  "schema_version": "1",
  "project_name": "moondex",
  "generated_at": "2026-04-29T00:00:00Z",
  "confidence": "high",
  "languages": ["rust", "markdown"],
  "frameworks": [],
  "package_managers": ["cargo"],
  "test_tools": ["cargo fmt --check", "cargo test -p moondex", "cargo build -p moondex"],
  "runtime_surfaces": ["cli", "plugin", "skill"],
  "contract_surfaces": ["cli_command", "persisted_state", "plugin_manifest", "skill_contract"],
  "quality_gates": ["formatter", "unit_test", "build", "json_manifest_validation"],
  "detected_files": ["Cargo.toml", "crates/moondex/Cargo.toml", ".codex-plugin/plugin.json", "skills/moondex-runtime/SKILL.md"],
  "unknown_signals": []
}
```
