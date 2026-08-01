# Codex Harness Parity Spec

## 개요

- 한줄 요약: Moon Harness의 Claude Code 전용 런타임 결합을 Codex에 맞게 대체하면서, 런타임 독립적인 개발·검증·학습 시스템을 Moondex에 동등하게 이식한다.
- 타겟 사용자: 신뢰된 로컬 환경에서 Codex로 자신의 저장소를 개발하는 단일 개발자.
- 핵심 가치: 에이전트가 "완료"라고 말하는 것이 아니라, 명세·상태·로컬 검증 증거가 일치할 때만 완료로 판정한다.

## 문제와 의도한 결과

### 현재 실제 상태

Moondex에는 Codex plugin manifest, `AGENTS.md`, SDD·idea·harness·orchestrator 스킬 및 역할 프롬프트가 이식되어 있다. 그러나 Moon Harness의 결정적 자가개선 코어, PR 수렴, code-mapper, 오프라인 테스트, benchmark/held-out eval은 아직 없다. `hooks/`는 보존되어 있지만 현재 Codex plugin manifest가 노출하는 것은 `skills`뿐이므로, Claude lifecycle hook을 전제로 한 강제 규칙은 실제 Codex 실행에서 보장되지 않는다. 특히 현재 `skills/sdd/SKILL.md`의 시작 절차는 `$HARNESS_HOOKS/enforcement/lib/pipeline-utils.sh`를 직접 source한다. 일반 Codex plugin 실행에는 이 환경변수가 설정되지 않으므로 `/sdd start`가 상태를 초기화하지 못하고 시작 단계에서 실패한다.

### 의도한 사용자 경험

사용자가 Codex에서 Moondex로 기능 작업을 시작하면, 요구사항부터 결과까지의 산출물이 저장소에 남고, 구현은 계획된 작업·소유 범위·검증 기준을 통과해야 완료된다. Codex에 존재하지 않는 Claude hook은 조용히 약화하지 않고, 신뢰된 로컬 실행에서 재현 가능한 preflight·명시적 검증 명령·선택적 git hook으로 대체한다.

### 운영 가정

- 한 명의 개발자가 자신의 로컬 checkout에서 Codex와 검증 명령을 실행한다. 협업자·악의적 PR·신뢰할 수 없는 checkout을 방어 경계로 삼지 않는다.
- GitHub 등 hosted provider, 원격 branch protection, required check, 원격 PR 게시 권한은 기본 완료 조건이 아니다.
- 로컬 정책 파일과 현재 작업 트리는 사용자가 신뢰한다. 이 작업의 목적은 정책 변경 공격을 격리하는 것이 아니라, 실수·누락·회귀를 눈에 보이는 로컬 실패로 만드는 것이다.
- 로컬 Git 저장소는 사용할 수 있으나 원격 push·공유·hosted PR은 기본 작업 흐름에 포함하지 않는다. 로컬 감사 기록은 이 신뢰 경계 안의 디버깅·재개 증거다.

## 범위

### 포함

1. Moon Harness의 런타임 독립 자산을 Moondex로 이식한다.
   - `self-improve`, `pr-converge`, `code-mapper`
   - `hooks/lib/self_improve/`, `hooks/lib/code_mapper/`의 결정적 Python 코어
   - `tests/`, `benchmarks/`, `evals/` 및 필요한 fixtures
2. Claude Code 전용 지시·경로·상태를 Codex용 인터페이스로 치환한다.
3. Claude lifecycle hook에 의존하던 핵심 검증을 Codex에서 실제 실행 가능한 로컬 preflight·명시적 검증 경로로 재구성한다.
4. 개인 경로·개인 wiki 의존을 기본 실행 경로에서 제거하고, 지식 동기화는 명시적 설정이 있을 때만 수행한다.
5. 이식 완료 여부를 자동 검증과 end-to-end 시나리오로 판정한다.

### 제외

- Claude Code plugin, marketplace, settings 또는 hook 등록을 유지·배포하는 일
- Codex에 존재하지 않는 lifecycle event를 흉내 내기 위한 상시 백그라운드 데몬
- 회사 프로젝트의 코드나 비밀 정보를 개인 Compound 저장소에 자동 전송·저장하는 일
- 원본 Moon Harness의 동작과 무관한 신규 워크플로 확장
- hostile PR, 공급망 공격, 원격 정책 변조를 막기 위한 immutable base-policy snapshot 및 원격 ancestry 검증
- hosted CI required check, provider API를 통한 PR 응답 게시, 원격 head SHA와 CI 상태의 암호학적/권한적 증명

## 용어

| 용어 | 런타임 동작 정의 |
|---|---|
| 완료 | 관련 수용 기준, 태스크 검증 명령, 로컬 리뷰·테스트 결과가 기록되고 통과한 상태 |
| hard gate | 지시문이 아니라, 로컬 preflight 또는 명시적 검증에서 실패 시 다음 작업 단계로 진행하지 않게 하는 실행 가능한 검사 |
| Codex adapter | Claude 고유 인터페이스를 Codex의 skill, `AGENTS.md`, 에이전트 협업, shell 검사로 바꾸는 계층 |
| 프로젝트 티어 | 현재 저장소에만 영향을 주는 학습·설정 변경 |
| harness 티어 | 여러 저장소에 배포될 Moondex의 skill·agent·gate 변경 |
| PR 코멘트 | provider의 실제 PR 객체가 없어도 입력 파일·CLI 또는 adapter가 전달하는 로컬 리뷰 요청. 원격 게시를 전제하지 않는다. |

## 기능 요구사항

### F1. 이식 자산 완결성

Moondex는 Moon Harness의 런타임 독립 스킬과 결정적 코어를 포함해야 한다. 각 이식 파일은 Codex 경로·용어·도구를 사용해야 하며, 남은 Claude 전용 참조는 호환성 문서 또는 명시적 비활성 어댑터로 한정한다.

**수용 기준**

- `skills/self-improve/`, `skills/pr-converge/`, `skills/code-mapper/`가 존재한다.
- `hooks/lib/self_improve/`와 `hooks/lib/code_mapper/`의 Python 모듈 및 대응 테스트가 존재한다.
- 사용자 실행 경로의 `SKILL.md`와 `AGENTS.md`에 `.claude/`, `CLAUDE_PLUGIN_ROOT`, Claude 전용 도구 호출이 남아 있지 않다.

### F2. 문서 기반 SDD 상태와 재개

Spec → Design → Plan → Execute → Result의 필수 산출물과 진행 상태를 저장소에서 읽어 재개할 수 있어야 한다. 상태 변경 권한은 오케스트레이터 하나에만 있다.

`/sdd start`와 이후의 재개는 Codex plugin의 기본 실행 경로여야 한다. 이 경로는 `$HARNESS_HOOKS`, Claude Stop hook, session hook 등록, 또는 host 고유 환경변수가 없어도 상태를 초기화하거나 기존 상태를 결정적으로 식별해 재개해야 한다. Codex의 일반 대화 turn은 상태를 읽고 다음에 필요한 명시적 작업 또는 사용자 승인 게이트를 안내·수행하는 재개 계기이며, 지원되지 않는 Stop hook이 백그라운드에서 다음 단계를 자동 실행한다고 주장해서는 안 된다.

기존 hook이 제공하던 보조 자동화는 설치되어 있고 실행 가능할 때만 advisory diagnostic 또는 선택적 편의 기능으로 사용할 수 있다. hook 또는 그 환경변수가 없다는 사실만으로 시작·재개·상태 조회가 실패해서는 안 되며, 오류 대신 누락된 선택 기능, 수동 재개 명령, 현재 상태를 명확히 표시해야 한다.

**수용 기준**

- `docs/sdd/spec/`, `design/`, `task/`, `ORCHESTRATOR_STATE.md`, `result/`가 일관된 경로 규약을 가진다.
- 선행 산출물 또는 사용자 승인 기록이 없으면 다음 단계로 진행하지 않는다.
- 중단된 실행에서 상태 파일만으로 미완료 태스크와 다음 검증 단계를 식별할 수 있다.
- 깨끗한 Codex plugin 환경에서 `$HARNESS_HOOKS`를 설정하지 않은 채 `/sdd start <feature>`를 실행해도, host-specific source 실패 없이 새 상태를 초기화하고 현재 라벨·다음 명시적 작업·필요한 사용자 게이트를 기록 또는 표시한다.
- 같은 feature의 상태가 이미 있을 때 `/sdd start <feature>` 또는 정상 Codex turn의 재개 경로는 상태 파일과 산출물만으로 같은 다음 단계 또는 사용자 게이트를 결정하며, 새 상태를 덮어쓰거나 Stop hook의 비동기 자동 진행을 전제하지 않는다.
- 선택적 hook, hook 스크립트, 또는 관련 환경변수가 없을 때 상태 조회·시작·재개는 성공한다. 결과에는 `advisory unavailable`과 수동으로 실행 가능한 다음 검증/재개 방법이 나타나며, 이를 hard gate 실패로 분류하지 않는다.
- 선택적 hook이 설치된 경우에도 상태 전이는 오케스트레이터가 기록한 명시적 전이와 동일한 규약을 사용한다. hook 유무로 사용자 승인 게이트를 우회하거나 서로 다른 다음 라벨을 만들 수 없다.

### F3. Codex용 로컬 hard gate

TDD/E2E 요구와 민감 정보 보호는 Codex에서 실행되는 로컬 검사로 검증해야 한다. 지원되지 않는 hook은 문서 규칙으로만 대체하지 않는다. 브랜치 보호는 사용자의 로컬 작업 흐름을 돕는 선택적 검사이며 hosted branch protection을 뜻하지 않는다.

**수용 기준**

- 각 기존 gate에 대해 Codex 대체 위치(오케스트레이터 preflight, 선택적 git hook 또는 명시적 검증 명령)가 문서화된다.
- 기본 브랜치에서 Phase 4 구현 커밋을 시도하는 시나리오는 실패한다.
- 명시적 changed-file 검사와 선택적 hook은 동일한 shared enforcement 경로를 사용한다. 현재 작업의 변경 범위와 changed-file 근거, 적용 규칙, 통과/실패 결과를 남긴다.
- 요구된 E2E가 없는 UI 변경은 실패한다.
- 노출 가능한 secret은 실패한다. 최소한 assignment 형태, JSON object의 credential 성격 key에 연결된 literal 값, `Authorization: Bearer <literal>` 형태를 탐지한다. 환경변수 참조·템플릿 placeholder·명시 allowlist는 노출 credential으로 오인하지 않아야 하며, allowlist 사용은 근거와 함께 기록한다.
- 검사 오류는 원인과 수정 방법을 출력한다.

원격 push 전체 범위/첫 push ancestry, hook과 hosted CI의 완전한 parity, 신뢰되지 않은 PR head가 policy를 바꾸지 못하게 하는 정책 snapshot은 **선택적 advisory extension**이다. 로컬 완료를 막는 조건이 아니다.

### F4. 구현 품질 루프

Wave 내 태스크는 engineer → compliance → review → test 순서로 처리하며, 실패는 원인과 함께 재시도 또는 에스컬레이션한다.

**수용 기준**

- 각 태스크의 담당자, 소유 범위, 반복 횟수, 검증 결과가 상태 파일에 남는다.
- 리뷰 또는 테스트 실패 태스크는 `complete`가 될 수 없다.
- 동일 태스크의 실패가 한도를 넘으면 자동 수정 대신 사람에게 에스컬레이션한다.

### F5. PR 수렴

`pr-converge`는 로컬에서 제공된 리뷰 코멘트, 빌드·린트·테스트 결과를 관찰하고, 안전하게 자동 수정 가능한 신호만 처리하는 리뷰 보조 워크플로다. 새로 수집된 모든 actionable 변경 요청은 명세·설계·소유 범위·검증 증거와의 정합성을 판정하고, 안전한 수정, 사유 있는 거부, 또는 사용자 에스컬레이션 중 하나로 종결한다.

**수용 기준**

- adapter가 제공하는 conversation, inline, review-body 형식의 신규 코멘트를 중복 없이 수집한다. provider 연결이 없으면 fixture 또는 로컬 입력으로 같은 core를 검증할 수 있어야 한다.
- core와 adapter 경계에서 받는 코멘트 입력은 strict JSON 또는 동등하게 명세된 엄격한 구조여야 한다. 표준 JSON이 아닌 상수(`NaN`, `Infinity` 등), 누락·비정상 ID, 타입 불일치 입력은 `BLOCKED`로 처리하며 수렴 또는 자동 수정으로 진행하지 않는다. 숫자 ID를 허용하는 경우에는 finite 값과 정수/문자열 식별자 규약을 검증한다.
- 각 신규 actionable 변경 요청에는 중복 제거에 쓰이는 안정된 source identity와 다음을 포함한 machine-readable disposition record가 남는다: 요청 식별자, 판정 시각, 정합성 판정(명세·설계·소유 범위·검증 증거), 결정(`SAFE_FIX` | `REJECTED` | `ESCALATED`), 사람이 읽을 수 있는 근거, 관련 증거 링크/명령 결과, 그리고 수정 시 변경·검증 결과 또는 에스컬레이션 대상.
- `SAFE_FIX`는 요청이 승인된 범위와 소유권 안에 있고 필요한 검증 증거를 만들 수 있을 때만 선택한다. 수정·검증 실패 또는 범위 확장은 `ESCALATED`로 전환한다.
- `REJECTED`는 요청이 승인된 명세·설계·소유 범위 또는 검증 증거와 충돌할 때만 선택하며, 충돌 근거와 대안을 로컬 disposition record에 남긴다.
- `ESCALATED`는 설계 판단, 상충하는 증거, 소유권 불명확, 외부 의존성, 또는 안전한 자동 수정/거부를 증명할 수 없는 경우에 사용하며, 필요한 사람의 결정 내용을 기록한다.
- actionable 요청은 disposition 없이 종료·중복 무시·수렴 계산에서 제외될 수 없다. 비-actionable로 분류한 입력도 그 분류 근거를 기록한다.
- 반복 실패 및 총 반복 횟수에 circuit breaker가 적용된다.
- 기본 브랜치 직접 push 또는 force push는 자동화하지 않는다.
- 수렴은 로컬 빌드·린트·테스트가 통과하고, 모든 actionable 요청의 최종 disposition과 필요한 로컬 검증 증거가 있으며, actionable 신호 0, 미처리 에스컬레이션 0일 때만 선언한다.

hosted CI green, exact remote head SHA, required-check ID, 원격 PR 응답 게시와 게시 실패 fail-closed는 **선택적 advisory extension**이다. provider adapter가 있을 때 기록할 수 있지만, 로컬 수렴·완료의 필수 증거는 아니다.

### F6. 자가개선의 안전한 적용

작업 교훈은 provenance와 함께 수집하고, 반복성·중복·일반성·critic 검증을 거친다. 프로젝트 티어만 제한적으로 자동 적용할 수 있고, harness 티어는 항상 변경 제안으로 남긴다.

**수용 기준**

- raw learning 입력은 커서 기반으로 한 번만 처리하며 원본을 수정하지 않는다.
- 적용 대상 경로는 문자열 prefix가 아니라 저장소 root 기준으로 정규화·containment 검증한 경로로 티어를 판정한다. 절대경로, `..` traversal, 저장소 밖으로 향하는 symlink, 또는 정규화/containment를 증명할 수 없는 경로는 자동 적용 대상이 될 수 없으며 `PROPOSAL` 또는 `BLOCKED`로 남긴다. 이는 신뢰된 로컬 작업에서도 의도치 않은 대상 편집을 막기 위한 안전 경계다.
- harness 티어 파일은 자동 편집되지 않는다. 이 티어에는 plugin 배포·실행·검증 경계를 구성하는 최소 `skills/`, `agents/`, `.codex-plugin/`, `harness_core/`, `scripts/`, `.github/`, `hooks/`, `tests/`, `benchmarks/`, `evals/` 및 그 하위 경로가 포함된다. 보호 집합의 추가 항목은 구성으로 확장할 수 있지만 축소할 수 없다.
- project-tier 자동 적용은 정규화 후 보호 집합 밖에 있다는 것과 대상 파일의 저장소 내 위치를 모두 증명해야 한다. 예를 들어 `app/../scripts/x`는 `scripts/x`로 판정되어 자동 적용할 수 없다.
- 자동 적용은 rollback 기록과 건별 상한을 가진다.
- benchmark score 향상과 held-out 회귀 없음이 확인되기 전에는 harness 변경을 채택하지 않는다.

### F7. code-mapper와 변경 영향 확인

구현·리뷰 전에 code-mapper는 가능한 경우 코드 그래프를 사용하고, 불가능하면 명시적으로 근사적 grep 폴백을 사용해 진입점·호출 관계·영향 범위를 제공한다.

**수용 기준**

- graph 도구 healthy/not-initialized/unavailable의 세 상태를 구분한다.
- 폴백 결과가 근사임을 표시하고, 가짜 확신을 피한다.
- 결과는 장기 상태를 오염시키지 않는 일시적 컨텍스트다.

### F8. 로컬 데이터 경계

Moondex 기본 설치와 기본 실행은 특정 사용자의 홈 디렉터리, 개인 Compound wiki 또는 개인 계정에 의존하지 않는다. 지식 동기화와 provider·공유·외부 export는 사용자가 대상과 권한을 명시적으로 설정한 경우에만 실행하는 미래 확장이다.

로컬 리뷰·자가개선의 append-only 감사 기록은 신뢰된 개인 checkout 안에서 처분 근거와 원본 evidence를 보존할 수 있다. 이는 외부 노출 저장소로 취급하지 않는다. 반대로 사용자에게 표시하는 CLI/로컬 보고서와 명시적으로 export·공유하는 산출물은 credential 성격의 값을 마스킹한 evidence만 표시해야 한다. 이 요구사항은 신뢰된 로컬 감사 파일의 at-rest 비밀성 또는 원문 저장 금지를 뜻하지 않는다.

**관찰 가능한 결과**

- 같은 리뷰 evidence를 처리했을 때, 신뢰된 로컬 감사 기록에는 처분을 재현·검토할 원문 근거가 남을 수 있고, CLI/로컬 보고서에는 그 credential 값이 나타나지 않는다.
- 사용자가 sync·provider 게시·파일 export를 설정하지 않으면, 기본 실행은 해당 외부 대상에 데이터를 전송하거나 저장하지 않는다.

**수용 기준**

- plugin source에 `/Users/moon/Workspace/moon-compound` 같은 개인 절대경로가 없다.
- 지식 sync 미설정 시 구현 완료를 실패시키지 않고 `SKIPPED` 결과를 기록한다.
- CLI와 사람이 읽는 로컬 보고서는 credential 성격 key에 연결된 literal evidence를 마스킹한다. 이 검사는 감사 JSONL의 원문 evidence 보존을 실패로 처리하지 않는다.
- 명시적으로 설정한 외부 전송·provider 게시·공유·export가 일어나는 경우에만 대상, 사용자 설정 근거, 그리고 적용한 마스킹 정책을 결과 문서에 기록한다. 설정이 없으면 외부 전송·저장은 발생하지 않는다.

### F9. 측정과 회귀 방지

결정적 로직은 네트워크·LLM 호출 없이 테스트할 수 있어야 한다. LLM 판단이 필요한 평가는 별도 live eval로 분리하며, held-out 시나리오를 포함한다.

**수용 기준**

- 오프라인 테스트는 단독 실행 가능하고 live eval을 수집하지 않는다.
- train/held-out benchmark 분할이 존재한다.
- 변경 전후 점수와 held-out 결과를 기록할 수 있다.

### F10. Codex용 역할 프로필과 협업 계약

Moondex의 `agents/`는 Codex가 자동 등록하는 실행 단위가 아니라, 오케스트레이터가 협업 에이전트에 주입하는 역할 프로필로 동작해야 한다. 각 활성 프로필은 Codex 호환 입력·출력·소유권 계약을 가져야 하며, Claude 도구명·개인 경로·구세대 문서 경로에 의존해서는 안 된다.

**수용 기준**

- 활성 SDD 역할은 공통 결과 계약(`DONE`, `DONE_WITH_CONCERNS`, `NEEDS_CONTEXT`, `BLOCKED`)과 변경 파일·검증 명령·증거를 반환한다.
- worker는 오케스트레이터 상태 파일을 직접 수정하지 않는다.
- agent 프로필의 `tools`, `model`, `Agent(...)`, `TeamCreate`, Claude Chrome MCP 등 Claude 전용 실행 문법은 Codex 협업 지침 또는 host-neutral capability로 치환된다.
- `docs/spec-design/` 등 구세대 경로를 쓰는 프로필은 현재 `docs/sdd/` 계약으로 이관하거나 명시적으로 archive 처리한다.
- 개인 Compound 동기화 역할은 조직 설정이 없는 경우 `SKIPPED`를 반환하며 개인 경로를 기본값으로 갖지 않는다.

## 비기능 요구사항

- 핵심 상태 전이·회로 차단·티어 판정·커서 처리는 Python stdlib 중심의 결정적 코드로 구현한다.
- 실패 시에는 진행을 허용하는 대신 누락을 숨기지 않고, 안전한 상태에서 중단·에스컬레이션한다.
- 설치·검증 절차는 개발자의 macOS 로컬 환경에서 재현 가능해야 한다. CI 연동은 선택 사항이다.
- Moondex 자체 변경은 기존 사용자 변경을 덮어쓰지 않는다.

## 구현 순서와 게이트

1. 자산 차이와 Codex adapter 계약을 설계 문서로 확정한다.
2. 결정적 코어·테스트·benchmark substrate를 이식하고 오프라인 검증을 통과시킨다.
3. `self-improve`, `pr-converge`, `code-mapper` 스킬을 Codex 경로와 도구로 이식한다.
4. hard gate의 Codex 실행 경로를 구현하고 실패 시나리오로 검증한다.
5. 실제 샘플 프로젝트에서 SDD 전체 흐름과 로컬 리뷰 요청 수렴을 수행한다.
6. 결과 문서에 수용 기준별 증거·제약·미해결 항목을 기록한다.

## 완료 판정

이 작업은 F1~F10의 로컬 baseline 수용 기준에 대응하는 자동 테스트 또는 재현 가능한 로컬 실행 증거가 모두 `docs/sdd/result/`에 연결되고, 로컬 데이터 경계(F8)가 검토된 뒤에만 완료다. optional advisory extension의 CI·원격 provider 증거는 있으면 기록하되 완료를 막지 않는다. 단순 파일 복사 또는 스킬 문서 존재만으로는 완료가 아니다.
