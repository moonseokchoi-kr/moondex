# 위임 실행 구현 결과 — 2026-09-10

## 기준과 결과의 경계

승인 기준은 [d5](../execution/delegated-execution-redesign/2026-09-10-design-d5.md)와
[구현 승인 기록](../execution/delegated-execution-redesign/approvals/implementation-d5.json)이다.
사용자 요청은 “Implement the plan.”이다. 이 문서는 사후 구현·검증 기록이며 기준을 변경하지 않는다.
작업 기준 main은 `fbf072e3d341c43f57b26b6c144e2fcb76e2556d`다.

## 사용자가 관찰할 변화

`$moondex:execute`가 합의한 실행 bundle을 고정하고, 현재 대화 AI 또는 명시한 Orca 작업자에게 작업을 배정한다.
AI가 제출하고 `advance`를 호출하면 스크립트가 의존성·동시성·필수 검증·다음 작업을 결정한다.
완료 보고만 제출하거나 테스트가 0개 수집되면 완료되지 않는다. 통합 검증과 의도 검토,
설정된 필수 지식 기록까지 충족해야 `COMPLETED`가 된다.

`.moondex/STATE.json`은 조회 snapshot이며 hash 연결 event가 복구 근거다. 중단 후 `resume`은
이미 배정한 작업·관찰 중인 테스트·수신한 Delivery를 다시 연결한다. 별도 무인 scheduler는 없다.
긴 검증은 대기하며 총시간·토큰 상한은 두지 않는다. 확인된 실패의 자동 복구는 최초 시도 뒤 최대 2회다.
추가 복구, 기준 변경, 불명확한 외부 실행은 증거와 질문을 저장한다.

취소는 새 작업을 중지하고 남은 node/통합 process를 기록한다. 실제 종료 확인을 `answer`로 남기면
소유권을 해제하되 취소 상태는 유지한다. 일반 feedback으로 취소를 되돌릴 수 없다.

## 구현 범위

| 단계 | 구현 |
|---|---|
| I1 계약 | `harness_core/execution/contracts.py`: 승인 digest, 요구/설계/검증, DAG, 읽기/쓰기 범위, gate 정의 hash |
| I2 상태 | `store.py`, `engine.py`: 단일 writer, immutable objects, fsync event/atomic snapshot, current-AI 배정과 중복 방지 |
| I3 검증 | `runner.py`: 실제 subprocess, 양성/결함 oracle, 수집 수·assertion·tree·명령·환경·로그 receipt, 통합 검증 |
| I4 Orca | `orca.py`: 실제 Task/Dispatch, intent-before-effect, Delivery 저장/replay/ack, 소유 worker release, 같은 실패 Task의 retry-of |
| I5 피드백/기록 | 영향 증거 무효화, 불변 revision/승인, 수정 한도 계승, `compound.py`의 opt-in wiki 기록과 충돌/중단 복구 |
| I6 제품 연결 | execute skill, package-relative 설치 launcher/inventory, 공개 SDD 퇴역, CI 명령 수정, 자동 hook 등록 제거 |

설치 manifest는 skills-only인 0.5.0이다. 공용 launcher의 기존 디렉터리 이름과 일부 legacy 내부 모듈은
다른 기능의 회귀 검증을 위해 남아 있다. 공개 SDD state/result-action/phase preflight는 실행을 거부한다.
다른 스킬의 광범위 개선, merge/push/deploy/reinstall은 이번 변경에 포함하지 않았다.

## 수용 조건과 실제 증거 대응

경로 약어: E=`tests/execution/`, B=`tests/e2e/test_codex_harness_acceptance.py`.
아래 대응은 구현 형태에 대한 주장과 실제 실행 관찰을 구분한다. pytest fixture의 의도적 사용자 승인/응답은
시험 입력이며 실제 사용자 승인 이력을 대신하지 않는다.

| 기준 | 검증과 관찰 |
|---|---|
| A01 | E/test_execution.py current-session 실제 출력42, gate와 통합 완료; phase 문서 강제 없음 |
| A02–A03 | 승인 digest 불일치·bundle 변조·오래된 assignment 거부; gate/tool 정의 hash 및 설치 tamper 시험 |
| A04 | live A/B/C: A·B 병렬, 최대 active2, A 성공 event63 이후 C 시작66; 단일 node도 production Engine 사용 |
| A05 | 실행 계약 cycle/누락 검증 거부, ancestor writer/descendant reader 충돌 시험; 명시 lock과 scope로 배정 제한 |
| A06 | production Orca의 실제 Task/Dispatch/worker 결과와 파일 A42/B22/C84 관찰 |
| A07 | live Delivery 저장 직후 exit86 및 replay; 이중 실제 process writer 시험; gate launch 응답 손실 재연결; unknown RPC 비반복·기존 dispatch 조회 시험 |
| A08 | 제출 자체로 완료 불가; forged submission/receipt, source 변경, 실패 gate, log/report 변조 차단 |
| A09 | B의 실제 browser click 결과 및 no-op 결함 oracle; E의 테스트0개 완료 차단 |
| A10 | 통합 gate를 새 snapshot에서 재실행; B의 필수 consumer-E2E 실패 및 E의 제출 후 tree 변경 차단 |
| A11 | 실제 지연 subprocess가 관찰 창을 넘겨도 살아 있고 repair 수가 증가하지 않는 시험 |
| A12 | 잘못된 출력3회 → 자동 복구2회 → 개입, 명시 답변 후 재개; 별도 live 실패 Task retry-of 1회 |
| A13 | 부모 호출 재시작, stale/duplicate 제출·답변, 일반 worker 질문의 AI 판단 경로, cancel 자원 종료 확인 |
| A14 | 기준 revision 승인 후 재개; 독립 N2의 완료 attempt/receipt 보존, 이전 결과 파일 byte 보존 |
| A15 | 구현 결함 재현/수정; 검증이라는 이름으로 기대값 완화 시 baseline 승인 요구 |
| A16 | 요구/설계 변경은 matching digest 답변 전 대기; 범위와 필수 gate coverage 계약 검사 |
| A17 | 미설정 SKIPPED; 설정 fixture의 template/index/log 기록, raw 쓰기 거부, 동시 사용자 편집 보존, 실제 process crash 후 partial write 재연결 |
| A18 | 필수 기록 전 REPORTING, sync 재호출 중복 방지, 기존 기준 prefix 보존 및 결과 별도 저장 |
| A19 | 실행 본체는 시도/실패/질문/receipt만 저장; self-improve 자동 호출 경로 없음(소스 점검). 별도 기존 self-improve 회귀 시험 유지 |
| A20 | live 정상3작업과 failed→succeeded 복구를 단계 승인 추가 없이 수행, 전체 결과 검토 후 완료 |
| A21-r2 | opaque installed path에서 production execute와 browser 실행, old SDD 호출 퇴역/과거 문서 보존, recursive inventory 검증 |

## 실제 Orca 실행

- A/B/C 원본: `.harness/audit/execution/production-orca-abc/`.
  `acceptance-observations.json`에 실제 값, 시작/성공 event, 12개 gate receipt, 모든 worker release를 기록했다.
  C Delivery `delivery_2a805cbf4b4e` 저장 후 process를 실제 종료했고, 동일 메시지 효과는 한 번만 적용됐다.
- 실패/복구 원본: `.harness/audit/execution/production-orca-repair/`.
  Task `task_b7e5dc9dff6a`의 `ctx_633862bb7d4c`가 failed,
  같은 Task의 `ctx_5a12f5647090`가 `--retry-of`로 succeeded. 실제 출력은41→42, repair1, 모두 release됐다.
- 두 시험 모두 node gate 후 통합 gate와 현재 AI의 출력/의도 검토를 수행했다.
  이 관찰은 최초 구현의 Orca 경로를 검증한다. 이후 취소 복구 보완은 로컬 회귀 테스트로 별도 검증했다.

## 검증 이력과 한계

첫 전체 실행은 351 passed/13 failed였다. 공개 SDD 퇴역에 따른 옛 기대값과 변경 중 inventory 불일치를 수정했다.
기존 보호 기능 시험은 유지했고, simulation 위주의 완료 시험은 production 실행과 실제 browser 행동 시험으로 교체했다.
CI fixture의 누락 설정을 명시하고 실제 지원되는 CLI 명령을 격리 Git repository에서 검증했다.
두 번째 전체 실행은 367 passed/120.06s. 취소 복구 보완 후 최종 전체 실행은 **368 passed / 126.72s**로 통과했다.
원본 로그는 `.harness/audit/execution/implementation-d5/`에 보존한다.

30개 정적 검사(JSON manifest, skill frontmatter, hook shell 구문, Python compile, plugin/skill validator,
diff whitespace)가 통과했다. 기존 hook wrapper의 독립 회귀 시험은 유지하되 `hooks/hooks.json` 등록은 비웠다.
d1 SHA256은 `2669fd0e2d7addb739c0799be75f60d9ee1a483512aa6c0c8dd10b5783510e03`으로 보존했다.

별도 세션의 Orca 인증 인수나 부모 종료 후 무인 스케줄링은 지원 검증으로 주장하지 않는다.
확인할 수 없는 외부 실행은 `RECOVERY_REQUIRED`로 멈춘다. 같은 OS 계정의 임의 파일 변조에 대한
보안 격리 제품도 아니다. 명령 hash/receipt와 AI 의도 검토는 승인 기준에 맞는 검증을 위한 계약이다.
개인 Compound 경로는 이 작업의 명시적 기록 대상이며 제품 기본값이 아니다.

최종 검증: [영수증](../execution/delegated-execution-redesign/results/2026-09-10-implementation-validation.json).

로컬 원본 로그의 2026-09-13 보관 위치와 hash 검증은 [로그 정리 기록](2026-09-13-local-evidence-and-commit.md)을 참조한다.
