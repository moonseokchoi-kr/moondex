# Codex Harness Parity — Architecture Design

## 관련 문서

- Spec: [`2026-07-14-codex-harness-parity.md`](../../spec/2026-07-14-codex-harness-parity.md)
- 원본 비교 대상: `/Users/moon/Workspace/moon-harness`

## 설계 목표

Codex에서 Moon Harness의 사용자 관찰 가능 결과를 보존한다.

1. 작업은 문서·상태 파일만으로 재개할 수 있다.
2. 구현 완료는 검사 결과로 판정한다.
3. 지원되지 않는 Claude lifecycle hook은 약한 자연어 규칙으로 대체하지 않는다.
4. 신뢰된 로컬 checkout에서 설치·검증·재개할 수 있다. 로컬 감사는 재현 가능한 원문 근거를 보존하고, 사람이 보거나 밖으로 나가는 표면에서만 마스킹한다.

## 핵심 설계 결정

| 결정 | 선택 | 이유 |
|---|---|---|
| 플러그인 경계 | Codex plugin은 `skills/`만 공개 | 현재 manifest validator와 실제 Codex plugin 표면에 맞춘다. |
| 실행 상태 | 프로젝트의 `.harness/state/` | plugin 설치 위치나 개인 홈 경로에 의존하지 않고, 재개·감사가 가능하다. |
| 실행 제어 | 프로젝트 로컬 상태 컨트롤러 + turn 기반 start/resume | Codex에 Claude Stop hook과 동등한 자동 재진입 이벤트를 가정하지 않는다. |
| hard gate | shared local enforcement + orchestrator preflight, 선택적 git hook | 모든 기본 검증 경로가 같은 현재-worktree 판정을 쓰며, hook은 빠른 피드백을 제공한다. |
| 역할 협업 | Codex 협업 에이전트 + 역할 프로필 문서 | `subagent_type` 등 Claude 고유 호출 문법을 쓰지 않는다. |
| 결정적 코어 | Python stdlib 패키지 + pytest | 상태·보안·학습 판정은 LLM 응답의 변동성에서 분리한다. |
| 데이터 경계 | 신뢰된 로컬 audit은 원문, report/render는 redacted view | 재개·디버깅에 필요한 evidence를 잃지 않으면서 화면·파일 공유 실수를 줄인다. |
| 외부 전송 | 기본 없음; export/shared/provider는 별도 opt-in 설계 | 이 baseline은 원격 전송이나 hostile at-rest 환경을 방어 대상으로 삼지 않는다. |

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
├── audit/                          # append-only 원문 처분 근거(신뢰된 로컬 경계)
└── reports/                        # 사람이 읽는 redacted preflight/convergence 결과
```

`docs/sdd/`는 version-controlled 결과물이며 `.harness/state/`는 실행 상태다. `.harness/audit/`는 신뢰된 개인 checkout 내부의 재개·디버깅 증거이고, 원문 review evidence를 보존할 수 있다. `.harness/reports/`와 CLI 출력은 사람이 읽는 surface이므로 redacted view만 둔다. 어느 경로도 기본적으로 export·공유·원격 전송되지 않는다. plugin 자체 또는 개인 홈 디렉터리는 상태 저장소가 아니다.

### 배포 프로젝트와 plugin의 소유 경계

Moondex **plugin 저장소**와 이를 설치해 사용하는 **프로젝트**는 서로 다른 소유 경계를 가진다. plugin 저장소에서는 이 문서의 최소 protected set(예: `skills/`, `harness_core/`, `scripts/`, `tests/`)이 배포·검증 자산을 보호한다. 프로젝트에서는 그 set을 애플리케이션 전체에 적용하지 않으며, 로컬 config가 추가한 `.harness/**`와 설치 adapter만 harness-tier로 보호한다. 이 설계는 신뢰된 사용자의 현재 작업트리 config를 사용한다. PR이 정책을 바꾸는 공격을 막는 원격 정책 스냅샷은 선택적 확장에서만 다룬다.

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
  → integration preflight
  → local review convergence
  → result 문서
  → (opt-in) organization knowledge sync
```

Codex에는 Stop event를 이용한 자동 다음 단계 주입을 설계에 포함하지 않는다. 각 skill 호출과 오케스트레이터 반복은 `pipeline.json` 및 산출물 존재를 읽고 **다음 유효 단계만** 실행한다. 따라서 새 세션에서도 상태를 읽어 재개하며, 자동 실행이 누락되어도 단계가 건너뛰어지지 않는다.

### Host-independent SDD state controller

`/sdd start <feature>`와 이후의 일반 Codex turn은 모두 프로젝트 로컬 state controller를 호출한다. controller는 현재 작업 디렉터리(또는 명시 `--project-root`)에서 `.harness/state/pipeline.json`과 `docs/sdd/` 산출물을 찾는다. `$HARNESS_HOOKS`, `CODEX_PLUGIN_ROOT`, 세션 ID, hook 등록 여부는 입력도 전제조건도 아니다.

정상 turn에서 사용자가 “계속”, “진행”, “재개”처럼 작업을 요청하면 `sdd` skill은 controller의 `inspect`와 `resume` 결과를 먼저 읽는다. 결과가 action이면 그 한 단계의 명시적 작업만 수행하거나 오케스트레이터에 위임한다. 결과가 사용자 승인 대기이면 필요한 승인과 근거를 표시하고 전이하지 않는다. 이 turn 기반 재개는 지원되지 않는 host event가 나중에 백그라운드에서 다음 단계를 실행할 것이라고 약속하지 않는다.

controller의 portable API는 다음의 idempotent 작업으로 한정한다. skill은 이 API를 직접 호출하거나 동등한 `python -m harness_core state ...` CLI를 호출할 수 있다. CLI는 작업트리와 상태 파일만 사용하며 host 환경변수를 source하지 않는다.

| API / CLI 예 | 책임 | 상태 변경 |
|---|---|---|
| `initialize(feature)` / `state start <feature>` | 새 feature의 상태를 만들거나 기존 동일 feature 상태를 식별 | 새 상태가 없을 때만 생성 |
| `inspect(feature?)` / `state status [feature]` | 산출물·승인·lock·다음 유효 단계를 결정 | 없음 |
| `resume(feature)` / `state resume <feature>` | 현재 상태를 다시 판정하여 `ACTION`, `WAITING_USER`, `BLOCKED`, `COMPLETE` 중 하나를 반환 | 승인된 명시 전이만 |
| `transition(expected, target, evidence)` / `state transition ...` | compare-and-transition, approval/artifact/retry 검증, event 기록 | 오케스트레이터만 허용 |
| `doctor` / `state doctor` | optional hook 및 adapter 가용성을 진단하고 수동 명령을 제시 | 없음 |

`start`는 기존 상태를 덮어쓰지 않는다. 동일 feature가 있으면 `inspect`와 동일한 next result를 반환하고, feature를 생략한 resume에서 여러 활성 상태가 있으면 후보 목록과 선택 방법을 반환한다. controller 응답은 사람이 읽는 설명과 안정적인 code를 함께 가진다. 최소 code는 `INITIALIZED`, `ACTION`, `WAITING_USER`, `BLOCKED_ARTIFACT`, `BLOCKED_APPROVAL`, `STATE_INVALID`, `STATE_BUSY`, `AMBIGUOUS_FEATURE`, `COMPLETE`, `ADVISORY_UNAVAILABLE`이다.

`STATE_INVALID`(schema/문서-상태 모순), `STATE_BUSY`(단일 작성자 lock 보유), `BLOCKED_ARTIFACT`, `BLOCKED_APPROVAL`, `AMBIGUOUS_FEATURE`는 상태를 수정하지 않고 remediation을 반환한다. 반면 hook 또는 hook 환경변수가 없는 것은 `ADVISORY_UNAVAILABLE` 진단일 뿐 `start`, `status`, `resume`, `transition`의 실패가 아니다. 이 구분으로 host 독립 controller의 실패와 선택적 편의 기능의 부재를 관찰 가능하게 분리한다.

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

모든 전이는 `harness_core.state.transition`이 검사한다. 허용되지 않은 phase jump, 승인 없는 전이, 누락 산출물은 실패 코드와 수정 지침을 반환한다. controller는 상태 파일을 atomic write하고 exclusive lock 아래에서 expected state를 확인한다. lock/쓰기 실패는 기존 상태를 보존한 `STATE_BUSY` 또는 `STATE_INVALID`로 끝나며, skill이 추측으로 문서를 고쳐 전진하지 않는다.

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
| E1 | `.harness/hooks/` git hook wrapper (선택) | commit 직전 | 빠른 로컬 피드백 |
| E2 | `harness_core preflight` / 명시적 verify | SDD phase 전환·리뷰 수렴 전 | baseline workflow 강제 |
| E3 | CI/provider adapter (선택) | 원격 통합 시 | advisory extension |

E0만 통과한 변경은 완료가 아니다. baseline 완료에는 E2의 로컬 report가 필요하다. E1은 E2와 같은 command를 호출할 뿐 hook 미설치는 실패가 아니며, E3는 로컬 완료 조건이 아니다.

### 기존 Claude gate의 대체

| 원본 gate | Codex 대체 | 실패 동작 |
|---|---|---|
| `phase-gate` / Stop controller | `harness_core state resume` + `preflight phase` + skill의 명시적 재개 | 누락 산출물/승인 단계에서 다음 action 없이 종료 |
| `role-gate` / file ownership | task 소유 범위 검사 + 오케스트레이터 diff 검사 | 범위 밖 변경은 review 전 반려 |
| `tdd-gate` | test manifest의 RED 증거 + task diff 정책 + local verify | 구현자가 기존 테스트만 바꿔 통과시킨 경우 반려 |
| `branch-gate` | explicit/preflight + 선택적 pre-commit wrapper | 기본 브랜치의 Phase 4 구현 변경 거부 |
| `e2e-gate` | `e2e-config.json`과 changed-file classifier를 preflight에서 확인 | UI 변경에 E2E 증거 없으면 반려 |
| secret/dangerous/sensitive hooks | shared secret scanner, allowlist, protected-path 검사 | 명시 검증 또는 hook 실패 |
| escalation tracker | state transition에서 retry count를 증가·판정 | 한도 초과 시 `ESCALATED`, worker 재실행 금지 |

git hook은 편의 및 빠른 피드백용이다. `harness_core doctor`는 설치 여부를 알리지만, hook 미설치는 경고일 뿐이다. 명시적 local verify/preflight가 기준선의 source of truth다.

### Shared local changed-file enforcement

E1 wrapper와 E2 CLI는 하나의 `harness_core.enforcement` entrypoint를 호출한다. 입력은 현재 worktree에서 사용자가 명시한 `--changed-file` 목록 또는 Git으로 얻은 현재 변경 목록이며, 결과는 `.harness/reports/`에 남는다.

```json
{
  "schema_version": 1,
  "source": "explicit | worktree | hook",
  "worktree": "repository-relative identity",
  "changed_files": ["canonical repository-relative paths"],
  "rules": ["branch", "e2e", "secret", "protected-path"],
  "result": "PASS | FAIL | INDETERMINATE",
  "evidence": ["redacted diagnostic or command result"]
}
```

The same classifier is used whether a developer invokes `python -m harness_core verify --changed-file …`, runs preflight, or installs the optional hook. It examines the supplied current change set, records canonical paths and applicable rules, and reports a useful remediation message. Rename/copy entries examine both names when Git supplies them. A missing or unusable changed-file input is `INDETERMINATE`, not a successful empty change set.

This baseline deliberately does not resolve remote push ancestry, first-push history, provider events, or cross-host range parity. Those checks may be supplied by the advisory extension described below.

### Repository path containment와 protected set

자동 변경과 changed-file 정책은 raw 문자열 prefix를 믿지 않는다. repository root는 `git rev-parse --show-toplevel`로 얻은 physical path이며, 각 후보는 다음 순서로 판정한다.

1. 입력이 absolute path이거나 NUL을 포함하면 `INVALID_PATH`다.
2. POSIX segment를 해석하기 전에 `.`는 제거하고 `..` segment가 하나라도 있으면 자동 적용 대상에서는 `INDETERMINATE`다. audit/scan 입력은 별도 경고와 함께 거부한다. `app/../scripts/x`를 project path로 재분류하지 않는다.
3. 허용된 relative candidate를 root에 결합하고 `resolve(strict=false)`한 뒤 physical root의 하위인지 `commonpath`로 증명한다. root 밖, resolve 오류, 또는 containment를 증명할 수 없는 결과는 `OUTSIDE_OR_INDETERMINATE`다.
4. 존재하는 각 ancestor와 최종 file의 symlink를 확인한다. root 밖을 가리키는 symlink, 끊어진 symlink, 또는 검사 시점과 사용 시점 사이의 대상을 고정할 수 없는 symlink는 자동 적용할 수 없다. non-existent path도 existing ancestor의 physical containment를 증명할 수 있을 때만 project-tier 후보가 된다.

자동 적용은 `CANONICAL_INSIDE` 상태만 허용한다. 나머지는 변경을 만들지 않고 `PROPOSAL`(정책 제안 가능) 또는 `BLOCKED`(명시 target을 안전하게 판정할 수 없음) disposition과 원인을 남긴다.

이 목록은 **plugin 저장소를 검사할 때의** 최소 protected set이다. config은 set을 **추가만** 할 수 있으며 이 최소 set을 삭제·완화할 수 없다. 프로젝트에서는 위의 “배포 프로젝트와 plugin의 소유 경계”에 정의한 local protected set을 사용한다. repository identity와 현재 신뢰된 local config가 mode와 추가 set을 결정한다.

```text
skills/**
agents/**
.codex-plugin/**
harness_core/**
scripts/**
.github/**
hooks/**
tests/**
benchmarks/**
evals/**
```

protected set은 canonical path segment 기준으로만 match한다. 따라서 `scripts2/x`는 `scripts/**`가 아니고, `app/../scripts/x`는 traversal로 실패하며, `linked/x`가 `scripts/x`를 가리키는 경우도 symlink policy로 auto-apply 불가다. harness-tier는 언제나 proposal-only다. project-tier `APPLY`는 canonical-inside, 해당 repository mode의 protected-set 밖, rollback record, configured run cap, 그리고 기존 recurrence/critic checks를 모두 만족할 때만 가능하다.

### Secret policy

`enforcement.secret_scan`은 현재 changed-file의 added/modified text와 새 binary가 아닌 file content를 검사하며, 원문 secret을 audit log에 쓰지 않는다. 다음은 최소 차단 패턴이다.

- `API_KEY`, `TOKEN`, `SECRET`, `PASSWORD` 등 credential 성격 key의 literal assignment;
- JSON object에서 위 credential 성격 key에 연결된 non-placeholder string literal;
- `Authorization: Bearer <literal>` 및 동등한 HTTP header key/value form.

literal은 충분한 길이·문자 다양성의 실제 값으로 판정하며, `${NAME}`, `$NAME`, `os.environ[...]`, `process.env.NAME`, `YOUR_*`, `REPLACE_ME`, `<token>`, 빈 값 및 문서화된 dummy fixture는 placeholder/reference로 분류해 차단하지 않는다. allowlist는 file/line, pattern class, reason, expiry를 가진 repository-local record다. scanner가 allowlist를 사용하면 match class와 record ID(값은 redacted)를 audit에 남기고, 만료·범위 불일치·형식 오류 allowlist는 실패한다. scanner 오류나 encoding ambiguity는 `SECRET_SCAN_INDETERMINATE`로 중단한다.

### 로컬 evidence와 렌더링 경계

이 baseline의 trust boundary는 단일 사용자의 현재 checkout이다. 따라서 review·learning core가 `.harness/audit/`에 append하는 immutable event는 처분 재현에 필요한 **원문 evidence**를 보존할 수 있다. 이것은 Git에 추가하거나 원격에 전송하는 산출물이 아니며, 원문을 at-rest에서 암호화·제거·마스킹하는 것은 baseline hard gate가 아니다.

반면 CLI JSON/text, `.harness/reports/`의 사람이 읽는 보고서, result 문서에 인용되는 evidence, 그리고 사용자가 명시적으로 생성하는 export는 render/export boundary를 반드시 지난다. 이 경계는 credential 성격 key의 literal, Bearer literal 및 같은 정책으로 식별된 값을 `[REDACTED]`로 표시한다. 처분 ID, path/rule, validation command 결과 및 마스킹 사실은 남겨 사용자가 원문 audit를 찾아 검토할 수 있어야 한다.

```text
local review/learning input
  → deterministic core
  → .harness/audit/*.jsonl       (raw evidence; trusted local only)
  → render_report()/CLI          (redacted evidence view)
  → optional export/shared mode  (not part of this architecture; separate sanitization contract)
```

이 구분은 scanner 자체의 진단을 평문으로 출력하라는 뜻이 아니다. secret scanner의 report·allowlist audit는 계속 값 없이 match class와 location만 기록한다. 단, `pr`/`learning`의 원문 evidence가 로컬 audit에 있다는 사실만으로 failure를 만들지 않는다.

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
| `state` | portable state controller, schema I/O, start/status/resume/transition, stale/lock/circuit breaker | LLM·네트워크 호출 또는 host 환경변수 의존 |
| `learning` | cursor, provenance, tier, recurrence, precheck, memory routing | plugin 파일 자동 변경 |
| `pr` | strict input validation, comment dedup, disposition, convergence state, raw local audit event | hosting/provider API 직접 호출 또는 report redaction 우회 |
| `code_mapper` | graph availability, search pattern, output formatting | graph 결과를 사실로 과장 |
| `enforcement` | local changed-file classification, secret policy, report | hook/CLI마다 다른 정책 구현 |
| `cli` | `state start/status/resume/transition/doctor`, preflight/validate/report, redacted rendering | 정책 판단을 숨긴 mutation, host hook source, 또는 raw audit의 무가공 출력 |

### Skills

- `sdd`: 모든 `/sdd start`와 일반 turn 재개에서 portable controller를 먼저 호출하고, 그 `ACTION`/`WAITING_USER`/`BLOCKED` 결과만 사용자에게 제시·실행한다. 자동 Stop loop를 언급하지 않는다.
- `sdd-orchestrator`: Codex 협업 에이전트를 Wave 단위로 dispatch하고 controller의 `transition`을 이용하는 단일 상태 작성자 역할을 한다.
- `pr-converge`: local input/fixture에서 신호를 수집하고 core state machine 결과에 따라 한 pass만 수행한다. 기본 흐름은 어떤 provider mirror도 호출하지 않으며, 사람에게 보여 주는 결과는 redacted report다.
- `self-improve`: raw learning에서 proposal 또는 프로젝트 티어 적용을 만든다. harness tier는 언제나 proposal이다.
- `code-mapper`: graph adapter의 3상태를 확인하고, 필요 시 grep fallback으로 ephemeral report를 반환한다.
- `harness`: `.harness/` 생성, 선택적 git hook wrapper 설치, 선택적 CI workflow 템플릿 제안, `doctor` 실행을 담당한다.

`hooks/`는 이행 기간에 기존 host 호환 실험과 optional git-hook wrapper의 소스로 보존할 수 있다. 그러나 active `sdd` skill path는 그 안의 `pipeline-utils.sh`를 source하거나 Stop-hook directive를 기다리지 않는다. `.codex-plugin/plugin.json`이 hook을 등록·실행한다고 주장하지 않으며, `doctor`가 발견한 legacy hook은 `ADVISORY_UNAVAILABLE` 또는 설치 가능한 선택 기능으로만 보고한다.

### 로컬 리뷰 요청 수렴 계약

`pr` core는 hosting API나 LLM을 호출하지 않는다. local adapter/CLI는 conversation, inline, review-body 형식의 리뷰 요청을 strict JSON으로 전달한다. parser는 duplicate key, trailing data, `NaN`, `Infinity`, `-Infinity` 및 표준 JSON 밖 상수를 거부하며, schema 검증 전 실패도 `BLOCKED`로 기록한다. provider 연결이 없어도 fixture 입력으로 같은 core를 실행할 수 있다.

#### 결정적 정합성 판정

`SAFE_FIX`/`REJECTED`는 자연어의 그럴듯한 요약만으로 결정하지 않는다. 판정 시점의 현재 worktree spec, design, task/ownership과 로컬 build/lint/test 결과에서 requirement ID, 소유 경계, 검증 계획을 찾는다. 요청·근거·검증 계획을 충분히 연결할 수 없으면 alignment는 `UNKNOWN`이고 `ESCALATED`다.

LLM은 요약, 후보 근거 검색, 설명 초안을 도울 수 있지만 증거의 권위자가 아니다. 후보는 현재 로컬 문서의 path/rule과 명시 검증 결과로 재확인한 뒤에만 사용한다. deterministic validation이 실패·부족·모순이면 `ESCALATED`다.

각 comment는 최소 다음 schema를 만족해야 한다.

```json
{
  "schema_version": 1,
  "source": "conversation | inline | review_body",
  "source_identity": "non-empty stable string",
  "comment_id": "non-empty string | finite integer",
  "revision_identity": "provider revision/update id or content hash",
  "body_hash": "SHA-256 of normalized body",
  "author": "non-empty string",
  "body": "string",
  "created_at": "RFC 3339 timestamp",
  "review_state": "optional string",
  "path": "optional repository-relative string",
  "line": "optional positive finite integer"
}
```

Numeric identifiers and line values are accepted only when JSON numbers are finite integers in the safe configured range; fractional, bool, null, non-finite, negative (where disallowed), missing, or type-mismatched values are invalid. `source_identity` is the dedup key and must be stable across polling; a malformed identity cannot be silently deduplicated. Any malformed item blocks its collection pass and cannot produce `CONVERGED`, `SAFE_FIX`, or an automatic mutation.

The adapter persists a local collection snapshot before disposition: input identity, collection time, ordered source identities, revision identities, and normalized body hashes. The core compares the next snapshot with the last one. An edited request or changed body/revision is a new actionable revision and must be re-dispositioned; a prior terminal decision is not inherited. A local file/CLI input is complete once it parses and all entries are enumerated.

For every newly observed comment revision, the core writes an immutable machine-readable, append-only disposition event before it can disappear from the actionable queue. A non-actionable classification is also a disposition and requires a human-readable reason. One orchestrator-owned writer appends events and advances the cursor under an exclusive lock; it writes a temporary file, fsyncs it, atomically renames it, then fsyncs the containing directory. Concurrent writer, lock loss, partial write, or any audit persistence failure is `AUDIT_WRITE_FAILED`: no automatic change/post/terminal convergence may occur.

```json
{
  "schema_version": 1,
  "source_identity": "provider/kind/id",
  "revision_identity": "provider revision/update id or normalized body SHA-256",
  "collection_snapshot_id": "immutable snapshot ID",
  "request_id": "stable local UUID or provider ID",
  "observed_at": "RFC 3339",
  "actionability": "ACTIONABLE | NON_ACTIONABLE | BLOCKED_INPUT",
  "request_summary": "raw local audit summary; renderer redacts credential literals",
  "alignment": {
    "spec": "ALIGNS | CONFLICTS | UNKNOWN",
    "design": "ALIGNS | CONFLICTS | UNKNOWN",
    "ownership": "OWNED | OUT_OF_SCOPE | UNKNOWN",
    "verification": "AVAILABLE | REQUIRED | INSUFFICIENT"
  },
  "decision": "SAFE_FIX | REJECTED | ESCALATED | NON_ACTIONABLE | BLOCKED",
  "reason": "non-empty human-readable rationale",
  "evidence": [{"kind": "spec|design|ownership|command|diff", "ref": "raw local evidence reference or command result"}],
  "fix": {"changed_files": [], "validation": []},
  "escalation": {"question": "optional", "owner": "optional"},
  "posting": {"status": "NOT_REQUESTED | PENDING_LOCAL_REPORT | POSTED | FAILED", "reference": "optional"}
}
```

Decision is deterministic over supplied local evidence, not an LLM inference: `SAFE_FIX` requires an aligning spec/design rule, ownership, concrete validation plan, and no unresolved conflict; applying it records changed files and passing validation. A failed validation, changed ownership, or scope expansion converts it to `ESCALATED`. `REJECTED` requires conflicting or out-of-scope evidence plus a human-readable rationale and alternative. Unknown alignment, contradictory evidence, design trade-off, external dependency, or missing authority is `ESCALATED`.

Every disposition is written atomically to a local append-only audit record before it leaves the actionable queue. The trusted local audit may retain the submitted body and other raw evidence needed to reproduce the disposition. A local report contains the rendered reason and redacted evidence references. Audit write failure blocks automatic change and convergence. No provider posting exists in the baseline or contributes to a local disposition.

`CONVERGED` requires complete valid local input, passing configured local build/lint/test commands, no actionable request without a terminal disposition, and no open escalation. Hosted CI green, exact remote head SHA, required-check identity, and reply-posting proof belong only to the advisory extension.

### Local configuration

`<project>/.harness/config.json`의 기본값은 아래와 같다.

```json
{
  "schema_version": 1,
  "knowledge_sync": {"enabled": false},
  "security": {
    "secret_scan": true,
    "protected_paths": [],
    "secret_allowlist": ".harness/secret-allowlist.json"
  }
}
```

knowledge sync를 활성화할 때에는 `destination`, `credential_source`, `retention_policy`를 모두 요구한다. 이 설정은 개인 절대경로를 기본값으로 제공하지 않는다. 미설정 상태의 Phase 5는 `SKIPPED` 보고를 만들고 Phase 4 구현 결과를 무효화하지 않는다.

`protected_paths`는 최소 protected set에 더하는 canonical repository-relative glob만 허용한다. secret allowlist는 위 secret policy의 구조화된 record만 허용하며, broad wildcard 또는 만료 없는 예외는 허용하지 않는다. baseline은 현재 신뢰된 local config와 allowlist의 content hash 및 parser version을 report에 기록한다.

## 검증 설계

### 오프라인 테스트

`python3 -m pytest tests/ -q`는 네트워크와 LLM 호출 없이 다음을 검증한다.

- state transition, cursor, circuit breaker, tier/protected-set, recurrence
- canonical path containment: absolute/`..`/root escape/broken·out-of-root symlink/indeterminate rejection과 in-root project path 허용
- protected-set 최소 항목 및 config 추가-only, `app/../scripts/x`와 symlink alias가 `APPLY`가 되지 않는 회귀
- shared changed-file enforcement: explicit/worktree/hook 동일 결과, 누락 입력 indeterminate, rename/copy old/new path, E2E evidence 누락 차단
- assignment/JSON credential/Bearer secret detection, placeholder/reference non-match, allowlist audit·expiry failure
- strict PR JSON (`NaN`/`Infinity`/duplicate key/trailing data), finite ID/line, dedup 및 convergence state machine
- PR semantic alignment: local SOT rule/evidence extraction, unknown language escalation, LLM-only SAFE_FIX/REJECTED 금지
- PR lifecycle: local input snapshot, body/revision edit 재-disposition, append-only raw local event 및 one-writer atomic persistence/audit write failure block
- PR disposition: safe fix 검증 실패 escalation, rejection/non-actionable 근거, passing local build/lint/test와 open escalation convergence block
- data boundary: trusted local audit의 raw evidence 보존, CLI/report credential literal redaction, raw audit가 렌더 경로로 누출되지 않는 회귀
- code-mapper graph fallback 및 출력 규약
- config schema와 개인 절대경로 금지
- phase/branch/E2E/secret preflight의 실패·통과 fixture
- host 환경변수를 비운 깨끗한 process에서 `state start`, `status`, `resume`이 새 상태 생성·기존 상태 재개·다음 action 계산을 수행하는 fixture
- `HARNESS_HOOKS`/`CODEX_PLUGIN_ROOT`가 없는 상태와 임의 값인 상태에서 같은 controller 결과가 나오는 parity test
- 승인 대기, 누락 산출물, 손상 상태, lock 경합, 복수 활성 feature가 각각 `WAITING_USER`, `BLOCKED_ARTIFACT`, `STATE_INVALID`, `STATE_BUSY`, `AMBIGUOUS_FEATURE`로 비파괴적으로 끝나는 test
- legacy hook 파일이 없거나 실행 불가해도 start/resume가 성공하고 `doctor`만 `ADVISORY_UNAVAILABLE`과 수동 명령을 반환하는 test

### Benchmarks와 live eval

- `benchmarks/sets/train`: 개발 중 관찰용 점수
- `benchmarks/sets/held-out`: 채택 전 회귀 방지용, 수정 금지
- `evals/`: 명시 실행 전용. Codex collaboration 또는 LLM 판단을 사용해도 pytest에 수집되지 않는다.

harness tier 변경의 채택 조건은 `train score > baseline` 이면서 `held-out regression = 0`이다. baseline이 없으면 자동 채택하지 않는다.

### End-to-end acceptance

샘플 저장소에서 다음을 실행해 F1~F10의 최종 증거를 만든다.

1. SDD spec/design/plan 승인 후 worktree에서 하나의 UI 변경을 구현하고, 요구된 E2E evidence로 local gate를 통과한다.
2. 같은 변경 목록을 explicit CLI와 선택적 hook에 각각 주입해 같은 changed-file report와 결과를 확인한다.
3. E2E 없음·기본 브랜치 구현 변경·assignment/JSON/Bearer secret·만료 allowlist 포함 변경이 각각 local preflight에서 실패하는지 확인한다.
4. canonical path 밖/`..` traversal/out-of-root symlink와 harness protected set에 대한 self-improve 입력이 `APPLY`가 아니라 proposal 또는 blocked가 되는지 확인한다.
5. 로컬 리뷰 입력에 코드 수정 요청, 명세 충돌 요청, 설계 질문, malformed ID를 각각 넣어 disposition event를 확인한다. 코멘트 본문 변경은 재-disposition되고, audit write 실패는 escalation 및 수렴 차단이 되어야 한다. credential 성격 evidence는 trusted local audit에 보존될 수 있지만 CLI/report에는 마스킹되어야 한다.
6. local build/lint/test 실패, 미처리 escalation, malformed input이 수렴을 막고 모든 terminal disposition과 검증 통과가 수렴을 허용하는지 확인한다.
7. engineer → compliance → review → test 실패와 재시도 한도를 기록한다.
8. 반복 교훈을 `self-improve`에 전달해 프로젝트 티어 적용과 harness 티어 proposal 분리를 확인한다.

## 마이그레이션 순서

1. `harness_core.state`에 portable controller와 `harness_core` CLI의 `state start/status/resume/transition/doctor`를 먼저 구현하고, host-env-free fixture로 관찰 가능한 start/resume을 고정한다.
2. `skills/sdd`와 `skills/sdd-orchestrator`를 controller 계약으로 이전한다. active skill path에서 `$HARNESS_HOOKS`, `CODEX_PLUGIN_ROOT`, Stop-hook directive와 `pipeline-utils.sh` source를 제거한다.
3. self-improve, pr-converge, code-mapper를 Codex 어댑터로 연결한다.
4. 기존 `hooks/`는 active controller에서 분리한다. 필요한 git wrapper만 `harness`가 명시 설치하는 advisory adapter로 남기고, legacy lifecycle controller는 archive/compatibility 문서 대상으로 표시한다. manifest에는 unsupported hook field를 추가하지 않는다.
5. `harness_core preflight`, 명시적 verify, 선택적 git hook wrapper를 구현한다.
6. SDD/오케스트레이터 역할 프로필을 Codex 협업 계약으로 정리하고, 구세대·중복 프로필을 archive 또는 통합한다.
7. 샘플 E2E를 host 환경변수 없이 통과하고 result 문서에 F1~F10 증거를 연결한다.

## 설계상 제약과 위험

- Codex가 Claude와 동일한 lifecycle hook을 제공한다고 가정하지 않는다. 자동 연쇄가 아니라 idempotent resume를 선택한다.
- 로컬 git hook은 설치하지 않거나 우회할 수 있다. baseline의 gate는 동일 core를 직접 호출하는 preflight/verify이며, 사용자는 완료 전 그 report를 확인해야 한다.
- Codex 협업 에이전트의 동시성은 파일 잠금의 증거가 아니다. ownership 검사와 Wave 의존성으로 충돌을 줄이고, 공유 파일은 순차 처리한다.
- 외부 export·공유는 baseline 기능이 아니다. 나중에 추가하더라도 local audit를 그대로 전송하는 adapter로 취급할 수 없으며, 별도의 대상·동의·sanitization 계약과 검증이 필요하다.

## 미래 export·공유 모드

원격 provider, hosted CI, team sharing, 파일 export는 baseline 밖이다. 향후 필요해져도 local audit JSONL를 그대로 mirror하거나 현재 local completion gate를 원격 증명으로 바꾸지 않는다. 별도 설계에서 최소한 대상, 사용자 opt-in, 전송 범위, redaction/sanitization 규칙, 저장·보존 정책, 실패 시 사용자 경험, 그리고 export fixture를 정의해야 한다. hostile PR·원격 policy 변조·at-rest secret 보관 방어는 그 모드가 실제로 도입될 때의 별도 위협 모델에서 판단한다.

이 기능이 설정되지 않은 신뢰된 local workflow에서는 네트워크 호출·외부 저장·공유용 artifact 생성이 없으며, local preflight와 local review record만으로 완료를 판정한다.

## Spec 수용 기준 매핑

| Spec | 설계 요소 | 수락 증거 |
|---|---|---|
| F1 | 대상 구조, skill 이식 | file inventory + regression test |
| F2 | host-independent state controller, `pipeline.json`, 문서 산출물, transition | host-env-free start/resume, advisory-unavailable, lock/corruption fixture |
| F3 | shared local changed-file enforcement, secret policy, E0~E2 enforcement | explicit/worktree/hook parity report, UI/E2E and JSON/Bearer fixtures |
| F4 | single writer, Wave loop | state transition log |
| F5 | strict local input parser, local semantic extractor, revision lifecycle/event log | malformed JSON/finite-ID, edit, audit failure, local validation, safe-fix/reject/escalate fixtures |
| F6 | canonical containment, plugin/project ownership-aware protected set, `learning` core + benchmark gate | traversal/symlink/protected-set/rollback tests |
| F7 | graph adapter + fallback | 3-state tests |
| F8 | opt-in config schema | unset sync scenario |
| F9 | pytest split + benchmark layout | local command and held-out run |
| F10 | 역할 프로필 계약, 단일 상태 작성자 | agent-profile lint + collaboration scenario |
