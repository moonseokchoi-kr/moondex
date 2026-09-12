# 2026-09-06 d1 승인과 Orca E1 준비

> 사실 기록이다. 요구·설계 기준이나 수용 조건을 바꾸지 않는다.

## Request Context

사용자: “문서를 읽어봤는데, 제안해준대로 진행을 해도 될것 같아”.
d1의 추천 방향을 채택하고 제안 순서대로 E1부터 진행한다.

## SSOT Impact

- 승인 원문·대상 digest·D1–D7 추천 선택: `docs/execution/delegated-execution-redesign/approvals/design-d1.json`.
- 승인된 원본 d1과 요구 r1 바이트는 유지했다.
- Compound 설계 검토 페이지에 후속 승인을 추가하고 log에 기록했다. raw는 변경하지 않았다.
- d1에 미정으로 남은 E1 수치에 대해 질문했다: 현재 worktree 전용 fixture, Codex 기본 모델,
  worker 1개, 자동 재시도 0회, 10분 후 해당 worker만 중지. 답변 전 agent launch를 하지 않는다.
- 금액/token 상한은 telemetry 미확인 상태에서 강제 가능하다고 주장하지 않는다.
- 기존 SDD status/resume은 여전히 BLOCKED_ARTIFACT/no project-local state.
  E1 전용 SQLite는 legacy SDD pipeline 또는 그 승인이 아니다.

## Implementation Changes

`experiments/orca-script-e1/` 아래 development-only 실험 준비:

- `rpc.py`: SQLite intent/receipt, unknown mutation의 무조건 재시도 방지, 같은 identity의 argv 변경 거부.
- `collect.py`: durable inbox 저장, 명시적 중단 지점, 새 프로세스 재수신 비교.
  실제 Delivery schema 확인 전 release/ack는 수행하지 않도록 구성했다.
- `verify_fixture.py`: worker 완료 보고와 별도로 실제 결과/nonce/산술을 검사.
- `check_local.py`: Orca 호출 없는 부정 경로 및 실제 프로세스 종료/재시작 검사.
- `README.md`: 작업 범위·필수 증거·진행 순서·미정 한도.

제품 core/manifest/installed runtime은 변경하지 않았다. 원래 orca-native-phase4는 읽거나 변경하지 않았다.

## Verification

직접 관찰:

- Orca 1.4.193 runtime ready.
- Python subprocess에서 Run 생성 성공: `run_a9c52f3b5b61`.
- 동일 live parent context의 별도 Python 프로세스에서 run-show 및 inbox peek 성공.
- `--from`, 다른 terminal identity, 비공개 인증정보를 사용하지 않았다.
- worker/Task/Dispatch는 아직 생성하지 않았다. 원래 인수인계 세션에 lifecycle 메시지를 보내지 않았다.

로컬 검사 통과:

- timeout으로 결과 불명확한 mutation은 두 번째 외부 호출을 하지 않음.
- 성공 receipt 재사용 시 추가 외부 호출 없음; argv 변경 시 거부.
- SQLite commit 후 실제 process exit 86, 새 process 재입력 후 inbox row는 1개.
- fixture 출력 없음·잘못된 값·stale nonce는 FAIL, 올바른 값은 PASS.

증거: `.harness/audit/execution/orca-script-e1/`의 `create-run.*`, `inspect-run.*`, `peek-shape.*`, `local-checks.json`.
상태: `.harness/state/execution/orca-script-e1/experiment.sqlite`.
이 로컬 검사는 Orca Delivery replay 또는 production executor E2E 통과를 뜻하지 않는다.

## Residual Gaps

E1은 진행 중이며 완료 아님. worker launch, 실제 Delivery 중단/재수신, fixture end-to-end,
worker release, parent 종료 후 인증·재개는 아직 미검증이다.
script/collector의 실제 응답 schema를 receipt로 확인하면서 후속 처리를 완성해야 한다.
미정 자원 한도에 대한 사용자 답변이 도착하면 이 Run에 한 Task/worker만 생성해 이어간다.
답변 대기 중 agent를 실행하거나 Run을 추가 생성하지 않는다.
