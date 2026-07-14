# Codex Harness Parity Spec

## 개요

- 한줄 요약: Moon Harness의 Claude Code 전용 런타임 결합을 Codex에 맞게 대체하면서, 런타임 독립적인 개발·검증·학습 시스템을 Moondex에 동등하게 이식한다.
- 타겟 사용자: 회사에서 Codex를 사용해 여러 저장소의 개발 라이프사이클을 운영하는 개발팀.
- 핵심 가치: 에이전트가 "완료"라고 말하는 것이 아니라, 명세·상태·검증·외부 신호가 일치할 때만 완료로 판정한다.

## 문제와 의도한 결과

### 현재 실제 상태

Moondex에는 Codex plugin manifest, `AGENTS.md`, SDD·idea·harness·orchestrator 스킬 및 역할 프롬프트가 이식되어 있다. 그러나 Moon Harness의 결정적 자가개선 코어, PR 수렴, code-mapper, 오프라인 테스트, benchmark/held-out eval은 아직 없다. `hooks/`는 보존되어 있지만 현재 Codex plugin manifest가 노출하는 것은 `skills`뿐이므로, Claude lifecycle hook을 전제로 한 강제 규칙은 실제 Codex 실행에서 보장되지 않는다.

### 의도한 사용자 경험

사용자가 Codex에서 Moondex로 기능 작업을 시작하면, 요구사항부터 결과까지의 산출물이 저장소에 남고, 구현은 계획된 작업·소유 범위·검증 기준을 통과해야 완료된다. Codex에 존재하지 않는 Claude hook은 조용히 약화하지 않고, 동등하거나 더 보수적인 preflight/CI/오케스트레이터 검증으로 대체한다.

## 범위

### 포함

1. Moon Harness의 런타임 독립 자산을 Moondex로 이식한다.
   - `self-improve`, `pr-converge`, `code-mapper`
   - `hooks/lib/self_improve/`, `hooks/lib/code_mapper/`의 결정적 Python 코어
   - `tests/`, `benchmarks/`, `evals/` 및 필요한 fixtures
2. Claude Code 전용 지시·경로·상태를 Codex용 인터페이스로 치환한다.
3. Claude lifecycle hook에 의존하던 hard gate를 Codex에서 실제 실행 가능한 검증 경로로 재구성한다.
4. 회사 사용을 위해 개인 경로·개인 wiki 의존을 기본값에서 제거하고, 지식 동기화는 명시적 설정이 있을 때만 수행한다.
5. 이식 완료 여부를 자동 검증과 end-to-end 시나리오로 판정한다.

### 제외

- Claude Code plugin, marketplace, settings 또는 hook 등록을 유지·배포하는 일
- Codex에 존재하지 않는 lifecycle event를 흉내 내기 위한 상시 백그라운드 데몬
- 회사 프로젝트의 코드나 비밀 정보를 개인 Compound 저장소에 자동 전송·저장하는 일
- 원본 Moon Harness의 동작과 무관한 신규 워크플로 확장

## 용어

| 용어 | 런타임 동작 정의 |
|---|---|
| 완료 | 관련 수용 기준, 태스크 검증 명령, 리뷰·테스트 결과가 기록되고 통과한 상태 |
| hard gate | 지시문이 아니라, 실패 시 다음 단계·커밋·배포를 막는 실행 가능한 검사 |
| Codex adapter | Claude 고유 인터페이스를 Codex의 skill, `AGENTS.md`, 에이전트 협업, shell/CI 검사로 바꾸는 계층 |
| 프로젝트 티어 | 현재 저장소에만 영향을 주는 학습·설정 변경 |
| harness 티어 | 여러 저장소에 배포될 Moondex의 skill·agent·gate 변경 |

## 기능 요구사항

### F1. 이식 자산 완결성

Moondex는 Moon Harness의 런타임 독립 스킬과 결정적 코어를 포함해야 한다. 각 이식 파일은 Codex 경로·용어·도구를 사용해야 하며, 남은 Claude 전용 참조는 호환성 문서 또는 명시적 비활성 어댑터로 한정한다.

**수용 기준**

- `skills/self-improve/`, `skills/pr-converge/`, `skills/code-mapper/`가 존재한다.
- `hooks/lib/self_improve/`와 `hooks/lib/code_mapper/`의 Python 모듈 및 대응 테스트가 존재한다.
- 사용자 실행 경로의 `SKILL.md`와 `AGENTS.md`에 `.claude/`, `CLAUDE_PLUGIN_ROOT`, Claude 전용 도구 호출이 남아 있지 않다.

### F2. 문서 기반 SDD 상태와 재개

Spec → Design → Plan → Execute → Result의 필수 산출물과 진행 상태를 저장소에서 읽어 재개할 수 있어야 한다. 상태 변경 권한은 오케스트레이터 하나에만 있다.

**수용 기준**

- `docs/sdd/spec/`, `design/`, `task/`, `ORCHESTRATOR_STATE.md`, `result/`가 일관된 경로 규약을 가진다.
- 선행 산출물 또는 사용자 승인 기록이 없으면 다음 단계로 진행하지 않는다.
- 중단된 실행에서 상태 파일만으로 미완료 태스크와 다음 검증 단계를 식별할 수 있다.

### F3. Codex용 hard gate

역할 분리, 브랜치 보호, TDD/E2E 요구, 민감 정보 보호는 Codex에서 실행되는 검사로 검증해야 한다. 지원되지 않는 hook은 문서 규칙으로만 대체하지 않는다.

**수용 기준**

- 각 기존 gate에 대해 Codex 대체 위치(오케스트레이터 preflight, git hook, CI 또는 명시적 검증 명령)가 문서화된다.
- 기본 브랜치에서 Phase 4 구현 커밋을 시도하는 시나리오는 실패한다.
- 요구된 E2E가 없는 UI 변경과 노출 가능한 secret은 검증에서 실패한다.
- 검사 오류는 원인과 수정 방법을 출력한다.

### F4. 구현 품질 루프

Wave 내 태스크는 engineer → compliance → review → test 순서로 처리하며, 실패는 원인과 함께 재시도 또는 에스컬레이션한다.

**수용 기준**

- 각 태스크의 담당자, 소유 범위, 반복 횟수, 검증 결과가 상태 파일에 남는다.
- 리뷰 또는 테스트 실패 태스크는 `complete`가 될 수 없다.
- 동일 태스크의 실패가 한도를 넘으면 자동 수정 대신 사람에게 에스컬레이션한다.

### F5. PR 수렴

`pr-converge`는 CI·빌드·린트·코드 수정 요청을 관찰하고, 안전하게 자동 수정 가능한 신호만 처리한다. 설계·질문·트레이드오프는 사용자 판단으로 올린다.

**수용 기준**

- 모든 신규 PR 코멘트 종류(conversation, inline, review body)를 중복 없이 수집한다.
- 반복 실패 및 총 반복 횟수에 circuit breaker가 적용된다.
- 기본 브랜치 직접 push 또는 force push를 하지 않는다.
- 수렴은 CI green, actionable 신호 0, 미처리 에스컬레이션 0일 때만 선언한다.

### F6. 자가개선의 안전한 적용

작업 교훈은 provenance와 함께 수집하고, 반복성·중복·일반성·critic 검증을 거친다. 프로젝트 티어만 제한적으로 자동 적용할 수 있고, harness 티어는 항상 변경 제안으로 남긴다.

**수용 기준**

- raw learning 입력은 커서 기반으로 한 번만 처리하며 원본을 수정하지 않는다.
- harness 티어 파일은 자동 편집되지 않는다.
- 자동 적용은 rollback 기록과 건별 상한을 가진다.
- benchmark score 향상과 held-out 회귀 없음이 확인되기 전에는 harness 변경을 채택하지 않는다.

### F7. code-mapper와 변경 영향 확인

구현·리뷰 전에 code-mapper는 가능한 경우 코드 그래프를 사용하고, 불가능하면 명시적으로 근사적 grep 폴백을 사용해 진입점·호출 관계·영향 범위를 제공한다.

**수용 기준**

- graph 도구 healthy/not-initialized/unavailable의 세 상태를 구분한다.
- 폴백 결과가 근사임을 표시하고, 가짜 확신을 피한다.
- 결과는 장기 상태를 오염시키지 않는 일시적 컨텍스트다.

### F8. 회사 환경의 데이터 경계

Moondex 기본 설치와 기본 실행은 특정 사용자의 홈 디렉터리, 개인 Compound wiki 또는 개인 계정에 의존하지 않는다. 지식 동기화는 조직이 지정한 저장소·권한·보존 정책으로 명시적으로 설정한 경우에만 실행한다.

**수용 기준**

- plugin source에 `/Users/moon/Workspace/moon-compound` 같은 개인 절대경로가 없다.
- 지식 sync 미설정 시 구현 완료를 실패시키지 않고 `SKIPPED` 결과를 기록한다.
- 외부 전송 또는 저장이 일어나는 경우 대상과 근거가 결과 문서에 기록된다.

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
- 설치·검증 절차는 macOS와 회사의 표준 CI 환경에서 재현 가능해야 한다.
- Moondex 자체 변경은 기존 사용자 변경을 덮어쓰지 않는다.

## 구현 순서와 게이트

1. 자산 차이와 Codex adapter 계약을 설계 문서로 확정한다.
2. 결정적 코어·테스트·benchmark substrate를 이식하고 오프라인 검증을 통과시킨다.
3. `self-improve`, `pr-converge`, `code-mapper` 스킬을 Codex 경로와 도구로 이식한다.
4. hard gate의 Codex 실행 경로를 구현하고 실패 시나리오로 검증한다.
5. 실제 샘플 프로젝트에서 SDD 전체 흐름과 PR 수렴을 수행한다.
6. 결과 문서에 수용 기준별 증거·제약·미해결 항목을 기록한다.

## 완료 판정

이 작업은 F1~F10의 수용 기준에 대응하는 자동 테스트 또는 재현 가능한 실행 증거가 모두 `docs/sdd/result/`에 연결되고, 회사 환경 데이터 경계(F8)가 검토된 뒤에만 완료다. 단순 파일 복사 또는 스킬 문서 존재만으로는 완료가 아니다.
