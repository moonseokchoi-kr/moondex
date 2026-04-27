# cmux Runtime Alignment

이 문서는 `oh-my-codex`의 `$team` runtime을 참고해 `moondex`의 `cmux` 기반 실행 모델로 번역할 규칙을 정리한다.

## Source Reference

주요 참고 대상:

- `oh-my-codex` repository: `https://github.com/Yeachan-Heo/oh-my-codex`
- `$team` skill: `https://github.com/Yeachan-Heo/oh-my-codex/blob/main/skills/team/SKILL.md`
- team mutation contract: `https://github.com/Yeachan-Heo/oh-my-codex/blob/main/docs/interop-team-mutation-contract.md`
- state model: `https://github.com/Yeachan-Heo/oh-my-codex/blob/main/docs/STATE_MODEL.md`

## What To Copy Conceptually

`oh-my-codex`의 핵심은 "tmux pane을 띄운다"가 아니라, durable state와 worker lifecycle을 먼저 두고 terminal pane은 실행 작업면으로만 사용하는 것이다.

가져올 원칙:

- worker는 독립 CLI 세션으로 실행된다.
- leader/orchestrator는 기존 pane에 남아 전체 상태를 관리한다.
- task dispatch는 terminal keystroke가 아니라 state mutation과 inbox/mailbox delivery가 기준이다.
- terminal send는 worker를 깨우는 trigger 또는 fallback이지 primary mutation path가 아니다.
- task claim과 terminal transition은 version/claim token 같은 안전장치를 가져야 한다.
- startup, progress, shutdown은 pane 존재만이 아니라 state evidence로 검증한다.
- worker state root는 leader workspace 기준으로 공유돼야 한다.

## Detailed OMX Team Process

`oh-my-codex`의 `$team` runtime은 대략 아래 순서로 동작한다.

1. CLI가 `omx team [N:agent-type] "<task>"`를 파싱한다.
2. team name을 안전한 slug로 정규화한다.
3. 기존 active team/state 충돌을 검사한다.
4. worktree mode를 결정한다.
5. `.omx/state/team/<team>/` 아래 durable state를 초기화한다.
6. task 파일을 생성한다.
7. team-scoped worker instructions를 만든다.
8. 각 worker별 role, model/reasoning, CLI provider를 결정한다.
9. 각 worker별 `inbox.md`, role instruction, identity payload를 준비한다.
10. tmux split-pane 또는 prompt-mode process로 worker runtime을 만든다.
11. worker identity, pane id, PID, worktree metadata를 state에 기록한다.
12. worker readiness를 `capture-pane` 기반으로 확인한다.
13. inbox를 state에 쓰고 dispatch request를 enqueue한다.
14. hook/preferred dispatch가 가능하면 hook 경로로 깨우고, 실패하면 direct transport로 fallback한다.
15. worker는 task를 claim하고, 완료 또는 실패 시 claim token으로 terminal transition을 수행한다.
16. monitor loop가 task count, heartbeat, mailbox, events, phase를 읽어 team 상태를 갱신한다.
17. 모든 task가 terminal 상태가 된 뒤에만 shutdown/cleanup을 허용한다.

중요한 점은 `send-keys`가 작업 할당 자체가 아니라는 것이다. 작업 할당은 state/inbox/dispatch request에 남고, `send-keys`는 worker에게 "읽고 진행하라"고 깨우는 전송 수단이다.

## OMX State Model To Preserve

OMX의 state root는 `<leader-cwd>/.omx/state`이며 team state는 아래 형태를 가진다.

```text
.omx/state/team/<team>/
  config.json
  manifest.v2.json
  phase.json
  tasks/
    task-<id>.json
  workers/
    worker-<n>/
      identity.json
      inbox.md
      heartbeat.json
      status.json
  mailbox/
    leader-fixed.json
    worker-<n>.json
  dispatch/
    requests.json
  events.jsonl
  monitor-snapshot.json
  shutdown/
```

`moondex`의 `moondex` runtime state root는 `.moondex/state`로 둔다. 아래 개념은 그대로 유지해야 한다.

- `config`: runtime topology와 worker metadata
- `manifest`: policy, governance, permissions snapshot
- `tasks`: claim-safe task lifecycle
- `workers`: identity, inbox, heartbeat, status
- `mailbox`: role 간 durable message
- `dispatch`: trigger delivery request와 delivery state
- `events`: wakeable/audit event stream
- `monitor snapshot`: leader가 판단할 수 있는 최근 runtime view

## Claim-Safe Task Lifecycle

OMX의 team task status는 단순하다.

- `pending`
- `blocked`
- `in_progress`
- `completed`
- `failed`

허용 transition도 의도적으로 좁다.

- `pending` 또는 claim 가능한 `blocked` task를 worker가 claim하면 `in_progress`
- `in_progress -> completed`
- `in_progress -> failed`
- `release-task`는 완료가 아니라 requeue다. 결과적으로 task를 `pending`으로 되돌린다.

claim은 아래를 포함한다.

- `owner`
- `token`
- `leased_until`
- optimistic `version`

이 구조는 `moondex`의 상세 상태 머신과 그대로 같지는 않다. 따라서 번역 시에는 `task/plan/wave` 상태는 Moondex 상태 머신을 유지하고, execution dispatch 구간에는 OMX식 claim token과 lease를 붙이는 것이 맞다.

## Dispatch Request Lifecycle

OMX dispatch request status:

- `pending`
- `notified`
- `delivered`
- `failed`

의미:

- `pending`: state에 dispatch request가 생성됐지만 worker가 아직 깨워졌다는 증거가 없다.
- `notified`: hook 또는 direct transport가 worker를 깨운 것으로 확인됐다.
- `delivered`: worker가 mailbox/inbox를 실제로 처리했다고 표시했다.
- `failed`: delivery path가 실패했다.

이 구분은 `cmux send` 성공 여부보다 중요하다. `cmux send`가 성공해도 request는 `delivered`가 아닐 수 있다.

## cmux Compatibility Command Mapping

cmux는 별도 tmux binary를 내장하지 않지만, tmux-compatible command layer를 제공한다. 이 Moondex에서는 raw `tmux` 호출을 만들지 말고 이 호환 command surface를 사용한다.

| OMX tmux call | cmux-compatible call | Notes |
| --- | --- | --- |
| `tmux display-message -p '#S:#I #{pane_id}'` | `cmux identify` or `cmux display-message -p ...` | cmux native refs가 더 안정적이다. |
| `tmux list-panes -F ...` | `cmux list-panes`, `cmux list-pane-surfaces`, or `cmux capture-pane` | pane id와 surface id를 분리해 저장해야 한다. |
| `tmux split-window -h ...` | `cmux new-split right` | worker surface 생성에 사용한다. |
| `tmux split-window -v ...` | `cmux new-split down` or `cmux new-split right` after focus | stacked worker layout 구현에 필요하다. |
| `tmux capture-pane -p -S -80` | `cmux capture-pane --surface <surface> --scrollback --lines 80` | readiness와 post-submit verification에 사용한다. |
| `tmux send-keys -t <target> -l -- <text>` | `cmux send --surface <surface> "<text>"` | literal trigger text 전송. |
| `tmux send-keys -t <target> C-m` | `cmux send-key --surface <surface> C-m` | submit key. `cmux send "<text>\n"`는 단순 케이스에만 사용한다. |
| `tmux send-keys -t <target> C-c` | `cmux send-key --surface <surface> C-c` | interrupt fallback. |
| `tmux send-keys -t <target> C-u` | `cmux send-key --surface <surface> C-u` | line clear fallback. |
| `tmux kill-pane -t <pane>` | `cmux close-surface --surface <surface>` or close pane equivalent | leader/hud surface 보호가 필요하다. |
| `tmux resize-pane ...` | `cmux resize-pane ...` | cmux help에 호환 command 존재. |
| `tmux wait-for` | `cmux wait-for` | barrier가 필요할 때 사용 가능. |

핵심 adapter handle은 tmux의 `%pane`이 아니라 cmux의 `surface:<n>` 또는 UUID여야 한다.

## Minimal cmux Team Adapter

OMX의 `crates/omx-mux`는 mux operation을 아래 여섯 개로 추상화한다.

- `resolve-target`
- `send-input`
- `capture-tail`
- `inspect-liveness`
- `attach`
- `detach`

`moondex`도 처음부터 전체 `tmux-session.ts`를 복제하기보다, 이 operation set에 맞는 `CmuxAdapter`를 정의하는 편이 낫다.

권장 `CmuxAdapter` operation:

- `resolve-target`: role id 또는 stored surface ref를 cmux surface로 해석한다.
- `send-input`: literal text를 `cmux send`로 보내고 submit policy에 따라 `cmux send-key C-m`을 수행한다.
- `capture-tail`: `cmux capture-pane --scrollback --lines N`을 수행한다.
- `inspect-liveness`: `cmux surface-health` 또는 `cmux list-pane-surfaces`로 surface 존재와 health를 확인한다.
- `attach`: `cmux focus-pane` 또는 `cmux select-workspace`로 operator focus를 이동한다.
- `detach`: cmux에서는 no-op 또는 focus restoration으로 둔다.

이 adapter의 반환값은 cmux raw output이 아니라 normalized outcome이어야 한다.

## What Must Not Be Ported Blindly

아래는 그대로 복제하면 안 된다.

- tmux `%pane` id를 semantic identity로 쓰는 것
- `TMUX`, `TMUX_PANE` env 존재를 runtime precondition으로 두는 것
- worktree-first 가정을 이 documentation repo에 강제하는 것
- `send-keys` 성공을 dispatch 성공으로 보는 것
- worker shutdown 중 leader pane을 같이 죽일 수 있는 cleanup logic
- prompt/provider별 key-submit retry를 state 없이 직접 반복하는 것
- worktree-first isolation을 git repository가 아닌 documentation/runtime repo에 강제하는 것

cmux에서는 `workspace`, `pane`, `surface` 계층이 있으므로 semantic owner는 role/task state에 두고, runtime handle은 `surface_ref`로 저장해야 한다.

## Worktree Isolation Modes

Moondex v1 documents three modes:

- `no_worktree`: current `moondex` mode. One workspace owns `.moondex/state`; role separation comes from cmux surfaces.
- `external_worktree`: target product repository provides git worktrees. The orchestrator can dispatch roles into product worktree roots, while `.moondex/state` remains the runtime truth.
- `future_managed_worktree`: future Moondex-managed worktree creation and cleanup. This is out of scope for the current runtime.

`moondex` cannot require git worktrees while it is not a git repository. Worktree metadata such as `workspace_root`, `worktree_branch`, and `isolation_mode` may be documented in role identity handoffs, but Rust role identity fields are not extended in this wave.

## Runtime Retention And Archive

Keep active tasks, in-progress claims, pending/notified dispatch requests, unread or unconsumed mailbox messages, current role identity/status, and invalid state needed by `audit-state`/`repair-state`.

Manual archive candidates are completed tasks older than an operator-selected cutoff, consumed mailbox messages linked to completed tasks, delivered dispatch requests linked to completed tasks, reviewed hook warnings, and evidence files once referenced in a handoff or external artifact.

Do not silently delete failed dispatch requests, blocked tasks, `retry_exhausted` records, or audit/repair evidence.

Future command shape:

```bash
moondex api archive-state --input '{"apply":false,"older_than_seconds":2592000}' --json
```

## cmux Translation

`oh-my-codex`는 tmux를 사용하지만 이 저장소의 runtime target은 `cmux`다.

| OMX / tmux concept | moondex / cmux translation |
| --- | --- |
| leader pane | orchestrator surface |
| worker pane | role surface |
| `tmux split-window` | `cmux new-split` or `cmux new-pane` |
| `tmux capture-pane` | `cmux capture-pane` or `cmux read-screen` |
| `tmux send-keys` | `cmux send` |
| `.omx/state/team/<team>/...` | `.moondex/state/...` |
| worker `inbox.md` | role assignment artifact |
| leader mailbox | role output / event artifact |
| `omx team api ... --json` | `moondex api ... --json` |
| `claim-task` | lease-safe task claim |
| `transition-task` | guarded task status transition |

## Runtime Shape

Minimum runtime layout:

- `orchestrator` surface
- `task-planner` surface or pool when planning tasks are active
- `wave-dispatcher` surface when plan set is ready
- `implementer` surface or pool for `validated-ready` tasks
- `code-reviewer` surface
- `compliance-reviewer` surface only when required
- `tester` surface only for integration or E2E work

The orchestrator must keep source-of-truth state outside terminal history.

Suggested state root:

```text
.moondex/state/
  tasks/
    <task_id>.json
  plans/
    <plan_id>.md
  waves/
    <wave_id>.md
  roles/
    <role_id>/
      identity.json
      inbox.md
      heartbeat.json
      status.json
  mailbox/
    orchestrator.json
  events.jsonl
```

This path is provisional. The important point is the state contract, not the exact folder name.

## Dispatch Rules

Primary dispatch path:

1. Orchestrator validates task status and required contract.
2. Orchestrator writes a role assignment artifact.
3. Orchestrator records ownership or lease.
4. Orchestrator sends a short `cmux send` trigger to the target surface.
5. Target role ACKs through a durable output artifact.
6. Orchestrator verifies state evidence before status transition.

Do not treat `cmux send` success as dispatch success. It only proves a trigger was sent.

## Task Claim And Transition Rules

Future runtime should support claim-safe operations equivalent to:

- read task
- claim task with expected version
- transition task status with claim token
- release claim for requeue
- append event
- send role message
- read role status
- read heartbeat

This maps to the existing state machine in `docs/execution/multi-agent-orchestration.md`.

Recommended guarded transitions:

- `draft -> planning`: planner claim required
- `planning -> planned`: planner claim token required
- `wave-ready -> validated-ready`: wave-dispatcher approval required
- `validated-ready -> implementing`: implementer claim required
- `implementing -> reviewing`: implementer output and verification evidence required
- `reviewing -> done`: reviewer approval evidence required
- `reviewing -> implementing`: review changes required evidence required

## Evidence Requirements

An execution run is not proven by "pane exists" or "command was sent".

Minimum evidence:

- layout: relevant `cmux` surfaces exist
- assignment: target role has a current inbox artifact
- ACK: target role acknowledged assignment
- claim: task owner and lease are recorded
- progress: heartbeat or status updates exist
- output: role output contract is written
- verification: command results are recorded
- review: reviewer output contract is written
- shutdown: no active claims remain before surfaces are cleaned up

## Differences From OMX

This repository is currently not a git repo. That changes one major OMX assumption.

- OMX can rely on git worktrees for worker isolation.
- `moondex` cannot currently require git worktrees in this repository.
- Worktree isolation should be treated as optional or external until this repo becomes a git repo.
- For product examples such as `money_track`, worktree support depends on that target repository, not this documentation repo.

## Immediate Next Work

1. Update `docs/execution/multi-agent-orchestration.md` so `cmux Operation Layer` uses the state-first dispatch model above.
2. Convert `docs/execution/role-transfer-contracts.md` from document-only contracts into payload-ready envelopes.
3. Define a minimal `moondex api ... --json` command surface inspired by `omx team api ... --json`.
4. Decide the state root path and file layout.
5. Run one small `cmux` validation loop with real orchestrator / implementer / reviewer surfaces.
