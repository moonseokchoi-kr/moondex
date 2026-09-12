# 2026-09-13 기존 스킬 정리

> 구현 이력이다. 기존 승인 요구와 d5 실행 기준을 대체하지 않는다.

## 요청과 범위

사용자 요청: “기존 스킬들에 대한 정리도 진행하자”. 기준 commit은 `2f05714`다.
새 실행 구조 이후로 미뤘던 스킬 의존성과 옛 workflow 지침을 정리한다.
제품의 승인/retry/evidence 계약, 과거 승인과 설계 revision은 변경하지 않는다.
현재 세션에서 의존성 조사 → 공개 표면 정리 → 검증 순서로 수행했다.

## 관찰된 문제와 변경

| 대상 | 기존 문제 | 변경 |
|---|---|---|
| 공용 런처 | execute와 mapper/PR/learning이 sdd 폴더를 참조 | `runtime/`으로 이동, 실제 설치 경로 기준 root 계산과 모든 소비자 갱신 |
| 퇴역 SDD 3개 | 더 이상 실행하지 않지만 skills 목록과 설치 의존성에 남음 | `legacy/`로 이동, discovery/active surface/inventory에서 제외 |
| idea-workshop | Phase 순서, 인용/문서 수 기반 게이트와 AI 재디스패치 | 작업에 필요한 발산/검증/PRD 선택, 현재 세션 기본, 승인된 위임만 execute로 연결 |
| harness | 초기화 시 hook·학습 추출·정책 승격 설치 | 관찰 근거 기반 audit/setup, 자동 설치 제거, 명시 self-improve 분리 |
| handoff | docs/sdd와 Phase로 상태 추정, 문서 저장 후 추가 확인 | script status 조회, revision/질문/진행 process/증거 포인터와 재개 문맥 기록 |
| git-worktree | SDD 단계 진입, raw Git 생성, 자동 snapshot commit | 요청된 base commit과 실제 HEAD 검증, Orca 관리 경로 존중, 자동 commit/정리 제거 |
| adversarial-review | 고정 모델/에이전트와 수정·재비판 루프 | 현재 세션의 원인 분석, 결함 분류와 execute feedback 연결 |
| pr-converge | spec/design 문서 형식 의존으로 읽힐 수 있음 | 기존 alignment 키가 승인 요구/설계 판단을 뜻함을 명확히 하고 전체 실행 완료와 구분 |
| code-mapper/self-improve | SDD 런처 의존 | 독립 런처 사용. 분석 후보와 증거를 구분하고 자가개선은 명시 호출 유지 |
| 미사용 host-configs | 지원되지 않는 호스트/자동 hook 지침 | `legacy/harness/`로 이동 |

공개 스킬은 14개에서 11개가 됐다. Stitch 전용 design-md/enhance-prompt는 별도 기능이므로
삭제 여부 확인에 답변이 없는 상태에서는 유지했다. 사용자의 전체 삭제 결정으로 해석하지 않았다.
기존 agents 역할 프로필은 자동 등록/주입되지 않는 데이터이며 새 스킬이 옛 프로필을 필수로 불러오지 않는다.
legacy 자료는 이동 전 commit과 byte 단위 일치를 확인했다. legacy 내부의 옛 경로/지침은 역사 기록이다.

## 검증 계약과 결과

- 새 위치의 launcher를 opaque installed path에서 실행한다. 설치 파일 목록에 legacy가 없어도
  execute의 실제 구현/gate/통합과 mapper/PR/learning 동작이 통과해야 한다.
- 잘못된 approval/receipt, scope escape, runtime 파일 변조 차단을 유지한다.
- 공개 스킬 발견 목록과 참조 경로, recursive import closure와 inventory를 검사한다.
- 구형 결과 처리와 rate-limit helper의 직접 회귀 검증은 legacy 위치에서 보존한다.
- 종료한 SDD의 공개 라우팅/고정 조사 wave에 대한 옛 문구 검사는 새 discovery/경로 검사로 교체한다.
  기존 실행 안전성 시험이나 실제 browser 검증은 제거하지 않는다.

대상 테스트 75개 통과. 스킬별 validator와 필수 정적 검사 38개 통과.
전체 pytest **368 passed / 123.95s**. 실제 browser E2E 포함.
검증 로그·정적 영수증·최종 source hash: `/Users/moon/Workspace/moondex-local-evidence/skill-cleanup-20260913-001552`.
지침 검토는 AI가 모든 미래 요청에서 그대로 행동한다는 보장이 아니다. 실제 설치 동작과
검증 command 실행 증거, 문서의 권한/의존성 점검을 구분한다.

## 후속 경계

main 병합·push·플러그인 재설치는 이번 작업에 포함하지 않는다.

## 후속 결정: Stitch 전용 스킬 제외

사용자가 “Stitch전용스킬도 필요없지 않을까?”라고 답하여 design-md/enhance-prompt도
공개 목록에서 제외했다. 앞선 유지 기록은 그 답변 이전의 판단이다.
두 스킬을 `legacy/`로 옮겨 원문 hash를 보존했고 active surface에서도 제거했다.
참조는 이미 보관된 ui-designer 프로필에만 남아 있어 실행 기능의 의존성은 끊기지 않는다.
최종 공개 스킬은 **9개**다. 런타임과 승인 기준의 변경은 없다.

후속 검증: **54 passed in 3.61s**, 필수 정적 검사28개 통과.
증거: `/Users/moon/Workspace/moondex-local-evidence/stitch-removal-20260913-001733`. 전체368개 통과 기록은 직전 스킬 정리 시점이며, 이번 변경은 패키지/설치/이식성 범위로 재검증했다.

## main 반영 요청과 최종 검증

사용자가 스킬 구성을 확인한 뒤 main 병합을 요청했다. fetch한 origin/main은 기준 commit
`fbf072e`와 같으며, main의 기존 로컬 변경은 이번 커밋에 포함하지 않는다.
최종 전체 검증: **368 passed in 123.55s (0:02:03)**, 필수 정적 검사28개 통과.
검증 및 병합 영수증 보관 위치: `/Users/moon/Workspace/moondex-local-evidence/main-merge-20260913-002632`.
