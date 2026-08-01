# Agent 디스패치 가이드

sdd-orchestrator가 Phase 4에서 호스트 중립적인 역할 계약으로 워커를 디스패치할 때 참조한다. `SPEC`, `DESIGN`, `PLAN`의 유일한 transition caller는 SDD coordinator이며 필수 artifact와 현재 turn의 명시적 승인 검증 후에만 전진한다. `PLAN → EXECUTE` 성공 시 writer 권한이 execution orchestrator로 한 번 이관된다. EXECUTE 이후에는 오케스트레이터만 lifecycle 문서와 프로젝트 로컬 컨트롤러 상태를 변경한다. 모든 워커는 `agents/SDD_WORKER_CONTRACT.md`의 공통 envelope(`Status`, 선택적 `Verdict`, 변경 경로, 검증, 근거)를 반환한다. `Status`만 completion 상태이며 stage 판정은 `Verdict`에 둔다.

## 디스패치 계약

### Engineer

```text
role: sdd-flutter-engineer  # task 문서의 구현자에 맞게 선택
execution: parallel-when-independent
prompt: |
  develop 문서: <path>
  task 문서: <path>
  태스크: T-<ID> — <내용>
  소유 파일: <file-list>

  소유 범위 안에서 구현하고 다음을 반환한다.
  Status: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED
  Verdict: <omit>
  changed_paths: <paths>
  validation: <commands and evidence>
  concerns: <optional>
```

### Compliance checker

```text
role: sdd-compliance-checker
execution: sequential-per-task-after-engineer
prompt: |
  태스크 T-<ID> 요구사항 정합성 검증.
  develop/task 문서와 changed_paths를 읽고 누락, 범위 위반, 금지된 host 전제를 확인한다.
  Status: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED
  Verdict: COMPLIANCE_PASS | COMPLIANCE_FAIL
  evidence: <requirement-by-requirement evidence>
```

### Reviewer

```text
role: sdd-reviewer
execution: sequential
prompt: |
  태스크 T-<ID> 리뷰.
  요구사항, 소유 파일, 전체 diff, 정적 분석 결과를 확인한다.
  Status: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED
  Verdict: REVIEW_PASS | REVIEW_FAIL
  evidence: <findings or pass evidence>
```

### Test Automator

```text
role: sdd-test-automator
execution: sequential
prompt: |
  태스크 T-<ID> 검증.
  빌드, 정적 분석, 관련 테스트와 관찰 가능한 acceptance outcome을 검증한다.
  Status: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED
  Verdict: TEST_PASS | TEST_FAIL
  evidence: <commands and outcomes>
```

### Compound Syncer (Phase 5)

Phase 4 result 생성과 승인된 정리 이후 실행한다. 명시적 compound root가 없으면 변경하지 않고 `Status: DONE`, `Verdict: SYNC_SKIPPED`를 반환한다.

```text
role: sdd-compound-syncer
execution: sequential-after-phase-4
prompt: |
  feature: <feature>
  project_root: <project-root>
  compound_root: <explicit root, or omit>
  spec/arch/ux/api/tasks/result: <artifact paths>
  learning_buffer/events: <controller-owned artifact paths>

  compound 운영 규칙을 먼저 읽고 source snapshot을 만든 뒤 wiki를 갱신한다.
  기존 raw 파일은 수정, 삭제, 이동하지 않는다.
  Status: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED
  Verdict: SYNC_APPLIED | SYNC_SKIPPED
  evidence: <changed paths and validation>
```

## 역할 매핑

| 기술 스택 | role |
|----------|------|
| Flutter/Dart | sdd-flutter-engineer |
| React/Next.js | sdd-react-specialist / sdd-nextjs-engineer |
| Vue | sdd-vue-engineer |
| TypeScript | sdd-ts-engineer |
| Python | sdd-python-engineer |
| FastAPI | sdd-fastapi-engineer |
| Rust | sdd-rust-engineer |
| C++ | sdd-cpp-engineer |
| Swift | sdd-swift-engineer |
| SQL | sdd-sql-engineer |
| 범용 | sdd-implementer |
| Phase 5 compound sync | sdd-compound-syncer |

## 동시 실행 제한

- Engineer: 의존성이 없는 Wave 내 태스크 최대 4개
- Compliance checker: 구현이 끝난 태스크별 실행
- Reviewer: 1개씩 순차 실행
- Test Automator: 1개씩 순차 실행
- 소유 파일이 겹치는 태스크는 병렬 실행하지 않는다

## 오케스트레이터 전환 순서

1. controller phase가 `EXECUTE` 또는 `RESULT`이고 SDD coordinator의 권한 이관이 완료됐는지 `state status`/`state resume` 결과로 확인한다. 그 전에는 worker를 디스패치하거나 state를 쓰지 않는다. `RESULT`에서는 task worker를 디스패치하거나 transition을 다시 호출하지 않고, 현재 skill에서 절대 package-relative 경로로 해석한 `<moondex-runtime> result-action`으로 verified result와 redacted sync outcome을 기록한 뒤 보고만 재개한다.
2. 디스패치 전에 오케스트레이터가 현재 단계를 기록한다.
3. 워커는 task-owned 변경과 검증 근거만 반환한다.
4. 오케스트레이터가 결과를 검증하고 다음 단계를 기록한다.
5. durable controller transition이 필요하면 오케스트레이터가 프로젝트 로컬 컨트롤러를 호출한다.

## Envelope 판독 규칙

- Engineer `DONE`/`DONE_WITH_CONCERNS` → 오케스트레이터가 task를 `verifying`으로 기록한 뒤 compliance 디스패치. `NEEDS_CONTEXT`/`BLOCKED` → 구현 단계 유지.
- Compliance `COMPLIANCE_PASS` + passing status → 오케스트레이터가 `reviewing`으로 기록한 뒤 reviewer 디스패치. `COMPLIANCE_FAIL` + `BLOCKED` → 새 구현 iteration.
- Reviewer `REVIEW_PASS` + passing status → 오케스트레이터가 `testing`으로 기록한 뒤 test automator 디스패치. `REVIEW_FAIL` + `BLOCKED` → 새 구현 iteration.
- Test `TEST_PASS` + passing status → 오케스트레이터가 `complete`로 기록. `TEST_FAIL` + `BLOCKED` → 새 구현 iteration.
- Team 준비 보고는 `Status: DONE`, `Verdict: READY`다. `READY`를 lifecycle status로 해석하지 않는다.
- status/verdict 조합이 위 규칙과 충돌하거나 verdict가 빠진 stage 결과는 `NEEDS_CONTEXT`와 동일하게 취급하고 전환하지 않는다.

## 실패와 재시도

- 워커 실행 오류는 같은 입력으로 1회 재시도한다.
- 요구사항/리뷰/테스트 실패는 iteration을 올리고 누적 피드백을 다음 Engineer 입력에 포함한다.
- iteration이 프로젝트의 escalation 한계에 도달하면 추가 변경 없이 사용자 판단을 요청한다.
- rate-limit 오류가 연속 발생하면 새 디스패치를 보류한다. 워커는 중단 근거만 반환한다. 오케스트레이터는 그 evidence를 기록한 뒤 프로젝트 로컬 컨트롤러의 `state status`와 `state resume` 결과를 확인하고 사용자에게 보고한다. 별도 pause phase, 재개 시각, lifecycle 상태를 직접 만들거나 변경하지 않는다.
