# ORCHESTRATOR_STATE.md Schema

오케스트레이터가 런타임에 프로젝트의 `docs/sdd/ORCHESTRATOR_STATE.md`에 기록하는 실행 현황 문서의 스키마.
git이 추적하므로 손상 시 복구 가능하고, 변경 이력이 commit log에 남는다. 프로젝트 lifecycle의 유일한 source of truth는 프로젝트 로컬 컨트롤러다. `SPEC`, `DESIGN`, `PLAN`에서는 SDD coordinator가 taskmaster payload와 승인 근거를 검증해 이 문서를 초기화하고 controller transition을 호출한다. `PLAN → EXECUTE` 성공 직후 권한을 execution orchestrator에 단 한 번 이관하며, 그 이후에는 오케스트레이터만 이 현황 문서를 쓰며 controller transition을 호출한다. 두 writer는 동시에 활성화되지 않는다. 워커, 팀 리더, taskmaster, reviewer, tester는 변경 대신 `agents/SDD_WORKER_CONTRACT.md`의 공통 result envelope와 근거를 반환한다.

## 파일 위치

```
<project-root>/docs/sdd/ORCHESTRATOR_STATE.md
```

Phase 4 런타임 학습 버퍼:

```
<project-root>/.harness/state/sdd/<feature>/<run-id>/events.jsonl
<project-root>/.harness/state/sdd/<feature>/<run-id>/learning-buffer.md
```

UX Designer가 반환한 E2E 설정 payload는 handoff 전 SDD coordinator가 검증한 뒤 프로젝트 로컬 컨트롤러 소유의 다음 sidecar에 적용한다. 워커는 이 경로를 직접 생성하거나 변경하지 않는다.

```text
<project-root>/.harness/state/e2e-config.json
```

## 스키마

```markdown
# Orchestrator State

## 메타
- develop 문서: <path to develop document>
- spec 문서: <path to spec document>
- 시작 시각: <ISO 8601>
- 마지막 갱신: <ISO 8601>
- Controller phase: SPEC | DESIGN | PLAN | EXECUTE | RESULT
- Controller authority owner: SDD coordinator (SPEC | DESIGN | PLAN) | execution orchestrator (EXECUTE | RESULT)
- Controller evidence: <마지막 `state status`/`state resume` code, next_step, checked_at>

## 팀 배정
| Team | 담당 Wave | 선행 팀 |
|------|-----------|---------|
| 1    | Wave 1~4  | 없음 |
| 2    | Wave 5~7  | Team 1 |
| 3    | Wave 8~11 | Team 2 |

> Wave가 모두 순차 의존이거나 팀이 1개이면 이 섹션을 생략하고 기존 단일 오케스트레이터 모드로 실행.

팀 실행 가능 여부는 선행 task의 `complete` 근거와 DAG에서 계산한다. 별도 team lifecycle 상태를 저장하지 않는다.

## Wave 구성
| Wave | 태스크 | 의존성 |
|------|--------|--------|
| 1 | T-1 | 없음 |
| 2 | T-2, T-14 | T-1 |
| 3 | T-3, T-4, T-5, T-6, T-7 | T-1 |
| ... | ... | ... |

## 현재 진행
- 현재 Wave: <N>
- 완료 Wave: <list>

## 태스크 상태
| ID | Wave | Stage | Iteration | Agent | 비고 |
|----|------|--------|-----------|-------|------|
| T-1 | 1 | complete | 1 | - | |
| T-3 | 3 | implementing | 1 | sdd-flutter-engineer | 실행 중 |
| T-4 | 3 | reviewing | 1 | sdd-reviewer | 리뷰 중 |
| T-5 | 3 | testing | 2 | sdd-test-automator | 1회차: 타입 불일치 |

아직 디스패치되지 않은 task는 DAG에는 존재하지만 이 표에 stage 행을 만들지 않는다. 첫 Engineer 디스패치 직전에 `implementing` 행을 추가한다.

### Stage 값
- `implementing` — Engineer Agent가 구현 중
- `verifying` — Compliance Checker가 요구사항/설계 정합성을 검증 중
- `reviewing` — Reviewer Agent가 리뷰 중
- `fixing` — Engineer Agent가 리뷰 피드백 반영 중
- `testing` — Test Automator Agent가 검증 중
- `complete` — 완료 (리뷰 + 테스트 통과)

### Worker result와 단계 전환

| 현재 task 단계 | 요구 worker 결과 | 다음 task 단계 |
|---|---|---|
| `implementing` / `fixing` | `Status: DONE` 또는 `DONE_WITH_CONCERNS` | `verifying` |
| `verifying` | passing status + `Verdict: COMPLIANCE_PASS` | `reviewing` |
| `verifying` | `Status: BLOCKED` + `Verdict: COMPLIANCE_FAIL` | iteration 증가 후 `fixing` |
| `reviewing` | passing status + `Verdict: REVIEW_PASS` | `testing` |
| `reviewing` | `Status: BLOCKED` + `Verdict: REVIEW_FAIL` | iteration 증가 후 `fixing` |
| `testing` | passing status + `Verdict: TEST_PASS` | `complete` |
| `testing` | `Status: BLOCKED` + `Verdict: TEST_FAIL` | iteration 증가 후 `fixing` |

`NEEDS_CONTEXT`, 모순된 status/verdict 조합, stage verdict 누락은 전환하지 않는다. 팀 준비는 `Status: DONE` + `Verdict: READY`로 표현하며 `READY`는 task 또는 lifecycle status가 아니다.

## 에이전트 배정
- 오케스트레이터: 메인 세션
- Engineer 슬롯 1: <T-ID> | idle
- Engineer 슬롯 2: <T-ID> | idle
- Engineer 슬롯 3: <T-ID> | idle
- Engineer 슬롯 4: <T-ID> | idle
- Reviewer: <T-ID> | idle
- Test Automator: <T-ID> | idle

## 파일 소유권
| 태스크 | 소유 파일/디렉토리 |
|--------|-------------------|
| T-3 | lib/models/ |
| T-4 | lib/repositories/transaction_repository.dart |
| T-5 | lib/repositories/category_repository.dart |

## 이력
- [HH:MM] T-1 구현 완료 → 리뷰 통과 → 테스트 통과
- [HH:MM] T-3 구현 완료 → 리뷰 피드백: "타입 불일치" → 재구현 중
- [HH:MM] learning buffer append: confirmed_incident user_correction
- [HH:MM] 리밋 감지: worker interruption evidence 기록; controller status/resume 결과 확인
- [HH:MM] 선택적 compound sync 시작
- [HH:MM] compound raw snapshot 생성: raw/projects/<feature>/sdd-<date>-<run-id>/
- [HH:MM] compound wiki 업데이트 완료: wiki/<page>.md, wiki/log.md

## 중단 근거 (worker 중단 시 기록)
### T-3 (implementing, iteration 1)
마지막 Agent 응답 요약: ...

### T-4 (reviewing, iteration 1)
마지막 Agent 응답 요약: ...
```

## 사용 규칙

1. **Phase 3(Plan)에서 초기 생성**: taskmaster가 controller phase `PLAN`, controller evidence, Wave/DAG payload를 반환하고, SDD coordinator가 검증 후 문서를 생성한다. 이 시점의 유일한 transition caller는 SDD coordinator다.
2. **Phase 4(Execute) 진입 시**: SDD coordinator가 필수 artifact와 명시적 plan 승인을 검증하고 `PLAN → EXECUTE`를 호출한다. 성공 결과와 함께 writer 권한을 execution orchestrator에 이관한다. execution orchestrator는 `state status`/`state resume`에서 controller phase `EXECUTE`와 실행 action을 확인하고 그대로 표시한다.
3. **매 task stage 변경 시 갱신**: implementing → reviewing 등
4. **학습 이벤트 발생 시**: 워커가 사용자 정정, 검증 실패, 규칙 위반, 접근 변경 근거를 반환하면 오케스트레이터가 컨트롤러를 통해 학습 버퍼와 이벤트를 적용
5. **리밋/에러 시**: 워커는 중단 근거만 반환한다. 오케스트레이터는 근거를 기록하고 `state status`/`state resume`를 호출하며 controller phase나 task stage를 직접 pause 상태로 바꾸지 않는다
6. **재개 시**: 새 오케스트레이터가 controller status/resume 결과, 이 문서의 task stage, learning buffer를 함께 읽는다. controller phase가 `EXECUTE` 또는 `RESULT`이면 handoff된 execution orchestrator가 재개한다.
7. **Phase 4 완료 시**: 모든 task의 `complete` 근거를 검증한 뒤 controller transition `EXECUTE` → `RESULT`를 호출하고 반환된 phase를 표시한다
8. **RESULT 중단 재개 시**: result artifact가 없고 controller가 `RESULT`/`ACTION`을 반환하면 execution orchestrator가 그 live action 전체와 verified evidence(`completion_identity`, `verified: true`, 비어 있지 않은 summary, `{name, status: PASS, evidence}` validation 목록)를 저장소 내부 JSON으로 준비하고, 현재 로드된 skill에서 절대 package-relative 경로로 해석한 `<moondex-runtime> result-action`을 호출한다. callable은 public read-only `status`/`resume` 결과와 supplied action의 완전 일치를 확인하고, 정렬된 UTF-8 canonical JSON의 versioned SHA-256을 result/snapshot/sync report에 함께 기록하며, 모든 출력 대상을 먼저 점검한 뒤 추가 transition/worker dispatch 없이 길이를 자르지 않는 credential-redacted result와 sync snapshot을 하나의 rollback 단위로 기록한다. 응답 유실 뒤 live 결과가 `RESULT/COMPLETE`라면 supplied ACTION digest의 모든 영속 사본, feature, completion identity, config 및 기존 result/sync/snapshot/wiki/index/log가 모두 동일한 경우에만 무쓰기 멱등 복구를 허용한다. 키 순서만 다른 JSON은 같지만 필드나 값의 추가·삭제·변경은 거부한다. 이후 `status`/`resume`이 `COMPLETE`이면 결과를 보고한다.
9. **선택적 knowledge sync**: controller phase `RESULT`에서 별도 evidence와 sync report만 기록한다. destination/index/log/lock/raw·feature·run 디렉터리/snapshot/project result 디렉터리/result/sync report를 완전한 named role set으로 만들고 NFC+casefold 상대 identity를 pairwise 비교한다. Compound lock 안에서는 존재하는 모든 role의 regular-file/directory 타입과 non-symlink 조건을 확인하고 모든 role pair의 device/inode를 비교한다. 따라서 destination뿐 아니라 index↔log, snapshot↔index, result↔report alias도 차단하며 공용 부모를 가진 정상 파일은 허용한다. Compound root의 durable `.moondex-sdd-sync.lock`(mode `0600`)에 bounded `fcntl.flock`을 획득한 뒤 mutable wiki/index/log를 읽고 commit, rollback 또는 recovery 검증이 끝날 때까지 유지한다. lock 파일 자체는 rollback 대상이 아니다. 명시된 compound의 운영 규칙과 index를 읽고, completion identity 기반 run-id의 append-only raw snapshot, configured destination wiki page, wiki index/log, 프로젝트 sync report가 하나의 rollback 단위로 모두 반영된 경우에만 `SYNC_APPLIED`다. lifecycle phase를 추가하지 않는다
