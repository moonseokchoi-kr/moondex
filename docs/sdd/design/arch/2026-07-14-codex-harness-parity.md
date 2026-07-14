# Codex Harness Parity — Architecture Design

## 관련 문서

- Spec: [`2026-07-14-codex-harness-parity.md`](../../spec/2026-07-14-codex-harness-parity.md)
- 원본 비교 대상: `/Users/moon/Workspace/moon-harness`

## 설계 목표

Codex에서 Moon Harness의 사용자 관찰 가능 결과를 보존한다.

1. 작업은 문서·상태 파일만으로 재개할 수 있다.
2. 구현 완료는 검사 결과로 판정한다.
3. 지원되지 않는 Claude lifecycle hook은 약한 자연어 규칙으로 대체하지 않는다.
4. 개인 환경에 묶이지 않고 회사 저장소에서 설치·검증·운영할 수 있다.

## 핵심 설계 결정

| 결정 | 선택 | 이유 |
|---|---|---|
| 플러그인 경계 | Codex plugin은 `skills/`만 공개 | 현재 manifest validator와 실제 Codex plugin 표면에 맞춘다. |
| 실행 상태 | 프로젝트의 `.harness/state/` | plugin 설치 위치나 개인 홈 경로에 의존하지 않고, 재개·감사가 가능하다. |
| 실행 제어 | 상태 전이 함수 + 명시적 preflight | Codex에 Claude Stop hook과 동등한 자동 재진입 이벤트를 가정하지 않는다. |
| hard gate | git hook + CI + orchestrator preflight의 3계층 | 어느 한 계층을 우회해도 배포/병합 전 검증이 남는다. |
| 역할 협업 | Codex 협업 에이전트 + 역할 프로필 문서 | `subagent_type` 등 Claude 고유 호출 문법을 쓰지 않는다. |
| 결정적 코어 | Python stdlib 패키지 + pytest | 상태·보안·학습 판정은 LLM 응답의 변동성에서 분리한다. |
| 지식 동기화 | 조직 설정이 있을 때만 opt-in | 회사 코드가 개인 Compound로 자동 전송되지 않게 한다. |

## 대상 구조

```text
moondex/
├── .codex-plugin/                 # manifest 및 marketplace 메타데이터
├── AGENTS.md                      # 사용자·Codex 진입점, 짧은 지도
├── skills/                        # Codex가 호출하는 workflow skills
│   ├── sdd/
│   ├── sdd-orchestrator/
│   ├── self-improve/
│   ├── pr-converge/
│   └── code-mapper/
├── agents/                        # 역할 프로필(프롬프트 템플릿), 런타임 등록물 아님
├── harness_core/                  # 새 stdlib Python package
│   ├── state/                     # pipeline, cursor, circuit breaker, validation
│   ├── learning/                  # provenance, tier, recurrence, routing
│   ├── code_mapper/               # graph probe와 grep fallback
│   ├── pr/                        # comment dedup, convergence state
│   └── cli.py                     # `python -m harness_core` 검증 진입점
├── scripts/                       # 설치·CI·git-hook 어댑터
├── tests/                         # 오프라인 pytest
├── benchmarks/                    # train + held-out fixtures
└── evals/                         # 명시 실행 live eval; pytest 수집 대상에서 제외
```

프로젝트에 설치되는 런타임 상태는 다음으로 제한한다.

```text
<project>/.harness/
├── config.json                    # 조직별 옵션, 모든 외부 sync는 기본 false
├── state/
│   ├── pipeline.json
│   ├── e2e-config.json
│   └── sdd/<feature>/<run-id>/
│       ├── events.jsonl
│       └── learning-buffer.md
├── hooks/                          # 설치된 git hook wrapper
├── LEARNING.md                     # raw, append-only 입력
└── reports/                        # audit, preflight, convergence 결과
```

`docs/sdd/`는 version-controlled 결과물이며 `.harness/state/`는 실행 상태다. 둘 다 프로젝트에 속하지만, plugin 자체 또는 개인 홈 디렉터리는 상태 저장소가 아니다.

## 런타임 흐름

```text
사용자 요청
  → Codex skill: sdd
  → state preflight (문서/승인/작업트리 검사)
  → docs/sdd 산출물 생성·승인
  → Codex orchestrator
       → wave별 engineer 협업
       → compliance → review → test
       → 상태 단일 기록자: orchestrator
  → integration preflight + CI
  → PR converge
  → result 문서
  → (opt-in) organization knowledge sync
```

Codex에는 Stop event를 이용한 자동 다음 단계 주입을 설계에 포함하지 않는다. 각 skill 호출과 오케스트레이터 반복은 `pipeline.json` 및 산출물 존재를 읽고 **다음 유효 단계만** 실행한다. 따라서 새 세션에서도 상태를 읽어 재개하며, 자동 실행이 누락되어도 단계가 건너뛰어지지 않는다.

## 상태와 권한

### 상태 파일

`docs/sdd/ORCHESTRATOR_STATE.md`는 사람이 읽는 작업 현황과 증거 인덱스다. 기계 판정에 필요한 정규화된 값은 `.harness/state/pipeline.json`에 둔다.

```json
{
  "schema_version": 1,
  "feature": "codex-harness-parity",
  "phase": "DESIGN",
  "approval": {"spec": true, "design": false, "plan": false},
  "worktree": null,
  "run_id": null,
  "updated_at": "ISO-8601"
}
```

모든 전이는 `harness_core.state.transition`이 검사한다. 허용되지 않은 phase jump, 승인 없는 전이, 누락 산출물은 실패 코드와 수정 지침을 반환한다.

### 단일 작성자

- 오케스트레이터만 `ORCHESTRATOR_STATE.md`와 `pipeline.json`을 변경한다.
- worker는 파일 변경 목록, 검증 출력, `DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED` 결과만 반환한다.
- worker의 소유 파일 범위는 태스크 문서와 상태 파일에 기록한다.
- 공유 계약 파일은 태스크 계획에서 명시적으로 owner를 지정하거나, 오케스트레이터가 순차 태스크로 만든다.

Codex 협업 호출은 역할 프로필 파일을 읽어 프롬프트에 포함한다. 역할 이름은 dispatch 힌트일 뿐 권한 경계가 아니므로, 실제 파일·브랜치·검증 경계는 아래 enforcement 계층에서 확인한다.

## Codex enforcement 설계

### 계층 모델

| 계층 | 구현 | 막는 시점 | 권위 |
|---|---|---|---|
| E0 | `AGENTS.md`/skill 지시 | 에이전트 판단 전 | advisory |
| E1 | `.harness/hooks/` git hook wrapper | commit/push 직전 | 로컬 강제 |
| E2 | `harness_core preflight` | SDD phase 전환·PR 수렴 전 | workflow 강제 |
| E3 | CI required check + branch protection | 병합 전 | 최종 강제 |

E0만 통과한 변경은 완료가 아니다. E1~E3 중 해당 규칙에 지정된 증거가 없으면 result 문서에 `VERIFICATION_INCOMPLETE`로 남기며 완료 상태로 전이하지 않는다.

### 기존 Claude gate의 대체

| 원본 gate | Codex 대체 | 실패 동작 |
|---|---|---|
| `phase-gate` / Stop controller | `harness_core preflight phase` + skill의 명시적 재개 | 누락 산출물/승인 단계에서 종료 |
| `role-gate` / file ownership | task 소유 범위 검사 + 오케스트레이터 diff 검사 | 범위 밖 변경은 review 전 반려 |
| `tdd-gate` | test manifest의 RED 증거 + task diff 정책 + CI | 구현자가 기존 테스트만 바꿔 통과시킨 경우 반려 |
| `branch-gate` | pre-commit/pre-push hook + CI default-branch guard | 기본 브랜치에서 구현 커밋/직접 push 거부 |
| `e2e-gate` | `e2e-config.json`과 changed-file classifier를 preflight/CI에서 확인 | UI 변경에 E2E 증거 없으면 반려 |
| secret/dangerous/sensitive hooks | secret scanner, allowlist policy, protected-path diff 검사 | commit/CI 실패 |
| escalation tracker | state transition에서 retry count를 증가·판정 | 한도 초과 시 `ESCALATED`, worker 재실행 금지 |

git hook은 편의 및 빠른 피드백용이다. 조직의 CI required check가 E3의 source of truth이고, 훅을 설치하지 않았다는 사실도 `harness_core doctor`가 경고한다. Git hosting branch protection 설정 자체는 조직 인프라 책임이므로, Moondex는 확인 가능한 정책과 설정 가이드를 제공하되 설치 성공으로 가정하지 않는다.

## 구성 요소 설계

### 역할 프로필(`agents/`)

현재 Codex plugin manifest는 `agents/`를 독립 실행 등록물로 노출하지 않는다. 따라서 이 디렉터리의 파일은 **역할 프로필**이며, `sdd-orchestrator` 또는 idea workflow가 Codex 협업 에이전트를 만들 때 필요한 프로필만 읽어 prompt에 주입한다. 파일이 존재한다는 사실만으로 실행되거나 권한을 얻지는 않는다.

모든 활성 프로필은 아래 host-neutral 형식을 따른다.

```markdown
---
name: sdd-python-engineer
role: implementer
capabilities: [read_repository, edit_owned_files, run_validation]
---

## Input contract
- task, spec/design paths, worktree path, owned paths, iteration, validation commands

## Authority
- May edit: owned paths only
- Must not edit: `ORCHESTRATOR_STATE.md`, `pipeline.json`, other task ownership

## Output contract
Status: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED
Changed files: ...
Validation: command → exit status → relevant output
Evidence / blocker: ...
```

`model`, `tools`, `Agent(...)`, `TeamCreate`, `TaskCreate`, Claude Chrome MCP와 같은 Claude Code 실행 문법은 이 계약에서 제거한다. Codex의 실제 도구 선택은 실행 시 권한과 환경에 따라 이루어지며, 역할 프로필은 필요한 **capability**와 결과만 선언한다.

#### 역할 분류와 정리

| 그룹 | 조치 | 이유 |
|---|---|---|
| `sdd-*-engineer`, implementer, taskmaster, compliance, reviewer, test-automator, architect 계열 | 유지·계약 표준화 | 현재 SDD 실행 경로의 핵심 역할이다. |
| idea market/user/feasibility/biz-model/reviewer | 유지·research capability 표준화 | Codex web/browser 도구로 조사 가능하되 Claude Chrome MCP 의존을 제거한다. |
| `sdd-compound-syncer` | 조직 knowledge-syncer로 변경 | 개인 Compound 경로와 사용자 종속성을 없앤다. |
| `sdd-team-leader` | 재설계 | 현재는 team leader가 상태를 직접 편집하고 Claude Agent/Skill 도구를 전제한다. Codex 오케스트레이터만 상태를 쓰도록 바꾼다. |
| `ux-researcher`, `ia-designer`, `ui-designer`, `api-designer`, `architect-reviewer`, `blocker-checker` 등 비-SDD 구세대 | 현재 SDD와 계약 통합 또는 `agents/archive/` 이동 | `docs/spec-design/` 경로와 중복 역할이 남아 있어 어떤 프로필이 SOT인지 모호하다. |
| product/competitive 등 확장 역할 | 기본 dispatch 대상에서 제외 | parity 범위와 직접 관계가 없으므로 명시 호출일 때만 사용한다. |

모든 worker는 상태를 직접 수정하지 않고 결과만 반환한다. 오케스트레이터가 결과를 검증한 뒤 단일 작성자로 상태를 전이한다. 이는 collaboration 도구의 동시 실행 여부와 무관하게 유지하는 불변식이다.

### `harness_core`

원본 `hooks/lib/self_improve/`와 `hooks/lib/code_mapper/`, `skills/pr-converge/scripts/`를 파일 복사가 아니라 테스트를 보존한 package로 이식한다. 외부 호출(gh, git, graph tool, Codex)은 thin adapter에만 둔다.

| 모듈 | 책임 | 금지 |
|---|---|---|
| `state` | schema I/O, phase transition, stale/lock/circuit breaker | LLM·네트워크 호출 |
| `learning` | cursor, provenance, tier, recurrence, precheck, memory routing | plugin 파일 자동 변경 |
| `pr` | state machine, comment dedup, pattern detection | GitHub API 직접 호출 |
| `code_mapper` | graph availability, search pattern, output formatting | graph 결과를 사실로 과장 |
| `cli` | preflight/doctor/validate/report | 정책 판단을 숨긴 mutation |

### Skills

- `sdd`: 상태와 산출물을 확인해 다음 Phase를 제안·실행한다. 자동 Stop loop를 언급하지 않는다.
- `sdd-orchestrator`: Codex 협업 에이전트를 Wave 단위로 dispatch하고 단일 상태 작성자 역할을 한다.
- `pr-converge`: `gh` adapter에서 신호를 수집하고 core state machine 결과에 따라 한 pass만 수행한다.
- `self-improve`: raw learning에서 proposal 또는 프로젝트 티어 적용을 만든다. harness tier는 언제나 proposal이다.
- `code-mapper`: graph adapter의 3상태를 확인하고, 필요 시 grep fallback으로 ephemeral report를 반환한다.
- `harness`: `.harness/` 생성, git hook wrapper 설치, CI workflow 템플릿 제안, `doctor` 실행을 담당한다.

### Company configuration

`<project>/.harness/config.json`의 기본값은 아래와 같다.

```json
{
  "schema_version": 1,
  "knowledge_sync": {"enabled": false},
  "ci": {"required_check_name": "moondex-verify"},
  "security": {"secret_scan": true, "protected_paths": []}
}
```

knowledge sync를 활성화할 때에는 `destination`, `credential_source`, `retention_policy`를 모두 요구한다. 이 설정은 개인 절대경로를 기본값으로 제공하지 않는다. 미설정 상태의 Phase 5는 `SKIPPED` 보고를 만들고 Phase 4 구현 결과를 무효화하지 않는다.

## 검증 설계

### 오프라인 테스트

`pytest tests/ -q`는 네트워크와 LLM 호출 없이 다음을 검증한다.

- state transition, cursor, circuit breaker, tier/protected-set, recurrence
- PR comment dedup 및 convergence state machine
- code-mapper graph fallback 및 출력 규약
- config schema와 개인 절대경로 금지
- phase/branch/E2E/secret preflight의 실패·통과 fixture

### Benchmarks와 live eval

- `benchmarks/sets/train`: 개발 중 관찰용 점수
- `benchmarks/sets/held-out`: 채택 전 회귀 방지용, 수정 금지
- `evals/`: 명시 실행 전용. Codex collaboration 또는 LLM 판단을 사용해도 pytest에 수집되지 않는다.

harness tier 변경의 채택 조건은 `train score > baseline` 이면서 `held-out regression = 0`이다. baseline이 없으면 자동 채택하지 않는다.

### End-to-end acceptance

샘플 저장소에서 다음을 실행해 F1~F9의 최종 증거를 만든다.

1. SDD spec/design/plan 승인 후 worktree에서 하나의 UI 변경을 구현한다.
2. E2E 없음·기본 브랜치 커밋·secret 포함 변경이 각각 preflight/CI에서 실패하는지 확인한다.
3. engineer → compliance → review → test 실패와 재시도 한도를 기록한다.
4. PR에 CI 실패, 코드 수정 코멘트, 설계 질문 코멘트를 각각 넣어 `pr-converge`의 자동 처리/에스컬레이션을 확인한다.
5. 반복 교훈을 `self-improve`에 전달해 프로젝트 티어 적용과 harness 티어 proposal 분리를 확인한다.

## 마이그레이션 순서

1. `harness_core`와 tests/benchmarks/evals을 먼저 이식한다.
2. self-improve, pr-converge, code-mapper를 Codex 어댑터로 연결한다.
3. `.claude`·Claude tool·Stop hook 의존을 사용자 경로에서 제거한다.
4. `harness_core preflight`, git hook wrapper, CI workflow를 구현한다.
5. SDD/오케스트레이터 역할 프로필을 Codex 협업 계약으로 정리하고, 구세대·중복 프로필을 archive 또는 통합한다.
6. 샘플 E2E를 통과하고 result 문서에 F1~F9 증거를 연결한다.

## 설계상 제약과 위험

- Codex가 Claude와 동일한 lifecycle hook을 제공한다고 가정하지 않는다. 자동 연쇄가 아니라 idempotent resume를 선택한다.
- 로컬 git hook은 우회 가능하므로 CI required check 없이는 hard gate라고 부르지 않는다.
- Codex 협업 에이전트의 동시성은 파일 잠금의 증거가 아니다. ownership 검사와 Wave 의존성으로 충돌을 줄이고, 공유 파일은 순차 처리한다.
- `gh`와 Git hosting API는 외부 의존이다. 인증·네트워크 오류는 자동 수정하지 않고 `BLOCKED`로 기록한다.

## Spec 수용 기준 매핑

| Spec | 설계 요소 | 수락 증거 |
|---|---|---|
| F1 | 대상 구조, skill 이식 | file inventory + regression test |
| F2 | `pipeline.json`, 문서 산출물, transition | resume fixture |
| F3 | E0~E3 enforcement | intentional-failure CI fixtures |
| F4 | single writer, Wave loop | state transition log |
| F5 | `pr` core + gh adapter | PR scenario fixture |
| F6 | `learning` core + benchmark gate | protected-set/rollback tests |
| F7 | graph adapter + fallback | 3-state tests |
| F8 | opt-in config schema | unset sync scenario |
| F9 | pytest split + benchmark layout | CI command and held-out run |
| F10 | 역할 프로필 계약, 단일 상태 작성자 | agent-profile lint + collaboration scenario |
