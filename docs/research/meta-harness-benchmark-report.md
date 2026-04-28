# Meta Harness 벤치마크 보고서

작성일: 2026-04-28

소스 저장소: `https://github.com/SaehwanPark/meta-harness`

분석에 사용한 임시 클론: `/tmp/moondex-meta-harness-analysis`

## 요약

`meta-harness`는 Moondex에 기술 스택 기반 팀 구성, 지속 가능한 핸드오프 산출물, 검증 시나리오를 평가하는 벤치마크 프레임워크로 가장 유용하다. Moondex의 런타임 아키텍처로 그대로 복사해서는 안 된다.

Moondex는 이미 `meta-harness`보다 강한 런타임 강제 수단을 갖고 있다. 예를 들어 task phase, lease, dispatch, mailbox contract, readiness validation, hook wrapper, event log, archive policy, cmux role surface가 있다. 따라서 유용한 벤치마크 대상은 런타임 구조가 아니라 팀 설계 정책 품질이다. 즉, 저장소의 언어, 프레임워크, 테스트 도구, 배포 표면을 읽고 어떤 specialist role을 구성할지, task나 wave가 어떤 패턴을 써야 하는지, 어떤 핸드오프 산출물이 반드시 있어야 하는지, 정상 흐름과 실패 흐름을 어떻게 검증할지를 평가해야 한다.

## Meta Harness가 제공하는 것

상위 저장소는 repo-local agent workflow를 설계하기 위한 이식 가능한 meta-skill 패키지다. 대부분은 문서이며, 작은 Python 설치 스크립트와 검증 스크립트가 포함되어 있다.

주요 구성 요소:

- `AGENTS.md`: 의도적으로 짧게 작성된 저장소 전체 지침.
- `.agents/skills/harness/SKILL.md`: 도메인 workflow, specialist skill, team spec, 결정적 핸드오프 산출물을 설계하는 핵심 skill.
- `.agents/skills/harness/references/`: architecture pattern, AGENTS 작성, skill 작성/테스트, QA, autonomous experimentation, team example, orchestrator template을 progressive disclosure 방식으로 제공하는 참고 문서.
- `docs/harness/README.md`: team spec, role brief, `_workspace/` handoff, experiment ledger를 위한 생성 산출물 계약.
- `docs/harness/starter-research/team-spec.md`: 역할, workflow, 실패 정책, 검증을 포함한 최소 research team spec.
- `scripts/install_harness.py`: 표준 skill tree를 project scope 또는 user scope에 설치.
- `scripts/test_install_harness.py`: installer 동작 smoke test.
- `scripts/validate_codex_port.py`: 필수 파일, 링크, skill frontmatter, heading, pattern coverage, 금지된 legacy token을 검증.

## Workflow 벤치마크

`meta-harness`는 6단계 workflow를 사용한다.

1. Domain Analysis
2. Team Architecture Design
3. Role and Artifact Definition Generation
4. Skill Generation
5. Integration and Orchestration
6. Validation and Testing

Moondex는 이를 `.moondex/state`의 대체물이 아니라 정책 설계 루프의 벤치마크로 삼아야 한다.

권장 Moondex 매핑:

| Meta Harness 단계 | Moondex 대응 항목 |
| --- | --- |
| Domain Analysis | task/readiness 분석, task planner 입력 품질 |
| Team Architecture Design | 기술 스택에 맞는 specialist team, role chain, wave pattern 선택 |
| Role and Artifact Definition | task/plan/wave와 role mailbox contract |
| Skill Generation | 재사용성이 있을 때만 선택적으로 만드는 Moondex specialist skill |
| Integration and Orchestration | `next-action`, `orchestrator-step`, `orchestrator-loop`, dispatch 및 mailbox state |
| Validation and Testing | validator 결과, event log, audit-state, benchmark scenario 결과 |

## Architecture Pattern 매핑

Moondex는 상위 저장소의 6개 패턴을 role composition vocabulary로 사용할 수 있다.

| Pattern | Moondex에서의 사용 |
| --- | --- |
| Pipeline | `task -> plan -> wave -> implementation -> review -> optional compliance/test` |
| Fan-out/Fan-in | 독립적인 wave task, planner pool, 병렬 review angle, 이후 synthesis |
| Expert Pool | 조건부 `compliance-reviewer`, `tester`, 또는 향후 domain specialist |
| Producer-Reviewer | 제한된 revision 범위를 갖는 `implementer -> code-reviewer` |
| Supervisor | backlog, lease, stale role, retry, archive, phase transfer를 관리하는 orchestrator |
| Hierarchical Delegation | 도메인 분할에만 제한적으로 사용하고 coordination은 얕게 유지 |

가장 즉시 적용하기 좋은 조합은 `Expert Pool`과 `Producer-Reviewer`다. Moondex에는 이미 고정 runtime role이 있으므로, 벤치마크는 그 위에 어떤 기술 스택별 specialist lens를 얹을지 검증해야 한다. 예를 들어 같은 `code-reviewer`라도 Rust CLI, React UI, Flutter 앱, Python data pipeline에서는 확인해야 할 위험과 검증 명령이 다르다.

## 기술 스택 기반 팀 구성

사용자의 적용점은 generic agent team이 아니라 project-aware specialist team이다. Moondex는 저장소를 먼저 읽고 stack profile을 만든 뒤, 그 profile에 맞는 역할 조합과 검증 계획을 제안해야 한다.

입력으로 삼을 수 있는 신호:

- package manifest: `Cargo.toml`, `package.json`, `pnpm-lock.yaml`, `pubspec.yaml`, `pyproject.toml`, `go.mod`
- framework signal: React, Next.js, Flutter, Axum, Clap, Tauri, FastAPI, Django 등
- test runner: `cargo test`, `npm test`, Playwright, Vitest, Flutter test, pytest
- persistence and contract surface: DB migration, schema, API route, CLI command, state file, archive format
- runtime surface: web UI, mobile UI, CLI, background worker, plugin, skill, MCP server
- quality gates: formatter, linter, typecheck, E2E, screenshot verification, audit command

stack profile 예시:

| 프로젝트 유형 | 추천 specialist lens | 필수 검증 |
| --- | --- | --- |
| Rust CLI/runtime | Rust implementer, CLI contract reviewer, state/audit reviewer | `cargo fmt --check`, `cargo test`, CLI smoke, state diff |
| React/Next.js web app | frontend implementer, accessibility/UI reviewer, browser tester | typecheck, unit test, Playwright screenshot, responsive check |
| Flutter app | Flutter implementer, widget tester, platform reviewer | `dart format`, `flutter test`, target device smoke |
| Python data/API | Python implementer, API/schema reviewer, integration tester | `pytest`, contract fixtures, migration/API smoke |
| Plugin/skill package | plugin packager, skill reviewer, install tester | manifest validation, local install, skill discovery smoke |

이 관점에서 `meta-harness`의 `Team Architecture Design`은 Moondex 안에서 `Stack-Aware Team Design`으로 해석하는 것이 맞다. 목표는 role을 많이 늘리는 것이 아니라, 현재 프로젝트의 기술 스택에 맞는 검토 렌즈와 검증 명령을 자동으로 붙이는 것이다.

## 권장 벤치마크 트랙

### 1. Role Selection Benchmark

목표: 기술 스택과 변경 범위에 맞는 팀 구성이 올바른지 검증한다.

입력:

- task metadata
- stack profile
- ownership scope
- changed files
- framework/runtime surface
- shared contract flags
- user-visible behavior flags
- verification requirements
- prior mailbox outputs

기대 출력:

- 선택된 role chain
- 선택된 specialist lens
- 건너뛴 role에 대한 근거
- stack-specific verification plan
- escalation trigger

시나리오:

- 낮은 위험의 국소 코드 변경: `implementer -> code-reviewer`
- 문서만 바뀌는 contract 변경: `implementer -> code-reviewer -> compliance-reviewer`
- persisted state, schema, CLI, API, archive behavior 변경: `compliance-reviewer` 필수
- integration/E2E/external IO/user-critical flow 변경: `tester` 필수
- React/Next.js UI 변경: frontend reviewer와 browser/screenshot validation 필수
- Rust CLI 변경: CLI contract reviewer와 command smoke 필수
- Flutter widget 변경: widget tester와 platform smoke 필수
- plugin/skill 변경: manifest reviewer와 install/discovery smoke 필수
- 변경 파일이 모호함: 추측하지 않고 compliance로 route
- reviewer가 변경을 요청함: 제한된 rework 범위 안에서 implementation으로 되돌림

### 2. Pattern Selection Benchmark

목표: task 집합이 Pipeline, Fan-out/Fan-in, Supervisor, 또는 hybrid composition 중 무엇을 써야 하는지 결정한다.

시나리오:

- 엄격한 의존성 chain: Pipeline
- 독립적인 wave task: Fan-out/Fan-in
- 변하는 backlog 또는 stale lease: Supervisor
- 구현과 필수 review 조합: Producer-Reviewer
- 조건부 compliance/test role: Expert Pool

### 3. Handoff Quality Benchmark

목표: role handoff 산출물이 downstream role이 독립적으로 진행할 만큼 완전한지 점수화한다.

평가 기준:

- 명명된 input
- 명명된 output
- owner role
- task id와 phase
- scope boundary
- verification evidence
- failure path
- downstream role이 숨겨진 context 없이 진행 가능

이 항목은 기존 `validate-role-transfer`와 `validate-readiness` 검사를 기반으로 하되, cross-artifact consistency까지 확장해야 한다.

### 4. Review Boundary Benchmark

목표: reviewer role이 서로 겹치거나 위험을 건너뛰지 않도록 한다.

기대 boundary:

- `code-reviewer`: 구현 정확성, regression risk, test, maintainability
- `compliance-reviewer`: spec/design/contract/schema/API/CLI/state/archive/policy-sensitive boundary
- `tester`: 필요할 때 독립적인 integration/E2E/user-flow evidence

시나리오:

- code reviewer가 민감한 경로에서 compliance를 건너뜀: risk를 flag해야 함
- compliance reviewer가 contract review 대신 code review를 중복함: benchmark 실패
- tester가 E2E가 필요한 변경에서 unit-level check만 실행함: benchmark 실패

### 5. Failure Flow Benchmark

목표: 임의의 blocking 대신 결정적인 fallback을 강제한다.

시나리오:

- implementer lease 만료
- dispatch가 ACK 없이 pending/notified 상태로 남음
- reviewer가 현재 plan 범위를 넘는 변경을 요청함
- compliance가 scope drift를 발견함
- tester가 integration failure를 발견함
- planner task가 너무 넓어서 split이 필요함
- hook warning이 있는데 orchestrator가 계속 진행하려고 함

검증 조건:

- state transition이 명시적임
- event log가 변경을 기록함
- mailbox output이 유효한 schema를 가짐
- next action이 결정적임
- operator stop reason이 실행 가능한 형태임

## 산출물 전략

`_workspace`를 Moondex의 source of truth로 채택하면 안 된다. 런타임 truth는 `.moondex/state`를 사용해야 한다.

`_workspace` 스타일 산출물은 benchmark run에만 사용하고, runtime state에서 파생되었거나 runtime state와 대조 감사할 수 있어야 한다.

```text
docs/research/benchmarks/{run-id}/
  request-summary.md
  team-spec.md
  role-selection-matrix.md
  scenario-results.tsv
  final-report.md
```

이 방식은 결정적 중간 산출물이라는 상위 저장소의 유용한 아이디어를 유지하면서도, `.moondex/state`를 중복하거나 대체하지 않는다.

## 제안하는 Moondex 추가 항목

### 문서

- `docs/contracts/stack-profile-schema.md`
- `docs/contracts/team-spec-schema.md`
- `docs/execution/dynamic-team-composition.md`
- `docs/research/benchmarks/README.md`

### Skills

- `skills/moondex-team-designer`
  - 저장소의 기술 스택을 읽고 stack profile 생성
  - task 또는 wave에 대한 role chain, specialist lens, team pattern 선택
  - team spec 또는 role-selection matrix 생성
  - stack-specific verification plan 생성
  - `.moondex/state`를 runtime truth로 유지

### 향후 CLI

문서와 skill을 실제로 사용해본 뒤에만 추가한다.

```bash
moondex api inspect-stack --json
moondex api propose-team --input '{"task_id":"T-01"}' --json
moondex api apply-team --input '{"task_id":"T-01","team_spec":{...}}' --json
```

`inspect-stack`과 `propose-team`은 non-mutating이어야 한다. `apply-team`은 제안된 contract가 안정된 뒤에만 durable state를 써야 한다.

## 위험

- `meta-harness`를 그대로 복사하면 Moondex가 markdown-only orchestration 쪽으로 퇴행할 수 있다.
- `_workspace`가 parallel truth source가 되면 `.moondex/state`와 drift가 생길 수 있다.
- role selection이 machine-checkable하지 않으면 role 수가 늘어날수록 처리량이 떨어질 수 있다.
- 기술 스택 감지가 manifest 이름만 보고 끝나면 잘못된 specialist team을 만들 수 있다.
- stack-specific verification이 너무 강하면 작은 변경에도 과도한 검증 비용이 발생할 수 있다.
- Hierarchical Delegation은 ownership을 숨길 수 있으므로 드물게 사용해야 한다.
- scenario benchmark가 state transition, mailbox output, audit output, event를 assert하지 않으면 단순 prompt test가 될 수 있다.

## 가장 좋은 다음 벤치마크

첫 번째 benchmark run으로 `money-track-app-bootstrap-theme-raw-replan` 예제를 사용한다.

비교 대상:

1. manual planning
2. planner pool
3. split-retry planning

평가 항목:

- role selection correctness
- stack profile correctness
- specialist lens suitability
- handoff completeness
- validation outcomes
- stack-specific verification coverage
- review changes
- hung/retry rate
- final confidence
- `.moondex/state`가 execution을 깔끔하게 표현할 수 있었는지

이 benchmark는 Moondex runtime mechanics를 바꾸지 않고도 기술 스택 기반 dynamic team composition을 직접 검증한다.

## 권고

다음 단계로 `moondex-team-designer`, `stack-profile-schema.md`, `team-spec-schema.md`를 추가한다. 처음에는 docs-first와 read-only 방식을 유지한다. Rust automation을 추가하기 전에 stack profile, benchmark spec, role-selection matrix, stack-specific verification plan을 생성하는 데 먼저 사용한다.

상위 저장소 파일을 wholesale import하지 않는다. 상위 저장소는 benchmark reference로 유지하고, Moondex의 기존 state-first runtime을 강화하는 durable concept만 선별해 적용한다.
