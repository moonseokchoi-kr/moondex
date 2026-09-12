# 2026-09-06 Moondex 위임 실행 전환 조사와 설계

> 작업 기록이며 제품 SSOT가 아니다. 승인된 요구가 이 기록보다 우선한다.

## Request Context

사용자의 소유권 인수인계에 따라 요구 11항을 보존하고 최신 main 기반 구조/동작을 조사해 상세 개편 설계를 작성했다.
기준 HEAD는 `fbf072e3d341c43f57b26b6c144e2fcb76e2556d`이며 시작 시 checkout은 clean이었다.
원래 `orca-native-phase4`와 그 미추적 실행 코드·테스트는 읽거나 가져오거나 변경하지 않았다.
Orca task/dispatch 생성, worker 메시지, worker_done 전송은 하지 않았다.

## SSOT Impact

- 읽은 규칙: 현재 `AGENTS.md`, Compound `CLAUDE.md`·`wiki/index.md`·page/hub template.
- 참고 스킬: SSOT change management, idea-workshop의 설계/검증 지침, compound-query/ingest, Orca CLI/orchestration 설치 가이드.
- 현재 SDD/실행 skill과 과거 HANDOFF는 현행 구조 파악용으로 읽었다. 과거 approval·작업 상태·push 지시는 이번 권한으로 승계하지 않았다.
- 승인 요구 보존: Compound `wiki/moondex-delegated-execution-requirements-r1.md`.
  사용자 전달문 11항을 그대로 보존하고, 과거 메시지 ID/승인 시각은 제공되지 않았다고 명시했다.
- 미승인 제안: [개편 설계 d1](../sdd/design/arch/2026-09-06-delegated-execution-redesign.md).
- Compound 사실 기록: `wiki/moondex-delegated-execution-design-review.md`; hub/index/log 연결 포함 총 5개 파일 변경.
- 기준 r1의 SHA-256은 설계에 연결했다. 제품 기본 설정에 개인 DB 경로를 추가하지 않았다.
- 기존 wiki 구상은 유지하고 허브에 현재 요구 우선 경계를 추가했다. raw에는 쓰지 않았다.
- 미결정: 진입점/이행, Orca script 실행 context, 저장 방식, 복구·비용 한도, 재계획 권한, 검토 독립성, 단일 세션 의미(D1–D7).

## Implementation Changes

제품 구현 변경 없음. 설계 d1은 실행 명세, 책임, 상태 전이, 승인 revision,
증거·통합·피드백·복구, Orca 실험 E1, Compound 기록, 전환 범위, 수용 테스트 A01–A21을 제안한다.
현재 feature에 SDD start/transition 또는 승인 레코드를 만들지 않았다.

## Verification

실제 조사와 가상의 미래 수용 조건을 구분한다.

| 확인 | 관찰/한계 |
|---|---|
| Git HEAD/초기 status | 지정 main commit 일치, 초기 clean |
| package-relative controller status와 resume | 둘 다 BLOCKED_ARTIFACT/no project-local state; `.harness/state/` 생성 없음 |
| 격리 baseline probe | 테스트 없는 complete+notes로 RESULT preflight 통과; 승인 후 spec 변경 감지 없음; 비실행 command 문자열로 policy 통과; RESULT 문서 존재 시 COMPLETE |
| Orca status | 1.4.193 runtime ready 직접 관찰 |
| Orca guides + worker-start/run-use/check help | 명령/Delivery/수명주기 계약 읽음; 실제 script 인증·worker lifecycle 미검증 |
| plugin manifest/marketplace JSON | parse 통과 |
| skill frontmatter | 전체 name/description 검사 통과 |
| hooks shell syntax | 대상 각 파일을 개별 bash -n 검사하여 통과 |
| stop-pipeline.py compile | 통과 |
| 새 wiki 양식/링크, 요구 1–11, 수용 A01–A21, 결정 D1–D7, 요구 digest | 구조 및 연결 확인 |

로컬 증거:

- `.harness/audit/delegated-execution-redesign/probe.py`, `probe-output.json`.
- 같은 디렉터리의 `controller-status.json`, `controller-resume.json`.
- `orca-orchestration-guide.txt`, `orca-cli-guide.txt`, `orca-status.json`, 세 help 출력.
- `read-receipts.json`: 읽기 명령·exit code·출력 digest.
- `validation.json`: 구조/문법/컨트롤러 읽기 검증 결과. 이는 전체 pytest 결과가 아니다.

재현 fixture는 임시 디렉터리에서 synthetic approval boolean을 사용했다. 사용자 승인이나 실제 workflow transition을 뜻하지 않는다.
조사 중 일부 추정 파일명(`state/controller.py`, `validation/preflight.py` 등)은 존재하지 않아 읽기에 실패했다.
파일 목록으로 실제 `state/pipeline.py`, `validation/policy.py`, `skills/sdd-orchestrator/scripts/result-action.py`를 찾아 근거를 확인했다.
Compound 디렉터리는 Git 저장소가 아니므로 Git diff로 KB 변경을 검증했다고 주장하지 않는다.

### 주요 코드 근거

- `harness_core/state/pipeline.py`: Phase/approval boolean, `preflight_phase`, `_task_completion_error`, `inspect_state`.
- `harness_core/state/storage.py`: atomic replace/fsync와 flock.
- `skills/sdd-orchestrator/SKILL.md`: AI 역할에 wave loop·검토·test dispatch를 요구.
- `skills/sdd-orchestrator/scripts/result-action.py`: `_validate_evidence`는 supplied verified/PASS/nonempty text 검사;
  `_sync_outputs`는 configured Compound의 raw/projects snapshot 경로를 만든다.
- `harness_core/validation/policy.py`: `_valid_tdd_manifest`, `_valid_e2e_config`는 필드/문자열 검사.
- `tests/e2e/test_codex_harness_acceptance.py`: `_SoleWriterSimulation`은 test-owned이며 production scheduler API가 아님.

## Residual Gaps

전체 기존 pytest/build/browser suite는 실행하지 않았다. 이번 변경은 기록/설계이며 향후 제품의 검증을 통과시킨 작업이 아니다.
A01–A21은 제안된 수용 조건이고 모두 미실행이다. E1도 미승인·미실행이다.
기존 main 기능의 완전성, detached script 인증, 외부 side effect exactly-once, 실제 예산 강제 가능성을 확인했다고 주장하지 않는다.
다음 단계는 D1–D7 선택과 E1의 위치·agent/model·비용/시간 한도를 합의하고 그 한정 실험을 실행하는 것이다.
이 단계의 승인도 대규모 구현 승인으로 확대 해석하지 않는다.
