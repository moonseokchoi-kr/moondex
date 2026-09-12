# Moondex 위임 실행 개편 설계안 d1

상태: **사용자 검토용 제안, 미승인**. 작성일: 2026-09-06.
기준 checkout: `fbf072e3d341c43f57b26b6c144e2fcb76e2556d` (인수받은 origin/main).
이번 산출물은 조사와 설계다. SDD 시작/전이, worker 실행, 제품 구현을 승인하거나 수행한 기록이 아니다.

## 1. 요구 기준과 현재 작업 범위

승인 요구의 원본 보존은 사용자가 지정한 Compound의
`wiki/moondex-delegated-execution-requirements-r1.md`에 있다. 이하 R1–R11은 그 문서의 번호다.
요구 보존본 SHA-256: `c4db591a4bb82619cfc4ed6802f25bc94dba4581f35b282821c28e3229e543d5`.
이 설계는 요구를 해석한 **제안**이며 승인 요구를 대체하지 않는다. 향후 제품은 해당 개인 경로를 알 필요가 없다.
구현 시에는 사용자 지정 SSOT 원본을 프로젝트의 revision bundle로 고정하고 원본 출처와 digest를 연결한다.
이번에는 bundle 승인 또는 실행 승인 레코드를 만들지 않는다.

허용 범위는 요구 보존, 현재 main의 읽기 중심 조사, 격리된 로컬 재현, 설계·수용 테스트 제안이다.
원래 `orca-native-phase4` worktree와 미추적 `harness_core/execution/`, `tests/execution/`는 조사·복사·수정하지 않았다.

## 2. 관찰 가능한 결과에서 출발

| 의도한 사용자 결과 | main에서 확인한 동작 | 차이와 제안 | 향후 수용 증거 |
|---|---|---|---|
| 준비 형식에 관계없이 합의 후 위임 | Phase enum과 preflight가 Spec/Design/Plan 파일과 순서를 요구 | 준비 문서 선택 자유, 실행 가능성은 실행 계약으로 검사 | A01 |
| 승인한 기준이 구현 중 유지 | approval은 spec/design/plan boolean, 문서 내용 digest 미결합 | 기준 snapshot과 승인 대상 digest 고정 | A02–A03 |
| AI를 계속 호출하지 않아도 확정 DAG가 진행 | Python은 phase 전이, 작업 wave loop는 skill 지침 | 단일 script executor가 dispatch·수신·검증·재개 소유 | A04–A07 |
| 실제 기능과 필수 검증이 끝나야 완료 | RESULT preflight는 complete 행과 비어 있지 않은 notes 확인 | 실행된 검증 receipt + 의도 적합성 + 통합 snapshot으로 완료 | A08–A10 |
| 긴 테스트는 기다리고 실패만 복구 | 고정 MAX_RETRIES=3; 실행 프로세스 수명주기와 묶이지 않음 | attempt·process 상태·한도 분리 | A11–A13 |
| 필요한 부분만 피드백 반영 | forward phase controller에 revision/영향 무효화 모델 없음 | 기준 revision, 계획 revision, attempt를 구분 | A14–A16 |
| 과거 기준과 사후 결과를 각각 보존 | result-action은 외부 verified/PASS 입력을 materialize; configured sync는 raw snapshot 생성 | 실행 증거를 소비하는 보고기와 rules-aware Compound 연결 | A17–A19 |

### 확인 방법과 한계

- 실제 재현: `.harness/audit/delegated-execution-redesign/probe.py`와 `probe-output.json`.
  임시 디렉터리의 synthetic fixture에만 승인 boolean을 설정했다. 사용자 승인이나 실제 feature state가 아니다.
- 테스트를 실행하지 않은 fixture의 complete 행+메모로 RESULT preflight가 통과했다.
  spec 내용을 바꿔도 통과했고, nonexecuted command 문자열로 policy 검사가 통과했다.
  RESULT 상태에 결과 Markdown이 존재하면 status가 COMPLETE였다.
- 따라서 **컨트롤러의 독립적인 실행 증거 강제는 확인되지 않으며 위 경로에서는 부족하다**.
  올바른 에이전트가 실제 테스트를 수행할 수 없다는 뜻은 아니다.
- `tests/e2e/test_codex_harness_acceptance.py:121`의 `_SoleWriterSimulation`은 명시적으로 test-owned다.
  브라우저 행동을 실행하는 consumer test도 있지만, 이 simulation 통과는 production scheduler의 존재를 증명하지 않는다.
- 현재 checkout에서 status/resume을 각각 실행했고 둘 다 `BLOCKED_ARTIFACT: no project-local state exists`였다.
  새 요구를 기존 phase에 넣기 위해 start/transition하지 않았다.
- 전체 기존 테스트 suite는 이 조사에서 실행하지 않았다. 테스트 존재·기존 결과 문서를 새 제품 지원의 증거로 쓰지 않는다.

## 3. 용어와 책임

**실행 명세**: 사용자가 합의한 목표·요구·설계 결정·통과 조건과, 이를 실행할 DAG·검증·권한·복구 한도를 고정한 입력.
문서 세 개를 순서대로 작성한다는 뜻이 아니다. 한 페이지·대화 합의·외부 문서 조합도 가능하다.

**DAG**: 실행 가능한 작업과 실제 입력 의존성. 노드 하나도 유효하다. 역할 이름이나 에이전트 수와 같지 않다.
**dispatch**: script가 승인 노드/attempt를 Orca task/dispatch와 연결하고 receipt를 저장한 실행 요청.
**자동 실행**: AI에게 다음 ready 작업 선택을 다시 묻지 않고 script가 계속 실행·검증한다. daemon 생존이 검증되기 전에는 세션 밖 무중단 실행을 약속하지 않는다.
**완료**: 현 revision의 필수 노드, 통합 snapshot의 필수 gate, 의도 적합성 검토가 유효하고 blocker가 없으며 최종 보고가 보존된 상태.
**통합**: 승인된 결과 worktree에 산출물을 결합하고 그 정확한 tree를 검증한 상태. main merge/push/deploy는 별도 승인 범위다.

| 구성 요소 | 소유 책임 | 소유하지 않는 책임 |
|---|---|---|
| 사용자 | 기준 승인·변경, 예외 결정, 실행 권한·한도 | 정상 task마다 재승인 |
| 준비/분석 AI | 요구 구체화, 분할 제안, 원인 분류, 구현, 검토 | scheduler 상태 직접 편집, 승인 추정 |
| Script executor | DAG validation, ready 선택, 한도/동시성, outbox/inbox, 검증 실행, evidence 검사, 상태/재개 | 모호한 제품 의도 결정, 기준 완화 |
| Orca adapter | Run/Task/Dispatch·질문·완료 수신·worker 수명주기 | Moondex 완료 판정, 자체 scheduling 가정 |
| Verification runner | 승인 gate 실행, 프로세스 추적, exit/assertion/log receipt | 테스트 커버리지만으로 의미적 적합성 추정 |
| Compound adapter | 규칙/양식 확인, 기준과 결과의 별도 기록, idempotent sync | raw 쓰기, 기준 자동 변경, 목적지 추정 |
| self-improve skill | 별도 명시 호출에서 수집 증거 검토 | 본체 실행 중/완료 후 자동 정책 변경 |

## 4. 실행 명세 계약 제안

최종 schema는 아래 계약과 수용 테스트를 승인한 뒤 작성한다. 필드명이 기존 CLI에 구현되어 있다는 뜻은 아니다.

### Revision bundle

- `schema_version`, `project_id`, `feature_id`, `baseline_revision`, `parent_revision`, `content_digest`.
- `source_refs`: 문서/대화 원본 위치, 수집 시점, 원본 digest. 출처가 없는 과거 메시지 ID는 발명하지 않는다.
- `intent`: 사용자 문제, 관찰 가능한 before/after, 제외 범위, 요구 ID.
- `design_decisions`: 합의된 동작·인터페이스·제약만; 미결정 사항은 별도 `open_decisions`.
- `criteria`: criterion ID, 적용 요구, fixture/input, 행동, 기대 관측 결과, 실패 예, gate ID.
- `dag_revision`, `dag_digest`, `nodes`, `integration_contract`, `verification_plan`.
- `execution_policy`: concurrency, 작업 범위/작업공간, retry/비용/시간 한도, 환경/권한, 외부 변경 권한.
- `approval_ref`: actor=user, 결정 원문/출처, 승인 시각을 알 때만 시각, 정확한 bundle digest, 허용 행동.
- `readiness`: 모든 필수 정보와 gate runner가 해석 가능해야 READY. 미결정 한도·권한은 값을 추정해 채우지 않는다.

### Node 계약

각 노드에 다음이 모두 있어야 한다.

| 필드 | 의미 |
|---|---|
| `node_id`, `goal`, `criteria_refs` | 무엇을 관찰하면 이 작업의 목표를 달성했는가 |
| `inputs` | artifact/revision/digest, 환경·의존 인터페이스 |
| `depends_on` | 선행 노드와 필요한 산출물; 존재·비순환 검사 |
| `write_scope`, `read_scope`, `workspace_ref` | 수정 허용 경로, protected baseline 제외, 공유 자원 |
| `output_contract` | 기대 artifact 유형·위치, 구현 tree/patch identity |
| `required_gates`, `required_evidence` | 필수 검증 목록, 의도 연결, 완료에 필요한 receipt |
| `executor_kind` | agent 판단/구현 또는 script command; 역할별 worker를 무조건 만들지 않음 |
| `resource_locks` | 공유 checkout, 포트, 테스트 DB, lockfile 등 충돌 자원 |
| `attempt_policy_ref`, `failure_route` | 복구 한도와 구현/검증/기준 변경 라우팅 |
| `split_rationale` | 단일 유지 또는 분할 이유, 예상 시간 이익·context/통합 비용 |

### 일관된 분할 규칙

1. 먼저 하나의 agent 노드와 필수 verification/integration gate로 표현한다. 검증은 별도 AI 세션 수와 무관하다.
2. 산출물·입력·수정 범위가 독립적이고, 공유 자원 충돌이 없고, 순차 대비 시간 이익이 context·dispatch·통합 비용보다 클 때만 분할한다.
3. 판단 근거와 예상치를 남긴다. token 예측 정밀도를 가장하지 않는다. 불확실하면 단일로 둔다.
4. 같은 파일/계약을 동시 수정해야 하면 dependency 또는 lock을 추가한다. 서로 파일이 다르다는 사실만으로 의미적 독립성을 인정하지 않는다.
5. 확정 후 script는 ready+resource-available 노드만 안정된 node ID 순서로 실행한다. ready 계산은 모든 의존 증거의 유효성을 검사한다.
6. 전체 wave barrier는 필수로 두지 않는다. 자기 선행 작업이 끝난 노드는 다른 무관한 노드를 기다리지 않는다. 동시성 상한은 승인 policy를 따른다.
7. 반복은 cycle을 추가하지 않고 attempt 또는 새 DAG revision으로 처리한다.

### 단일 세션과 실행 주체의 미해결 경계

기본 제안은 실행 AI 세션 하나를 순차 노드에 재사용하고, 준비를 맡은 AI는 계속 scheduling하지 않는 방식이다.
즉시 후속 노드가 있으면 같은 Orca terminal에 새 dispatch를 연결하고, 없으면 release한다.
각 노드마다 implementer/compliance/reviewer/tester 세션 네 개를 만드는 방식은 기본값이 아니다.
다만 사용자의 “단일 세션”이 **처음 대화한 바로 그 세션 하나만**을 뜻한다면,
현재 agent 호출 중 script가 그 agent에게 후속 작업을 전달하고 재개하는 인터페이스를 추가로 검증해야 한다.
새 구현 worker 하나를 쓰는 것과 동일 세션 유지가 같다고 설명하지 않는다. D7에서 의미를 확정한다.

## 5. SSOT와 승인

제안 저장 경계:

```text
<project>/docs/execution/<feature>/
  revisions/r0001/      # 기준 + 명세 + 출처 고정본 (작성 완료 후 immutable)
  approvals/           # 대상 digest, 사용자 결정 원문/출처, 권한
  changes/             # r1 -> r2 이유/차이/영향/승인
  results/<run-id>/     # 사실 보고, evidence manifest, sync 상태
<project>/.harness/state/execution/<run-id>/
  run.sqlite           # 단일 script writer; events/inbox/outbox/projections
<project>/.harness/audit/execution/<run-id>/
  ...                  # raw commands/logs/reproductions
<project>/.harness/reports/execution/<run-id>/
  ...                  # redacted 사용자 표시
```

`docs/execution/`와 SQLite는 선택 D1/D3이며 아직 저장소 규칙을 바꾸지 않는다.
이번 설계 문서는 현재 durable 위치인 `docs/sdd/design/arch/`에 둔다.

- 기존 `approval=true`를 새 bundle 승인으로 이관하지 않는다. 승인에는 실제 사용자 근거와 대상 digest가 함께 있어야 한다.
- bundle은 고정된 UTF-8 canonical JSON과 참조 문서 byte digest를 사용한다. 참조 파일을 mutable path만으로 읽지 않는다.
- AI는 승인 요청을 준비할 수 있지만 user 결정을 만들어낼 수 없다. 자연어 승인 해석이 모호하거나 대상 revision이 달라졌으면 확인한다.
- 같은 OS 사용자에게 파일 쓰기 권한이 있으므로 이것은 악의적 worker에 대한 보안 경계가 아니다. script 경로 보호와 실행 전/수신 전 digest 검사는 우발적 기준 변조를 탐지하는 장치다.
- 실행 권한은 승인된 계약의 정상 구현·수정·검증을 포괄한다. 새 node 실행마다 재승인하지 않는다.
- 요구/설계/통과 기준·권한·예산 변경은 새 bundle+사용자 합의가 필요하다.
- 동일 기준의 구현 결함 복구는 새 attempt로 처리한다. 동일 의도의 검증 도구 보강은 verification revision에 이전/이후 커버리지와 이유를 남긴다. 기준 삭제/완화/N/A 전환은 기준 변경이다.
- 동일 기준 아래 영향 DAG 재계획은 새 plan revision으로 보존한다. 권한/수정 범위/한도 안에서의 재계획 자동 허용 여부는 D5에서 결정한다.

## 6. 상태와 전이

준비 방식은 자유다. `DRAFT`는 Spec→Design→Plan 하위 단계를 강제하지 않는다.

| Run 상태 | 진입 조건 | 다음 동작/전이 |
|---|---|---|
| DRAFT | 입력 정리/설계 중 | 계약 검사 후 READY; 불충분하면 DRAFT 유지 |
| READY | 정확한 bundle 승인과 실행 권한, 환경·한도 해석 완료 | script 시작 시 RUNNING |
| RUNNING | lease 보유, 승인 digest 일치 | ready 실행·수신·검증; 필수 노드 유효 시 VERIFYING |
| VERIFYING | 통합 snapshot 봉인 | 통합 gate와 의도 검토 통과 시 REPORTING; 결함이면 RUNNING의 새 attempt |
| WAITING_USER | 요구 충돌/모호함/권한·정보 부족/한도 소진/복구 결정 | 질문 ID+대상 revision에 답이 연결된 후 저장된 resume 지점으로 복귀 |
| RECOVERING | 프로세스/remote 결과가 불명확하거나 executor 재시작 | 기존 attempt를 reconcile; 생존 확인은 대기, 종료 확인은 복구 정책 적용, 불명확하면 개입 |
| REPORTING | 모든 필수 증거 유효 | 결과 저장과 필수 기록 조건 충족 시 COMPLETED |
| COMPLETED | 봉인된 결과 존재 | read-only 재보고; 새 피드백은 연결된 revision/run 생성 |
| CANCELLED | 사용자 취소 및 잔존 자원 상태 기록 | 자동 재시작 금지; 계속하려면 명시적 새 실행 결정 |

Node 흐름: `PENDING → READY → DISPATCHING → RUNNING → SUBMITTED → VERIFYING → SUCCEEDED`.
`SUBMITTED`는 Orca 성공 보고도 포함하는 후보 상태이며 완료가 아니다.
실패 attempt는 `FAILED`; 다음 attempt는 별도 ID로 생성한다. 한도 소진은 `WAITING_USER`.
결과 불명확은 `OUTCOME_UNKNOWN`, 기준 변경 영향은 `INVALIDATED`로 보존한다.
의존 노드는 upstream이 SUCCEEDED여도 그 evidence가 INVALIDATED이면 ready가 아니다.

Test process 흐름: `QUEUED → STARTING → RUNNING → PASS | FAIL | CANCELLED | LOST`.
RUNNING의 출력 부재·poll timeout을 FAIL로 만들지 않는다. LOST는 프로세스 identity 재확인 후에만 판정한다.
`PASS`는 종료 성공과 승인된 assertion/report 충족이 함께 있어야 한다. exit 0만으로 기능 적합성을 보장하지 않는다.

### Script 조정 루프와 장애 경계

1. project/run lease와 fencing generation 획득. 오래된 writer의 event/receipt 반영을 거부한다.
2. resume은 저장된 approved digest, policy, inputs를 검증하고 상태를 재구성한다. status 조회 자체는 실행하지 않는다.
3. DB transaction으로 intent/outbox를 먼저 저장한다. 외부 side effect는 transaction 밖에서 실행하고 receipt를 다음 transaction에 연결한다.
4. Orca task/dispatch 매핑에는 `(run_id, baseline_revision, plan_revision, node_id, attempt_id)`를 둔다.
5. Delivery 전체를 로컬 inbox에 durable 저장하고 message ID로 중복 제거한 다음 반영한다. release 또는 즉시 재사용 결정을 저장한 뒤 ack한다.
6. ready 선택, 동시성 제한, 검증 예약은 script가 결정한다. 판단이 필요한 failure만 bounded analysis task로 전달한다.
7. process/worker 생존을 확인할 때까지 slot과 write lock을 반환하지 않는다. settle된 dispatch라도 살아 있는 writer 여부가 중요하다.
8. crash 직후 미확정 outbox는 task/dispatch receipt와 대조한다. "명령 실패"만으로 재dispatch하지 않는다.
9. 두 번째 writer는 lease 실패를 보고 종료한다. 원격 부작용의 exactly-once를 약속하지 않는다. Orca retry identity 보장이 불명확하면 OUTCOME_UNKNOWN으로 보존한다.
10. bounded wait마다 짧은 상태 알림을 낸다. AI가 한 메시지씩 scheduling 결정을 내려야 하는 루프로 되돌리지 않는다.

SQLite는 events, materialized 상태, inbox dedup, outbox intent를 한 transaction으로 묶기 위한 추천이다.
기존 atomic JSON+flock는 단일 상태 파일에는 유용하지만 여러 파일+외부 receipt commit을 그대로 해결하지 않는다.
선택 시 SQLite recovery, filesystem 지원, 잠금/내구성 시험이 필요하다. 기존 state를 삭제하거나 덮어쓰지 않는다.

## 7. 검증·증거 계약

Gate는 build/unit/integration/E2E 각각의 적용 여부와 이유를 준비 단계에 명시한다.
필수로 확정된 gate는 느리거나 환경이 없다는 이유로 skip/N/A로 바꾸지 않는다. 환경 부족은 blocker다.
문서 전용 작업처럼 범주가 적용되지 않으면 최초 계약에서 N/A와 근거를 합의한다.

필수 receipt 필드:

- `evidence_id`, `run/node/attempt`, baseline/plan/verification revision과 digest.
- `criterion_ids`, gate ID/kind, input/artifact digest, 테스트 정의 digest.
- 검사한 commit/tree+uncommitted diff/untracked manifest digest, 환경/toolchain/fixture identity.
- 실제 `argv`, `cwd`, 시작/종료 시점, runner/process identity, exit code/signal, 상태.
- raw log URI+digest, redacted summary, structured assertion result, 테스트 개수/수집 결과.
- 수집 주체와 provenance: runner-observed / agent-reported / human-reviewed를 구분한다.
- 무효화 사유/상위 evidence, 재사용 시 동일 입력이라는 근거.

명령은 shell 문자열을 임의 실행하지 않고 승인 argv 계약을 사용한다. credential 값은 공개 manifest에 넣지 않는다.
구조·digest·exit code가 통과해도 검증 내용이 의도에 맞는지 별도로 검토해야 한다.
각 criterion에 대해 **실패해야 하는 결함 fixture**를 실행하여 oracle이 그 결함을 잡는지 확인한다.
불완전한 oracle이 발견되면 검증 결함 경로로 수정하며 expected result를 구현에 맞춰 바꾸지 않는다.
UI라면 DOM 문자열 검사가 아니라 사용자 행동과 화면 결과, 필요한 viewport/browser를 검증한다.
사람 판단이 필요한 기준은 최초 계약에 human review를 포함한다. 새로 필요해지면 구체 질문과 영향을 기록한다.

Node 완료 = required artifact·scope 준수 + 필수 gate PASS + 기준 적합성 검토 + blocker 없음.
Run 완료 = 모든 필수 node 증거 유효 + 통합 snapshot의 필수 gate PASS + 최종 의도 적합성 + 결과 보존 + 필수 sync 조건.
worker_done, 테스트 파일 존재, Markdown notes, `verified:true`, 과거 PASS는 대체 증거가 아니다.

### 통합 및 증거 재사용

같은 checkout의 병렬 writer와 전체 검증은 겹치지 않게 자원 lock을 잡는다.
노드별 국소 검증도 읽는 자원이 다른 writer와 겹치면 serialize하거나 승인된 별도 snapshot에서 실행한다.
작업별 별도 checkout은 실제 수정 충돌·검증 격리 필요 또는 명시 승인이 있을 때만 Orca로 만든다.
충돌 없는 단일 작업은 현재 지정 worktree를 쓴다. 모든 role에 새 worktree를 만드는 정책은 아니다.

통합 전에 입력/출력 identity와 수정 범위를 검사한다. script가 명확하게 적용 가능한 patch만 결합하며
merge conflict는 AI 분석/수정 작업으로 보내고 기준·범위 변경이면 사용자에게 묻는다.
최종 gate 동안 tree를 봉인한다. 이후 코드 변경이 있으면 영향 gate를 무효화한다.
무관 노드의 증거는 입력/criteria/검증 정의/environment dependency fingerprint가 동일할 때 재사용한다.
run-level 통합 gate가 전체 tree를 입력으로 선언했다면 tree 변경으로 영향받은 gate이므로 다시 실행한다.

## 8. 피드백·예외·한도

| 분류 | 비교 기준 | 처리 |
|---|---|---|
| 요구/설계 변경 | 사용자 기대가 승인 baseline과 달라짐 | 변경안·이유·영향 제시 → 사용자 합의 → 새 baseline → 영향 DAG revision → 구현/검증 |
| 구현 결함 | baseline은 옳고 구현이 위반 | 재현/회귀 oracle → 새 구현 attempt → 영향 gate 실행 |
| 검증 결함 | baseline을 테스트가 검증하지 않거나 잘못 판정 | verification revision·적합성 검토 → gate 실행; assertion 완화는 기준 변경으로 분류 |
| 모호함/정보 부족 | 여러 해석 또는 근거 부족 | 질문과 시도·영향·선택지를 저장 → 사용자 결정 후 재개 |

무효화 집합은 변경 criteria/gate/artifact를 직접 참조하는 node와 그 출력에 의존하는 전이적 후속 node다.
의존성을 선언하지 않은 공유 영향이 발견되면 계획 결함으로 기록하고 보수적으로 해당 영향 범위를 넓힌다.
전체 무관 작업을 자동 재실행하지 않는다. 영향 계산·재사용 근거를 결과에서 확인할 수 있어야 한다.
기준 변경 대기 중인 영향 worker의 산출물은 이전 revision에만 귀속하며 새 revision의 완료에 쓰지 않는다.
다른 자원을 쓰는 무관한 승인 작업의 계속 진행 여부는 D5의 pause 범위 정책으로 정한다.

개입 기록: question ID, 종류, 관련 baseline/node/attempt, 마지막 안전 상태, 재현·시도 목록,
실패/살아 있는 프로세스 구분, 증거, 영향 노드/비용, 선택지, 추천, 답변 원문·출처, 적용 revision.
중복 답변은 한 번만 반영한다. stale revision의 답을 다른 실행에 적용하지 않는다.

한도는 아직 미합의다. 다음 값들은 설계 선택 D4이며 실행 기본값이 아니다:

- 구현/검증 실패 복구: **최초 실행 이후 자동 복구 2회** 후보. transport retry와 분리한다.
- transport: 안정된 request identity로 재시도 가능하다고 검증된 요청만 **2회** 후보.
  unknown side effect는 횟수를 소진하며 다시 생성하지 않고 reconcile/개입한다.
- 동시성: 기본 **1**, 유익한 분할 승인 시 명세에 상한 명시. 현재 skill의 4를 자동 승계하지 않는다.
- token/비용/run 시간: 프로젝트별 합의가 필요하다. provider usage가 없으면 정밀 비용 상한 강제를 주장하지 않는다.
  관측 가능한 한도(호출 수/실행 시간 등) 대체안 또는 사용량 제공 adapter를 합의해야 READY다.
- 긴 테스트: progress 관측 주기는 종료 deadline과 다르다. gate별 deadline은 알려진 소요시간과 사용자 정책으로 정한다.
  deadline 경과 시 timeout 사유와 살아 있는 process를 보존하고, 승인된 취소 권한이 있을 때만 중지한다.
- 예산 소진 시 새 dispatch를 막고 저장한다. 실행 중 작업의 대기/정지는 미리 합의된 policy를 따른다.

## 9. Orca 연결: 확인된 표면과 검증할 가정

조사 시 Orca `1.4.193`, runtime `ready`를 직접 확인했다.
가이드는 `orca skills get orchestration`, `orca skills get orca-cli`, 개별 `--help`에서 읽었다.
아래는 설치 버전의 문서상 계약이다. mutation 동작은 이번에 실행하지 않았다.

- Run은 namespace/inbox, Task는 작업, Dispatch는 attempt 배정이다. retired scheduler 명령은 쓰지 않는다.
- `worker-start`는 실행/준비/dispatch를 결합하고 ready/failed/outcome_unknown과 effects/residualResources를 반환한다.
- `check`는 FIFO Delivery를 ack 전까지 재전달한다. timeout은 worker 실패가 아니다.
- `worker_done`은 Orca Task/Dispatch를 completed 처리한다. Moondex는 이를 SUBMITTED로만 수용한다.
- settle 후 `worker-release` 또는 즉시 재사용 선택이 필요하다. unknown release를 terminal close로 대체하지 않는다.
- Run binding/권한은 invoking terminal/principal과 관련 있다. `--from`, terminal handle, inherited history를 권한으로 발명하지 않는다.
- 기본 nested depth와 dispatch circuit breaker(가이드상 연속 실패 3회)는 외부 제약이다.
  Moondex 한도와 별도로 capability/policy에 기록하고, 새 Run을 만들어 외부 한도를 우회하지 않는다.

미확인: script child process의 인증, agent가 idle/종료한 뒤 권한 유지, 다른 terminal에서 재개할 수 있는 조건,
mutation response loss의 idempotency, usage 측정, 중단/cleanup의 정확한 lifecycle.
read-only help/status만으로 지원 가능하다고 확정하지 않는다.

### 승인 요청 대상인 작은 실험 E1

**목적**: AI scheduler 없이 script가 Orca 한 작업을 실행·수신·복구할 수 있는지 확인.
**산출물**: 실행 환경별 capability matrix, 요청/receipt·중복 메시지 trace, 잔존 자원 기록, 지원/불가 판정.

1. 사용자가 승인한 disposable fixture 위치와 launch model/비용·시간 상한을 정한다.
2. 작은 script가 자기 정당한 실행 context에서 Run+Task+단일 worker를 만든다.
   worker는 fixture 파일 하나만 만들고 제공된 자기 dispatch preamble로 종료 보고한다.
3. script가 결과를 durable inbox에 저장하고 fixture 검증 명령을 직접 실행한다. worker_done만으로 완료되지 않는지 확인한다.
4. 수신 후 ack 전 script를 중단·재시작해 같은 Delivery가 중복 적용되지 않는지 본다.
5. agent idle, script 재시작, 가능한 별도 context 재개를 각각 시험한다. 불가하면 오류를 증거로 보존한다.
   principal 위장·비공개 token 추출·기존 세션 takeover는 하지 않는다.
6. response loss 주입은 request identity의 문서상 보장을 확인한 항목에 한정한다. unknown이면 자동 재시작하지 않는다.
7. 생성한 worker만 정상 release하고 fixture/작업공간은 결과 확인까지 보존한다. 다른 세션/작업을 건드리지 않는다.

통과: 한 task/attempt만 유효, script가 gate를 실행, 재전달 중복 효과 없음, 정상 cleanup receipt,
지원되는 재개 context를 명확히 구분. 실패: 필요한 principal 지속성 부재 또는 중복 dispatch를 배제할 수 없음.
실패하면 deterministic scheduling 요구를 AI loop로 조용히 대체하지 않는다.
지원 가능한 terminal-bound script 방식 또는 별도 Orca capability 필요성을 사용자에게 제시한다.
E1은 아직 실행하지 않았으며 실제 agent launch·비용이 있으므로 별도 승인이 필요하다.

## 10. Compound 및 자가개선

이번 사용자의 명시적 목적지에는 요구 r1, 설계 검토 상태, 조사 사실·증거 위치를 기록한다.
합의 계획/승인 변경/최종 구현 결과는 아직 없으므로 "미승인/미실행"으로 기록한다.

제품 adapter는 `enabled`, destination root, page mapping, rules/template refs, retention, 필수 여부를
프로젝트 설정으로 받는다. 설정이 없으면 SKIPPED이며 개인 경로를 기본값으로 넣지 않는다.
매 write 직전에 규칙과 index를 읽고 충돌을 확인한다. 현재 사용자의 raw 읽기 전용 규칙에 따라
**기존 result-action의 raw/projects snapshot 경로는 재사용하지 않는다**.

기준 page에는 요구/이유/승인 revision만, 사실 page에는 합의된 계획 ref/실행 시도/승인 변경 ref/최종 결과/증거 위치만 기록한다.
wiki frontmatter/필수 섹션은 해당 template을 따른다. index·hub·log를 일관되게 갱신한다.
쓰기 identity는 `(project, feature, revision, record_kind, completion_id)`로 고정하고 재시도 중복을 방지한다.
동시 편집은 사전 read hash/lock과 변경 충돌 검사를 사용하고, 사용자가 고친 문서를 rollback으로 덮어쓰지 않는다.
raw를 agent-write 대상으로 간주하는 설정은 실제 목적지 규칙과 충돌하면 거부한다.

sync 실패 시 구현 검증 결과는 보존한다. `implementation=VERIFIED`, `recording=PENDING`을 구분한다.
이번 요구처럼 기록이 필수인 run은 전체 완료를 선언하지 않고 기록 문제를 해결/개입한다.
원래 opt-in이 아닌 제품 사용자에게 sync 실패나 개인 DB 설정을 강요하지 않는다.

본체는 실패/재시도/개입/검증 사건을 수집할 뿐 lesson 승격·policy 변경·자동 self-improve 호출을 하지 않는다.
별도 self-improve는 이 증거를 입력으로 받을 수 있지만 실행 baseline을 소급 변경할 수 없다.

## 11. 전환 범위와 구현 순서 제안

| 현재 표면 | 제안 처리 | 이유 |
|---|---|---|
| `harness_core/state/pipeline.py` | legacy 보존, 새 execution core 분리 | phase boolean을 immutable approval로 억지 확장하지 않음 |
| `harness_core/state/storage.py` | atomic/lock 기법 참고, 새 transaction 설계 검증 | 다중 record+remote side effect는 추가 계약 필요 |
| `skills/sdd`, `skills/sdd-orchestrator` | 새 진입점/호환 정책 결정 후 전환 안내 | 새 실행을 과거 phase 승인으로 시작하지 않음 |
| `skills/sdd-orchestrator/scripts/result-action.py` | 결과 rendering/redaction 참고; evidence 입력과 sync rewrite | verified boolean 신뢰와 raw 쓰기 경로 제거 |
| `harness_core/validation`, `enforcement`, `pr` | scope/redaction/local gate 기법 재사용 검토 | policy preflight와 실제 gate 실행을 구분 |
| `agents/` | 역할 데이터로 유지, 필요한 노드에서만 주입 | role 존재가 worker 실행 권한이 아님 |
| `skills/self-improve`, learning core | 별도 명시 호출 유지 | 자동 학습 분리 요구 |
| manifest/README/AGENTS/runtime inventory | 새 경로가 실제 수용 시험 통과한 뒤 함께 갱신 | skills-only·package-relative 실행 보존 |
| 기존 E2E simulation | legacy 범위 유지, production executor E2E 추가 | test-only loop를 제품 증거로 간주하지 않음 |

후속 구현 DAG 후보(미승인):
`E1 capability 실험 → 계약/승인 확정 → {core+durability, evidence runner} → adapter 통합 → 실제 단일 run E2E → 선택 병렬/복구 E2E → 호환/패키징 전환`.
중괄호 구간도 인터페이스가 확정되고 시간 이익이 증명될 때만 병렬로 나눈다.
각 단계의 구현 작업 명세는 승인 후 node 계약으로 채운다. 이 순서는 새 제품 사용자에게 요구하는 문서 순서가 아니다.

기존 pipeline은 새 기능으로 자동 migration하지 않는다. 기존 진행은 기존 package/runtime 경로로 보존한다.
사용자가 전환을 요청하면 artifact/사실 기록을 import하되 새 기준과 실행 권한을 확정한다.
기존 complete 행·approval flag는 자동으로 새 승인/증거가 되지 않는다.
main 병합, plugin reinstall/publish, 과거 작업 정리·삭제는 이 설계 작성 범위에 포함하지 않는다.

## 12. 수용 테스트 제안 — 아직 승인·실행되지 않음

테스트는 아래 사용자 관찰 결과를 검증해야 한다. 기대 결과를 구현에 맞춰 낮추지 않는다.
각 테스트 실행에는 승인 baseline/검사 tree/gate receipt와 재현 입력이 필요하다.

| ID / 요구 | 시나리오 | 통과 관측 |
|---|---|---|
| A01 R1,R2 | 단일 페이지와 한 node 계약 승인 후 실행 | spec/design/plan phase 승인 없이 실제 구현·gate·결과 완료 |
| A02 R3 | 승인 후 spec/assertion 기대값을 몰래 수정 | dispatch/result 반영 차단, 원본 보존, 기준 변경 질문 |
| A03 R3 | r1 승인으로 r2 실행 시도, 다른 feature 승인 재사용 | 대상 digest 불일치 거부, user 근거 없으면 READY 불가 |
| A04 R4,R5 | 독립 A/B와 A에 의존하는 C, 상한 설정 | 승인 상한 준수, C는 A의 유효 증거 후만 시작; 단일 node도 같은 코드 경로 |
| A05 R4 | write scope 겹침/공유 DB/의미적 계약 의존 | 계획 검사 또는 lock으로 충돌 실행 방지; 잘못된 DAG/cycle 거부 |
| A06 R5 | 실제 script가 AI의 다음-task 선택 없이 Orca worker 실행 | task/dispatch trace와 script event로 end-to-end 증명; test simulation만으로 PASS 불가 |
| A07 R5 | dispatch 응답 손실, Delivery duplicate, ack 전 crash, 이중 executor | 중복 유효 attempt/완료 없음, 재시작이 기존 작업 연결, 옛 writer 거부 |
| A08 R6 | worker_done 성공, 테스트 미실행/FAIL/receipt 위조·stale | SUBMITTED에 머물거나 실패, 전체 완료 불가 |
| A09 R6 | unit 통과하지만 사용자 행동 fixture 실패; 테스트 0개 수집 | E2E 또는 oracle 적합성 검사로 완료 차단 |
| A10 R6 | 노드별 PASS 후 통합 결함 또는 검증 중 tree 변경 | 통합 gate FAIL/증거 무효화, main merge 없이 수정·재검증 |
| A11 R7 | 정상 장기 테스트가 wait window를 넘김 | RUNNING 유지, 중복 실행/강제종료/재시도 카운트 증가 없음 |
| A12 R7 | 명백한 실패가 승인 retry 한도 초과, 비용 telemetry 없음 | 저장·구체 질문, 무한 재시도/거짓 예산 보장 없음 |
| A13 R7,R8 | 권한/정보 부족 후 답변, 답변 duplicate/stale | 올바른 지점만 재개, 이미 끝난 무관 작업 보존 |
| A14 R9 | 기준 변경으로 일부 node+downstream만 영향 | 새 승인 revision, 영향 증거만 invalidated, 무관 증거 재사용 근거 보존 |
| A15 R9 | 구현 결함/검증 결함 각각 주입 | 올바른 경로로 복구; 사용자 기준 원문·digest 유지 |
| A16 R9 | feedback가 모호하거나 scope/한도 확대 | 변경 합의 전 종속 작업 시작 금지, 이미 승인된 무관 작업 정책 준수 |
| A17 R10 | Compound 미설정/설정/규칙 충돌/중간 실패/사용자 동시 편집 | 기본 SKIPPED, 설정 시 template+index+hub+log 일관, raw byte 변화 0, 사용자 변경 보존 |
| A18 R10 | 승인 기준 기록 후 실패/완료 결과 기록과 sync replay | 기준 불변, 사실 별도 보존, duplicate 페이지/로그 없음, 필수 sync 미완료면 전체 완료 아님 |
| A19 R11 | 실패 반복 및 정상 완료 | 증거만 추가, self-improve 호출/정책 변경 없음 |
| A20 R8 | 정상 여러 task와 자동 복구 1회 | 불필요한 단계 승인 없이 전체 결과 보고, 진행 알림은 유지 |
| A21 전환 | legacy 진행 state 옆 새 run, opaque installed path | legacy 바이트 불변, 새 package-relative 실행, inventory 검증 통과 |

Validation 층: core unit(전이/승인/무효화), process integration(실제 command/실패/복구),
Orca 실제 E2E(인증/dispatch/재개), 사용자 행동 E2E(승인 oracle), 설치 package 테스트.
필수 빌드·유닛·통합·E2E는 계약에 확정한 뒤 전부 실행한다.
외부 환경이 막히면 관련 필수 수용 조건은 미통과로 보고하며 테스트를 simulation으로 대체 통과시키지 않는다.

## 13. 사용자 결정 목록

| 선택 | 추천 제안 | 대안/영향 | 승인 범위 |
|---|---|---|---|
| D1 진입점/이행 | 새 `$moondex:execute`(가칭) + 기존 SDD legacy 유지, 새 artifacts는 docs/execution | sdd를 직접 교체하면 기존 호출/진행 migration 필요 | 명칭·호환 기간·문서 경계 |
| D2 Orca 제약 | E1을 먼저 승인하고 확인된 실행 context로 좁힘 | detached 지속 실행을 필수로 먼저 정하면 Orca 기능 확장이 필요할 수 있음 | E1만 별도; 제품 구현 승인 아님 |
| D3 저장 | project-local SQLite + immutable revision 파일 | JSON+append log는 친숙하지만 replay/다중 commit 별도 구현 필요 | 내구성 방식 |
| D4 복구/비용 | concurrency 1, 실패 자동 복구 2회 후보; 실제 token/시간 상한 별도 합의 | 더 큰 값은 비용 증가, 0회는 잦은 개입 | 숫자는 아직 미합의; E1도 한도 필요 |
| D5 재계획/정지 범위 | 같은 기준·scope·한도 내 plan revision은 자동; 변경 영향 부분만 정지 | 모든 재계획 사용자 승인 또는 run 전체 정지는 예측성 높지만 개입 증가 | 자동 재계획 권한과 pause 범위 |
| D6 의미 검토 | 모든 gate는 script 실행, 의도 적합성 검토 필수; 독립 AI 세션은 위험/비용에 따라 계약에서 선택 | 항상 독립 reviewer는 비용 증가, 동일 세션 검토는 상관된 오류 위험 | 모든 작업에 4 role 세션 강제하지 않음 |
| D7 단일 세션 | 준비 후 실행 agent 하나를 재사용; AI 조정 세션의 상시 실행 없음 | 처음 대화한 세션 자체만 쓰려면 Orca 재진입/동일 세션 continuation 검증 추가 필요 | 사용자 선호의 정확한 실행 의미 |

이번 요구 합의만으로 D1–D7을 승인 처리하지 않는다.
먼저 E1의 실행 위치·agent/model·비용/시간 한도를 정해 작은 실험을 승인한 뒤,
결과에 맞게 d2와 구현용 실행 명세를 제시하는 순서를 추천한다.
