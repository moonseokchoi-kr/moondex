# HANDOFF: moondex multi-agent planner-executor runtime

> 이 문서는 새로운 에이전트가 컨텍스트 없이 이 파일만 읽고 바로 작업을 이어갈 수 있도록 작성되었다.

## 프로젝트 한줄 요약

`moondex`는 외부의 `spec`, `design set`, `implementation design set`를 입력으로 받아 Codex가 `task`, `plan`, `wave`를 만들고, `cmux` 작업면 위에서 멀티에이전트 실행을 안정화하는 state-first runtime이다.

## 현재 상태

| 항목 | 상태 |
|------|------|
| 방향 정리 | **완료** — `executor-first`에서 `design-informed multi-agent planner-executor`로 정리됨 |
| 입력/산출물 계약 | **완료** — `task`, `plan`, `wave` 스키마와 템플릿 문서 존재 |
| `task-planner` 스킬 | **완료** — 플러그인 skills 구조로 `skills/moondex-task-planner/SKILL.md`에 정리됨 |
| `task-planner` 에이전트 | **완료** — `.codex/agents/task-planner.toml` 생성됨 |
| `cmux` 스킬 | **완료** — 플러그인 skills 구조로 `skills/moondex-cmux/SKILL.md`에 정리됨 |
| 멀티에이전트 운영 초안 | **진행 중** — 상태 머신, role dispatch, compliance/tester 기준이 문서화됨 |
| task state machine | **진행 중** — 상세 상태값 초안은 합의됐고 runtime claim lifecycle이 구현됨 |
| role selection / dispatch | **진행 중** — Rust `moondex` CLI MVP가 task/claim/dispatch state와 lifecycle guard를 강제함 |
| role transfer contract 정의 | **완료** — 실행/planning/tester payload-ready 문서와 `.codex/hooks` 검증 entrypoint 작성됨 |
| `cmux` 운영 규칙 | **완료** — state-first 운영 원칙과 반복 가능한 절차가 `cmux-operations-playbook.md`로 문서화됨 |
| OMX/team runtime 비교 | **완료** — `docs/execution/cmux-runtime-alignment.md`에 이어받기 기준과 isolation/archive 정책 정리됨 |
| runtime 강제 레이어 | **진행 중** — Rust `moondex` crate와 CLI MVP가 validator, hook warnings, next-action, event log, hook inspection까지 포함함 |

## 핵심 문서 위치

| 문서 | 경로 | 용도 |
|------|------|------|
| 방향 기준 | `docs/executor-direction.md` | 프로젝트가 무엇을 만들고 있는지 고정하는 기준 문서 |
| planning 절차 | `docs/planning/planning-workflow.md` | `spec/design set/implementation design set -> task -> plan -> wave -> execution` 흐름 |
| task-planner agent 계약 | `docs/planning/task-planner-subagent.md` | `task -> plan` 전용 planner agent 역할과 입력/출력 계약 |
| 멀티에이전트 운영 초안 | `docs/execution/multi-agent-orchestration.md` | 상태 머신, dispatch, role transfer contract, `cmux` 운영을 정리하는 작업 문서 |
| role transfer contracts | `docs/execution/role-transfer-contracts.md` | 역할 간 canonical input/output contract 초안 |
| `cmux` runtime alignment | `docs/execution/cmux-runtime-alignment.md` | `oh-my-codex` `$team`/tmux runtime을 `cmux` 기반 Moondex로 번역하는 기준 |
| `cmux` operations playbook | `docs/execution/cmux-operations-playbook.md` | role surface 준비부터 archive까지 반복 가능한 실제 운영 순서 |
| `moondex` CLI plan | `docs/execution/moondex-cli-plan.md` | Rust runtime CLI의 MVP command, state root, envelope 기준 |
| Codex hook auto-discovery | `docs/execution/codex-hook-auto-discovery.md` | `.codex/hooks` repo-local discovery와 lifecycle bridge 운영 기준 |
| plan 계약 | `docs/contracts/plan-schema.md` | executor-ready `plan`의 최소 계약 |
| plan 템플릿 | `docs/templates/plan-template.md` | `plan` 작성 형식 |
| task-planner 스킬 | `skills/moondex-task-planner/SKILL.md` | planner agent가 따라야 할 직접 지침 |
| task-planner 에이전트 | `.codex/agents/task-planner.toml` | 공식 Codex custom agent 엔트리 |
| `cmux` 스킬 | `skills/moondex-cmux/SKILL.md` | 멀티 세션 운영 보조 스킬 |

다음 에이전트는 우선 `docs/execution/cmux-runtime-alignment.md`, `docs/execution/multi-agent-orchestration.md`, `docs/executor-direction.md`, `docs/planning/planning-workflow.md`를 읽으면 충분하다. `role-transfer-contracts.md`는 runtime payload로 내릴 때 같이 읽는다.

## 완료된 작업

### 1. 저장소 방향 전환
- `legacy SDD prototype`식 SDD 스캐폴드 중심 구조를 걷어내고 planner-executor 중심 문서 저장소로 재정리했다.
- 핵심 방향은 `docs/executor-direction.md`에 고정했다.
- 사용자 결정:
  - Codex는 상위 설계 생성기가 아니라 planning + execution 레이어를 맡는다.
  - 외부 입력은 `spec`, `design set`, `implementation design set`다.
  - `task`, `plan`, `wave`는 Codex가 만든다.

### 2. 계약 문서와 템플릿 정리
- `docs/contracts/task-schema.md`, `docs/contracts/plan-schema.md`, `docs/contracts/wave-schema.md`를 정리했다.
- `docs/templates/task-template.md`, `docs/templates/plan-template.md`, `docs/templates/wave-template.md`를 추가했다.
- `plan`은 `task`보다 더 구체적인 `plan mode` 수준 문서가 되어야 한다는 결론을 반영했다.

### 3. `task-planner` 스킬과 에이전트 작성
- 공식 Codex skills/subagents 문서를 참고해 `skills/moondex-task-planner/SKILL.md`와 `.codex/agents/task-planner.toml`을 만들었다.
- `task-planner`는 broad planning이 아니라 `task 하나 -> plan 하나`만 담당한다.
- 사용자가 명시적으로 요구한 결정:
  - planner 쪽은 더 좋은 모델을 써야 하므로 `gpt-5.4` high로 두었다.
  - 스킬과 에이전트는 분리하고, 에이전트가 스킬을 사용하도록 둔다.

### 4. `cmux` 스킬 가져오기
- `~/.claude/skills/cmux`를 운영 레퍼런스로 보고 Codex용 `skills/moondex-cmux/SKILL.md`를 만들었다.
- `cmux`는 source of truth가 아니라 실행 화면 분리와 모니터링을 위한 운영 레이어로만 사용한다.

### 5. 멀티에이전트 운영 초안 작성
- `docs/execution/multi-agent-orchestration.md`를 만들었다.
- 현재 문서에 들어간 핵심 합의:
  - 메인 오케스트레이터가 전체 상태를 가진다.
  - `task-planner`는 planning layer의 하위 역할이다.
  - `wave-dispatcher`는 `plan set` 이후에만 동작한다.
  - implementer는 `validated-ready` 상태의 task만 받는다.
  - task 상태 머신은 상세하게 유지하는 편이 낫다.

### 6. runtime 모델 재정의
- 중요한 방향 수정이 있었다.
- 원래는 `spawn_agent`와 `cmux`를 혼용하는 식으로 진행됐지만, 이건 Moondex 설계를 흐린다는 결론에 도달했다.
- 현재 합의:
  - Moondex 본래 runtime은 `spawn_agent` 중심이 아니다.
  - role execution은 `cmux` 같은 멀티플렉서 위의 **role별 터미널 작업면 dispatch**가 기본이다.
  - `spawn_agent`는 참고 실험이나 보조 수단일 수는 있어도, Moondex의 표준 실행 경로를 대체하면 안 된다.
- 이 합의는 아래 문서에 반영됐다.
  - `docs/executor-direction.md`
  - `docs/planning/planning-workflow.md`
  - `docs/execution/multi-agent-orchestration.md`

### 7. `money_track`로 T-04 일부 루프 검증
- `money_track`에서 `T-04 App Shell, Navigation, And Route Gate Contracts`의 일부를 검증했다.
- 실제 결과:
  - stale codegen 문제를 먼저 복구해야 했고, 이 과정에서 `build_runner` 재생성으로 테스트가 다시 동작하게 됐다.
  - 이후 `T-04`의 onboarding redirect / reset -> onboarding contract 일부를 검증했다.
  - 하지만 처음에는 `spawn_agent` 중심으로 implementer/reviewer를 돌려, 원래 의도한 터미널 기반 Moondex 검증과 어긋났다.
- 남긴 교훈:
  - product fix를 Moondex 검증보다 우선하면 방향이 쉽게 무너진다.
  - `cmux` pane을 단순 관찰용으로 쓰는 것은 충분하지 않다.
  - reviewer 왕복 루프까지 포함한 role-based terminal execution이 필요하다.

### 8. T-11 slice 후보 식별
- `T-11 Cross-Flow Validation, Review Escalation, And Regression` 전체는 너무 크다.
- 대신 `scenario_6_settings_reset_onboarding` 같은 기존 integration scenario를 **T-11 slice**로 잡아 implementer/reviewer loop를 태우는 방향이 더 적절하다는 판단이 나왔다.
- 현재 `money_track`에는 `integration_test/`가 이미 존재한다.
- 따라서 예전 문서의 “integration target 없음” 가정은 더 이상 맞지 않는다. 다음 작업에서 문서 정리가 필요하다.

### 9. role transfer contract payload-ready 문서화
- `docs/execution/role-transfer-contracts.md`를 실행 루프 중심 payload-ready 문서로 갱신했다.
- 포함된 범위:
  - implementer input/output
  - `code-reviewer` input/output
  - `compliance-reviewer` input/output
- 각 role output은 현재 `write-mailbox` kind/body schema와 연결했고 복사 가능한 CLI 예시를 포함한다.
- `.codex/hooks/validate-role-transfer.sh`가 `moondex api validate-role-transfer`를 호출해 contract hard error를 non-zero exit로 막는다.
- `task-planner`, `wave-dispatcher`, tester의 payload-ready 예시와 validator가 추가됐다.

### 9.5 Work tracker W-01부터 W-08 구현
- `docs/execution/WORK_TRACKER.md`를 추가했다.
- 남은 runtime 작업을 `W-01`부터 `W-08`까지 실행 큐로 정리했다.
- `docs/execution/work-items/W-01-planning-contracts-payload-ready.md`에 W-01 전용 executor-ready 계획을 저장했다.
- `docs/execution/work-items/` 아래에 W-02부터 W-08까지 전용 executor-ready 계획도 저장했다.
- 2026-04-26 기준 W-01부터 W-08까지 완료했다.
- 2026-04-27 기준 W-09 same-task review phase runtime과 W-10부터 W-13까지의 automation hardening도 완료했다.
- 2026-04-27 기준 W-14 phase event log, W-15 cmux 운영 플레이북, W-16 repo-local Codex hook inspection도 완료했다.
- 구현된 항목:
  - planning payload validator: `task_planner_input`, `task_planner_output`, `wave_dispatcher_input`, `wave_dispatcher_output`
  - readiness validator: `moondex api validate-readiness` and `.codex/hooks/validate-readiness.sh`
  - lifecycle hook integration: `write-mailbox` hard validation, dispatch guards, `.moondex/state/hooks/warnings.json`
  - compliance escalation policy and validator warnings
  - canonical `tester` role and `tester_input`
  - advisory `moondex api next-action --json`
  - worktree isolation modes: `no_worktree`, `external_worktree`, `future_managed_worktree`
  - runtime retention/archive policy and implemented `archive-state` command shape
  - same-task phase transfer: `implementation -> code_review -> compliance_review/testing -> done`
  - phase-aware rich role inbox payload with previous task messages and expected output contract
  - executable `orchestrator-step` and bounded `orchestrator-loop`
  - implemented `archive-state` dry-run/apply command
  - append-only `.moondex/state/events.jsonl` event stream and `moondex api list-events`
  - malformed event log audit reporting
  - `moondex api inspect-hooks` for executable `.codex/hooks` validators

운영 원칙:

- `cmux` 화면은 source of truth가 아니다.
- `.moondex/state`가 source of truth이고, phase/runtime history는 active `.moondex/state/events.jsonl`에 보존된다.
- `archive-state`는 events를 archive 대상으로 삼지 않는다.

### 10. `oh-my-codex` `$team` runtime 비교 시작
- 사용자가 마지막으로 하던 작업은 `https://github.com/Yeachan-Heo/oh-my-codex`를 보고 `cmux` 기반 작업을 맞추는 것이었다.
- 참고한 핵심은 `$team` skill의 tmux 기반 durable worker runtime이다.
- 중요한 교훈:
  - 핵심은 tmux 자체가 아니라 durable state, worker lifecycle, inbox/mailbox, task claim, guarded transition이다.
  - terminal send는 primary mutation path가 아니라 worker wake-up trigger 또는 fallback이다.
  - `omx team api ... --json` 같은 machine-readable mutation API가 runtime 안정성의 핵심이다.
  - 이 저장소에서는 tmux 명령을 직접 쓰지 않고 `cmux` surface/pane 명령으로 번역해야 한다.
- 이 기준은 `docs/execution/cmux-runtime-alignment.md`에 정리했다.

### 11. Rust `moondex` CLI MVP 시작
- 프로젝트 이름은 목적을 명확히 드러내는 `moondex`로 확정했다.
- Rust workspace와 `crates/moondex`를 생성했다.
- 현재 구현된 최소 command:
  - `moondex init`
  - `moondex status --json`
  - `moondex dispatch <role> <task-id> --json`
  - `moondex role register-current <role-id> --json`
  - `moondex cmux identify --json`
  - `moondex cmux capture --surface <surface> --lines <N> --json`
  - `moondex api create-task/read-task/list-tasks/claim-task/transition-task/release-task`
  - `moondex api write-role-identity/write-role-status`
  - `moondex api list-dispatch/read-dispatch/ack-dispatch/retry-dispatch`
  - `moondex api write-mailbox/read-mailbox/mark-mailbox-read/consume-mailbox/consume-mailbox-for-task`
  - `moondex api list-evidence`
  - `moondex api list-stale-roles`
  - `moondex api audit-state/repair-state`
  - `moondex api next-action`
  - `moondex api orchestrator-step/orchestrator-loop`
  - `moondex api archive-state`
- state root는 `.moondex/state`다.
- dispatch는 state-first로 `dispatch/requests.json`에 먼저 기록하고, role identity에 `surface_ref`가 있으면 `cmux send --surface <surface>`를 wake-up trigger로 시도한다.
- dispatch inbox에는 task payload, previous relevant mailbox messages, expected output contract가 들어간다.
- `cmux send` 실패는 dispatch request를 `failed`로 표시한다. `cmux send` 성공은 `notified`일 뿐 `delivered`가 아니다.
- `ack-dispatch`가 worker-side 수신 증거이며 dispatch request를 `delivered`로 바꾼다.
- `write-role-status`는 `.moondex/state/roles/<role>/status.json`에 heartbeat/progress를 기록한다.
- `write-mailbox`는 기본적으로 `.moondex/state/mailbox/orchestrator.json`에 worker 결과/질문/blocked 메시지를 누적한다.
- `mark-mailbox-read`와 `consume-mailbox`는 메시지를 삭제하지 않고 `read_at`, `consumed_at`을 기록한다.
- `read-mailbox`는 `task_id`, `unread_only`, `unconsumed_only` 필터를 지원한다.
- `consume-mailbox-for-task`는 `message_id` 직접 복사 없이 `task_id`와 선택적 `from_role`/`kind`로 첫 unconsumed 메시지를 소비한다.
- `write-mailbox`는 `kind` allowlist와 kind별 JSON object string `body` schema를 검증한다.
- `role register-current`는 `cmux identify`의 `caller.surface_ref`를 사용해 현재 surface를 role identity로 등록한다.
- `cmux capture`는 `cmux capture-pane` 결과를 `.moondex/state/evidence/`에 텍스트 파일로 저장하고 `evidence/index.json`에 메타데이터를 남긴다.
- `cmux send/capture` 전 `cmux tree --json`으로 target surface 존재를 검증한다. invalid surface가 현재 surface로 fallback되는 cmux 동작을 막기 위한 방어다.
- `retry-dispatch`는 기존 request id를 유지하고 최신 role identity의 surface를 다시 resolve해 전송한다.
- `retry-dispatch`는 `retry_count`와 `retry_history`에 attempt surface, outcome, reason을 남긴다.
- `retry-dispatch`는 request별 최대 3회만 허용하며, 초과 시 전송하지 않고 `last_reason=retry_exhausted`로 failed 상태를 기록한다.
- `audit-state`와 `repair-state`는 legacy invalid mailbox/dispatch state를 보고하고 안전한 범위에서 수정한다.
- `next-action`은 advisory이고, `orchestrator-step/loop`가 안전한 action만 실제 적용한다.
- `archive-state`는 completed task, consumed mailbox, delivered dispatch, optional hook warnings를 archive manifest와 함께 `.moondex/state/archive/<archive-id>/`로 이동한다.
- dispatch trigger는 shell-safe comment와 newline으로 전송한다: `# moondex: read your inbox for task <task-id>\n`.
- 검증:
  - `cargo fmt`
  - `cargo test -p moondex`
  - `/tmp/moondex-smoke-2`에서 `init`, `create-task`, `dispatch`, `ack-dispatch`, `write-role-status`, `write-mailbox`, `read-mailbox`, `status`, `cmux identify`, `cmux capture`, `list-evidence` CLI smoke 수행
  - 현재 repo `.moondex/state`에서 `role register-current`, `mark-mailbox-read`, `consume-mailbox`, `read-mailbox --unconsumed` smoke 수행
  - 실제 `cmux` surfaces로 `T-RUNTIME-01` loop 수행:
    - orchestrator `surface:2`
    - implementer `surface:14`
    - reviewer `surface:15`
    - 결과: task `completed`, dispatch `delivered=2`, mailbox message `2`, evidence capture `2`
  - 실제 `cmux` surfaces로 `T-RUNTIME-02` helper-inclusive loop 수행:
    - `role register-current`로 orchestrator/implementer/reviewer surface 자동 등록
    - implementer: dispatch ACK, claim, status write, mailbox result, terminal transition, evidence capture
    - reviewer: dispatch ACK, unconsumed mailbox read, evidence list 확인, implementer message consume, approval mailbox write, evidence capture
    - orchestrator: reviewer approval message consume
    - 결과: task `completed`, dispatch `delivered=4` total, `T-RUNTIME-02` 관련 mailbox lifecycle closed, evidence capture 누적 `4`
  - risk probe 수행 결과는 `docs/execution/moondex-risk-probes.md`에 기록했다.
  - `consume-mailbox-for-task` smoke:
    - `T-RUNTIME-03`에 implementer result mailbox를 쓰고 `message_id` 없이 task/from_role/kind로 consume했다.
    - 결과: 해당 메시지에 `read_at`, `consumed_at`이 기록됐다.
  - retry history smoke:
    - `T-RISK-HISTORY-01`에서 invalid `surface:999999`로 failed dispatch를 만든 뒤 최신 identity `surface:2`로 retry했다.
    - 결과: 동일 request id `dispatch-broken_worker-1777188159870`가 `notified`, `retry_count=1`, `retry_history[0].outcome=notified`가 됐다.
    - smoke 후 `broken_worker` role identity는 `surface:14`로 되돌렸다.
  - `audit-state` 재실행 결과 mailbox/dispatch issue 모두 `0`.
  - risk probe 중 발견한 문제:
    - `read-mailbox`가 `task_id`를 무시했다. 수정 완료.
    - `write-mailbox`가 빈 body와 임의 kind를 허용했다. 수정 완료.
    - stale role detection 명령이 없었다. `list-stale-roles` 추가 완료.
    - `cmux send --surface surface:999999`가 현재 surface로 fallback했다. surface existence/target mismatch 검증 추가 완료.
    - failed dispatch same-request retry가 없었다. `retry-dispatch` 추가 완료.
    - 수정 전 legacy invalid state가 남았다. `audit-state`, `repair-state` 추가 및 현재 repo state repair 완료.

### 12. 실제 `cmux` runtime loop에서 발견한 문제와 수정
- 첫 implementer dispatch에서 trigger text가 newline 없이 shell prompt에 남아 다음 `ack-dispatch` command와 붙었다.
- 증상: `moondex: read your inbox..../target/debug/moondex ...` 형태로 실행되어 `zsh: command not found: moondex:`가 발생했다.
- 수정: dispatch trigger를 `# moondex: read your inbox for task <task-id>\n`로 바꿔 shell comment로 안전하게 실행되도록 했다.
- reviewer dispatch는 수정 후 trigger가 shell comment로 처리되어 정상 ACK가 가능했다.

## 미완료 작업

### 즉시 필요
1. **W-14+ 후보를 새로 정의** — W-01부터 W-13까지 완료됐으므로 새 작업은 Work Tracker에 새 번호로 추가한다.

### 후속 작업
1. native Codex hook auto-discovery를 안정적으로 연결할 수 있는지 조사하기
2. phase event log를 task runtime에 추가할지 결정
3. `cmux` 운영 플레이북 작성
4. `money_track` 예시를 현재 구조에 맞춰 더 엄밀하게 갱신하기
5. legacy SDD prototype에 있는 `/runtime` 스킬은 이름과 목적이 맞지 않는다. 필요하면 `moondex` 스킬로 재설계하기

## 실패하거나 주의가 필요한 점

### `codex exec` 테스트를 아키텍처 검증으로 착각하면 안 됨
- **문제**: `codex exec`로 task-planner를 실행해 본 적이 있는데, 이건 메인 오케스트레이터 내부의 하위 역할 호출 테스트가 아니다.
- **원인**: `codex exec`는 새 top-level Codex 프로세스를 띄우는 방식이라, 사용자가 원한 Claude식 subagent 감각과 다르다.
- **대응**: `codex exec`는 공식 skills/agents 런타임 인식 smoke test 용도로만 본다. 실제 아키텍처는 메인 오케스트레이터가 planner 역할 agent를 호출하는 구조로 본다.

### planning layer와 execution layer를 섞지 말 것
- **문제**: 처음에는 `task-planner`와 implementer를 같이 spawn하는 방향도 논의됐다.
- **원인**: task set 전체를 병렬로 처리하는 관점과 같은 task 내부 순서를 혼동했다.
- **대응**: 같은 task에서는 항상 `task -> plan -> wave approval -> implement` 순서를 지킨다. task set 전체로는 planning과 execution이 병렬일 수 있다.

### Moondex 검증과 product 구현을 섞지 말 것
- **문제**: `money_track`를 실제로 고치고 테스트를 통과시키는 쪽으로 판단 기준이 이동하면서, 원래 검증하려던 Moondex 운영 모델 검증이 흐려졌다.
- **원인**: 빠른 확인이 쉬운 `spawn_agent` 중심 흐름과 직접 구현/테스트가, `cmux` 터미널 기반 멀티에이전트 루프보다 실행이 편했기 때문이다.
- **대응**:
  - Moondex 검증의 1차 목표는 product fix가 아니라 운영 모델 검증이다.
  - Moondex 검증 모드에서는 먼저 `cmux` 기준의 orchestrator / implementer / reviewer / test 작업면을 만든다.
  - implementer와 reviewer의 왕복 루프가 실제로 돌기 전에는 “검증 완료”로 보지 않는다.
  - `spawn_agent`는 보조 수단일 뿐 기본 검증 경로가 아니다.
  - product code 수정은 Moondex 루프 검증의 부산물로만 다룬다.

### 편의상 `spawn_agent`로 단순화하지 말 것
- **문제**: implementer와 reviewer를 논리적으로만 분리하고, 실제 터미널 운영 레이어는 관찰용으로만 사용한 적이 있다.
- **원인**: `spawn_agent`가 빠르고 제어하기 쉬워서, 원래 의도한 터미널 기반 멀티에이전트 검증을 대체해 버렸다.
- **대응**:
  - Moondex runtime 자체의 기본 모드는 `cmux` 터미널 루프다.
  - 최소한 `orchestrator`, `implementer`, `reviewer`, 필요 시 `test` pane을 분리한다.
  - 각 role의 상태 전달과 재작업은 가능하면 해당 작업면 기준으로 관찰되고 기록돼야 한다.
  - `spawn_agent`는 Moondex 표준 runtime 경로로 쓰지 않는다.

### `oh-my-codex`의 핵심을 tmux 자체로 오해하지 말 것
- **문제**: `oh-my-codex`를 참고하면서 tmux split/send/capture만 가져오면 runtime 핵심을 놓친다.
- **원인**: `$team`의 안정성은 pane 조작보다 `.omx/state/team/...`, worker inbox/mailbox, task claim, JSON API mutation, lifecycle evidence에 있다.
- **대응**:
  - 이 저장소에서는 tmux 명령을 `cmux` 명령으로 번역하되, mutation source of truth는 문서/상태 파일/API로 둔다.
  - `cmux send`는 dispatch 성공 근거가 아니라 wake-up trigger로만 본다.
  - `moondex ... --json` API는 `omx team api ... --json`과 같은 machine-readable mutation 경계를 가져야 한다.

### `money_track` integration_test 존재 여부 가정이 stale해짐
- **문제**: 이전 문서에서는 `integration_test/`가 없다고 기록했는데, 실제로는 `money_track/integration_test/`와 여러 scenario 파일이 존재했다.
- **원인**: 초기 리뷰 시점의 관찰과 이후 코드 생성/환경 차이를 제대로 다시 동기화하지 않았다.
- **대응**:
  - 다음 작업에서는 `T-11` 관련 plan/README/execution review 문서에서 이 가정을 수정한다.
  - 특히 `scenario_6_settings_reset_onboarding`를 T-11 slice 후보로 반영하는 것이 적절하다.

### task 수준 병렬성은 provisional이다
- **문제**: task 단계에서는 병렬 가능해 보여도 plan 단계에서 shared contract, 테스트 인프라, 동일 파일 수정 때문에 직렬로 강등될 수 있다.
- **원인**: task 정보는 거칠고, 실제 충돌은 plan에서 드러난다.
- **대응**: 최종 병렬성은 `plan` 기준으로 `wave-dispatcher` 단계에서 확정한다. `validated-ready` 전에는 구현 시작 금지다.

### 상세 상태 머신은 의도적으로 유지
- **문제**: 상태값이 많아 보일 수 있다.
- **원인**: 사용자 경험상 상태를 단순화하면 중간 추적이 어려웠다.
- **대응**: 현재는 아래 상태를 유지하는 쪽으로 합의됐다.
  - `draft`
  - `planning`
  - `planned`
  - `wave-ready`
  - `validated-ready`
  - `implementing`
  - `reviewing`
  - `done`
  - `blocked`

### 저장소는 현재 git repo가 아님
- **문제**: `git status`, `git log`가 실패했다.
- **원인**: `/Users/moon/Workspace/moondex`에 `.git`이 없다.
- **대응**: handoff와 추적은 현재 문서 기준으로 한다. git 기반 상태 추적을 전제로 생각하지 말 것.

## 환경 정보

```text
OS: macOS (세부 버전 미확인)
Runtime: Python 3.12.3, Node.js v18.16.0, Rust 1.94.0
주요 도구: Codex custom agents, Codex skills, cmux skill, moondex Rust CLI
프로젝트 경로: /Users/moon/Workspace/moondex
Git: 현재 디렉터리는 git repository 아님
```

## 다음 에이전트가 해야 할 일

1. **이 파일을 읽는다**.
2. **`docs/execution/cmux-runtime-alignment.md`를 읽는다**.
3. **`docs/execution/multi-agent-orchestration.md`를 읽는다**.
4. **`docs/executor-direction.md`와 `docs/planning/planning-workflow.md`를 읽어 현재 합의와 충돌이 없는지 확인한다**.
5. **`docs/execution/WORK_TRACKER.md`에서 W-01부터 W-13 완료 상태와 W-14+ 후보를 확인한다**.
6. **필요하면 `moondex` 스킬을 설계한다**.
7. **T-11 전체가 아니라 `scenario_6_settings_reset_onboarding`를 T-11 slice로 잡아, terminal-based implementer/reviewer/test loop를 다시 시도한다**.
