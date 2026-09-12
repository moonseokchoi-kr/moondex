# 구현 실행 명세 초안 p2 — d3 반영

상태: **검토용, 아직 실행하지 않음**. d1 승인/E1 실행은 이 후속 상세 작업 전부의 사전 승인이 아니다.
기준: 요구 r1, d1 승인 방향, d2, 사용자 변경을 반영한 d3. A01–A20은 유지하고 A21은 d3의 A21-r2로 대체한다. p1 원본은 보존한다.

## 목표와 관찰 결과

사용자가 실행 명세를 승인하면 script가 DAG를 실행하고 필수 검증/통합 보고까지 수행한다.
의미적 판단은 AI가 하되 다음 ready task 선택·메시지 수신·재시도·상태 복구는 script가 한다.
작업 세션 안의 AI 판단과 script 실행을 검증한다. 세션 종료 후 무인 지속 실행은 범위에서 제외하며, 중단 후 새 세션 재개는 필수다.

## DAG와 작업 계약

초기 DAG: `I1 → I2 → I3 → I4 → I5 → I6` (동시성 1).
여러 모듈이 같은 계약을 공유하고 E1에서 adapter 경계 수정이 필요했으므로 지금은 병렬 이익을 확정할 수 없다.
별도 독립 reviewer 세션은 자동으로 추가하지 않는다. 필수 의도 검토 자체는 생략하지 않는다.

| 노드 | 목표/입력 | 수정 범위 제안 | 필수 검증/완료 증거 |
|---|---|---|---|
| I1 | r1/d1/d2/d3에서 immutable bundle·approval·DAG validator 구현 | 새 execution contracts 모듈, 해당 unit tests | A01–A03,A05: 변경 기준·다른 승인·cycle·누락 gate·미정 policy를 거부; digest/fixture receipts |
| I2 | I1 계약으로 event/inbox/outbox/lease/attempt·무효화 저장 | 새 execution store/scheduler 모듈, durability tests | A04,A07,A11–A16: 실제 두 process writer 충돌·crash·replay, 영향 집합과 무관 증거 재사용 |
| I3 | I1/I2 기준에 묶인 command runner·evidence·통합 봉인 | verification/process runner, oracle fixtures | A08–A10: worker success+gate fail, zero tests, stale tree, long-running process, mutation during gate 거부 |
| I4 | I2/I3와 Orca adapter 연결, 한 노드 전체 실행 | Orca adapter, development capability probes | A06,A07,A11–A13,A20: 실제 worker 생성부터 script 단독 gate/cleanup/report, 질문 및 unknown-outcome 보존 |
| I5 | 결과/Compound 기록·독립 self-improve 경계 | result/sync adapter와 destination fixtures | A17–A19: raw byte 변화 없음, template 준수, concurrent user edit 보존, idempotent 결과/기준 분리 |
| I6 | 공개 skill·구형 실행 경로 교체·설치 package 완성 | 새 skill, AGENTS/README, 필요 manifest metadata, runtime inventory | A21-r2 및 A01–A20: 단일 새 workflow, opaque installed path, 과거 기록 보존·구형 state 오인 거부, 실제 E2E+package checks |

각 node 입력은 선행 output tree와 계약 digest에 고정한다. scope 확장은 baseline 변경 절차를 따른다.
산출물은 코드 patch/tree, 검증 정의 hash, 실제 command/exit/log, 기준 적합성 검토 기록이다.
worker 보고만으로 완료 처리하지 않는다. 새로운 execution 모듈은 이 worktree에서 새로 구현하며
원래 orca-native-phase4의 미추적 코드를 가져오지 않는다.

## 검증 계약

필수: unit(승인/전이/DAG), process integration(SQLite/process/crash/receipt), 실제 Orca E2E,
사용자 행동 oracle 부정 fixture, 설치 runtime closure/단일 실행 경로, 저장소 필수 정적 검사.
유효한 기존 회귀 검사를 포함한 전체 suite를 최종 integration에서 실행한다. 구형 workflow 형식만 강제하는 검사는 A21-r2 기준으로 교체한다. browser 등 필수 환경 부족은 blocker로 기록한다.
환경을 조사해 정확한 command argv/toolchain/gate deadline을 채운 후 실행 bundle을 승인 대상으로 제시한다.
현재 초안은 명령·시간/비용 한도가 완전히 채워지지 않았으므로 READY가 아니다.

## 완료·예외

통합 snapshot에서 모든 필수 gate 통과, intent review, blocker 없음, 최종 보고와 필수 Compound 기록까지 완료해야 한다.
제품 복구 횟수는 d1의 추천값을 따르되 비용·시간 한도 및 telemetry 대체 기준은 실행 전 확정한다.
E1의 10분/0 retry를 대규모 구현 기본값으로 가져오지 않는다.
권한 소실/응답 불명확/한도 소진에는 저장하고 정확한 선택지를 보고한다. 긴 test와 실패를 구분한다.
새 기준·scope·권한 변경은 새 revision과 사용자 합의가 필요하다.

## 제외

main merge/push/deploy, plugin publish/reinstall, 원래 worktree 정리, 자동 self-improve,
세션 종료 후 무인 지속 실행, 구형 SDD runtime 공존 및 자동 migration. 상태·증거 보존과 새 세션 재개는 제외하지 않는다.
