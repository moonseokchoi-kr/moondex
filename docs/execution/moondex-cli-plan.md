# Moondex CLI Plan

`moondex`는 Codex agent team을 위한 state-first runtime CLI다.

목표는 `task/plan/wave` 상태, role dispatch, inbox/mailbox, claim/lease, `cmux` surface trigger를 하나의 안정적인 runtime 경계로 묶는 것이다.

## Goal

MVP는 아래 흐름을 안정화한다.

```text
validated-ready task
-> role inbox 작성
-> task claim/lease 기록
-> dispatch request 기록
-> cmux surface에 짧은 trigger 전송
-> worker ACK/결과를 state로 확인
-> guarded transition
```

`cmux send` 성공은 dispatch 성공이 아니다. state evidence만 runtime truth다.

## Non-Goals

MVP에서 하지 않는다.

- worktree 자동 생성
- git merge/cherry-pick integration
- provider routing
- HUD
- native hook auto-discovery
- full `oh-my-codex` clone
- reviewer 판단 자동화

## State Root

기본 state root:

```text
.moondex/state/
```

초기 구조:

```text
.moondex/state/
  config.json
  tasks/
    <task-id>.json
  roles/
    <role-id>/
      identity.json
      inbox.md
      status.json
  mailbox/
    orchestrator.json
  dispatch/
    requests.json
  evidence/
    index.json
    <evidence-id>.txt
  hooks/
    warnings.json
  events.jsonl
```

## CLI Surface

MVP command:

```bash
moondex init
moondex status --json
moondex dispatch <role> <task-id> --json
moondex role register-current <role-id> --json
moondex cmux identify --json
moondex api create-task --input '<json>' --json
moondex api read-task --input '<json>' --json
moondex api list-tasks --json
moondex api claim-task --input '<json>' --json
moondex api transition-task --input '<json>' --json
moondex api release-task --input '<json>' --json
moondex api write-role-identity --input '<json>' --json
moondex api write-role-status --input '<json>' --json
moondex api ack-dispatch --input '<json>' --json
moondex api retry-dispatch --input '<json>' --json
moondex api list-dispatch --json
moondex api read-dispatch --input '<json>' --json
moondex api list-events --input '{"task_id":"T-01","kind":"phase_advanced","limit":20}' --json
moondex api inspect-hooks --json
moondex api write-mailbox --input '<json>' --json
moondex api read-mailbox --input '<json>' --json
moondex api mark-mailbox-read --input '<json>' --json
moondex api consume-mailbox --input '<json>' --json
moondex api consume-mailbox-for-task --input '<json>' --json
moondex api validate-role-transfer --input '<json>' --json
moondex api validate-readiness --input '<json>' --json
moondex api next-action --json
moondex api orchestrator-step --input '<json>' --json
moondex api orchestrator-loop --input '<json>' --json
moondex api list-evidence --json
moondex api list-stale-roles --input '<json>' --json
moondex api audit-state --json
moondex api repair-state --input '<json>' --json
moondex api archive-state --input '<json>' --json
moondex cmux capture --surface <surface> --lines 120 --json
```

## JSON Envelope

All machine-readable commands return:

```json
{
  "schema_version": "1.0",
  "ok": true,
  "operation": "claim-task",
  "data": {}
}
```

Failure:

```json
{
  "schema_version": "1.0",
  "ok": false,
  "operation": "claim-task",
  "error": {
    "code": "claim_conflict",
    "message": "task is already claimed"
  }
}
```

## Task Runtime State

MVP task status:

- `pending`
- `blocked`
- `in_progress`
- `completed`
- `failed`

The planning-layer states from `docs/execution/multi-agent-orchestration.md` remain source-of-truth for planning. `moondex` MVP owns the execution-runtime claim lifecycle.

Task records also carry a runtime `phase`:

- `implementation`
- `code_review`
- `compliance_review`
- `testing`
- `done`

`role` means the currently dispatchable role for the active phase, not the permanent role for the logical task. This lets one `task_id` move through implementer, reviewer, compliance, and tester passes without creating artificial review-only tasks.

Claim fields:

- `owner`
- `token`
- `leased_until`
- `version`

Allowed runtime transitions:

- claim: `pending|blocked -> in_progress`
- terminal: `in_progress -> completed|failed`
- release: `in_progress -> pending`

Phase transfer happens when the orchestrator consumes canonical mailbox output:

- implementer `result` on a completed implementation phase: same task requeues as `pending`, `phase=code_review`, `role=code-reviewer`
- code-reviewer `review_approved` with `compliance_review_required: true`: same task requeues as `pending`, `phase=compliance_review`, `role=compliance-reviewer`
- code-reviewer `review_approved` with `tester_required: true`: same task requeues as `pending`, `phase=testing`, `role=tester`
- code-reviewer `review_approved` with no extra phase required: task becomes `completed`, `phase=done`
- compliance approval can requeue to tester or mark done
- tester `result` marks done
- `blocked` mailbox output marks the task `blocked`

## Phase Event Log

`.moondex/state/events.jsonl` is the append-only runtime audit stream. It is not archived by `archive-state`; active runtime history stays at the active state root even when completed tasks, consumed mailbox records, delivered dispatch requests, or old hook warnings move under `.moondex/state/archive/`.

Event kinds:

- `task_created`
- `task_claimed`
- `task_released`
- `task_transitioned`
- `phase_advanced`
- `mailbox_consumed`
- `dispatch_created`
- `dispatch_marked`
- `archive_created`

Every event carries `event_id`, `kind`, optional task/role/message/dispatch references, optional `from_phase`/`to_phase`, optional `from_status`/`to_status`, `created_at`, and structured `detail`.

Query recent runtime history:

```bash
moondex api list-events --input '{"task_id":"T-01"}' --json
moondex api list-events --input '{"kind":"phase_advanced","limit":10}' --json
moondex api list-events --json
```

`audit-state` reports malformed event log lines as `event_issues`. Repair does not rewrite `events.jsonl`; malformed lines require operator review because the file is the runtime audit trail.

## Dispatch State

Dispatch request status:

- `pending`
- `notified`
- `delivered`
- `failed`

MVP dispatch creates a request and attempts direct `cmux` trigger if the role identity has `surface_ref`.

If no surface exists, the dispatch request remains `pending` with reason `surface_ref_missing`.

Before `cmux send`, `moondex` validates that the target surface exists in `cmux tree --json`. This is required because `cmux` may fall back to the current surface for invalid targets. `moondex` also rejects a send result if the returned `OK surface:<id>` does not match the requested surface.

The trigger text is shell-safe and newline-terminated:

```text
# moondex: read your inbox for task <task-id>
```

This avoids leaving partial text in a terminal prompt where the next command could be concatenated.

`ack-dispatch` is the worker-side proof that the inbox was actually read. It transitions a request to `delivered`. `notified` only means the wake-up transport was attempted successfully.

`retry-dispatch` retries an existing non-delivered dispatch request using the same `request_id`. It re-resolves the latest role identity surface before sending.

Retry policy is limit-only. A request can be retried at most 3 times. Once `retry_count` is already 3, `retry-dispatch` does not send again; it leaves the request `failed`, records `last_reason` as `retry_exhausted`, and returns an error. Initial dispatch is not counted as a retry.

Retry attempts are recorded on the dispatch request:

- `retry_count`: number of retry attempts for this request.
- `retry_history`: ordered retry attempt records with `attempted_at`, `surface_ref`, `outcome`, and `reason`.

## Role Status And Mailbox

Role status is stored at:

```text
.moondex/state/roles/<role-id>/status.json
```

Workers update this with `write-role-status` for heartbeat-style progress reporting.

`role register-current` shells out to `cmux identify`, prefers `caller.surface_ref`, and writes the role identity automatically. This removes the manual `surface_ref` copy step during real cmux operation.

Mailbox messages are stored per recipient:

```text
.moondex/state/mailbox/<role-id>.json
```

If `to_role` is omitted, `write-mailbox` writes to `orchestrator`.

Mailbox lifecycle fields:

- `read_at`: set by `mark-mailbox-read`.
- `consumed_at`: set by `consume-mailbox`.

`read-mailbox` accepts optional `task_id`, `unread_only`, and `unconsumed_only` filters.

`consume-mailbox-for-task` consumes the first unconsumed message for a recipient and task, optionally narrowed by `from_role` and `kind`. This avoids manual message id copying in reviewer/orchestrator loops.

Mailbox `kind` is restricted to:

- `result`
- `blocked`
- `question`
- `review_approved`
- `review_changes_requested`
- `status`

Mailbox `body` is stored as a string, but the string must encode a JSON object. New writes validate the object by `kind`:

- `result`: `summary`, `changed_files`, and either non-empty `tests` or `not_run_reason`
- `blocked`: `reason`, `needs`
- `question`: `question`, `decision_needed`
- `review_approved`: `summary`, non-empty `checks`
- `review_changes_requested`: `summary`, non-empty `changes`, and `severity` of `low`, `medium`, `high`, or `blocking`
- `status`: `state`, `summary`

Example:

```bash
moondex api write-mailbox --input '{"from_role":"implementer","kind":"result","task_id":"T-01","body":"{\"summary\":\"done\",\"changed_files\":[\"crates/moondex/src/fs_state.rs\"],\"tests\":[\"cargo test -p moondex\"]}"}' --json
```

## Role Transfer Validation

`validate-role-transfer` checks planning payloads, role handoff payloads, and mailbox output payloads without mutating runtime state.

```bash
moondex api validate-role-transfer --input '{"from_role":"implementer","kind":"result","task_id":"T-01","body":"{\"summary\":\"done\",\"changed_files\":[],\"tests\":[\"cargo test -p moondex\"]}"}' --json
```

Planning payloads use `contract_type`: `task_planner_input`, `task_planner_output`, `wave_dispatcher_input`, `wave_dispatcher_output`, and `tester_input`.

The Codex hook wrapper lives at:

```bash
.codex/hooks/validate-role-transfer.sh
```

The wrapper exits non-zero when `valid` is false. Warnings keep `valid: true`.

`write-mailbox` runs the same role output validation for canonical roles before it writes durable state. Invalid role/kind combinations and missing `task_id` are rejected. Warning-only outputs are written and their warnings are recorded in `.moondex/state/hooks/warnings.json`.

`dispatch` also applies lifecycle guards before it writes a request:

- terminal task cannot be dispatched
- task role mismatch cannot be dispatched
- a task already claimed by another owner cannot be dispatched

If a dispatch target has no registered `surface_ref`, the request still succeeds as `pending`, and a hook warning records `surface_ref_missing`.

Dispatch writes a structured role inbox to `.moondex/state/roles/<role-id>/inbox.md`. The inbox contains:

- task id, phase, subject, description, version, and active role
- recent previous mailbox outputs for the same `task_id` that are relevant to the target role
- an `expected_output` contract with allowed mailbox kinds and body shape
- a machine payload JSON block for automation

## Readiness Validation

`validate-readiness` executes the planning quality gate:

```bash
moondex api validate-readiness --input '{"task":{"task_id":"T-01","subject":"Add gate","description":"Implement readiness validation."},"plan":{"plan_id":"P-01","task_id":"T-01","objective":"Add validator.","scope_paths":["crates/moondex/src/fs_state.rs"],"acceptance_criteria":["complete payload returns READY"],"verification_commands":["cargo test -p moondex"],"ownership":["crates/moondex/src/fs_state.rs"]}}' --json
```

Decision values:

- `READY`
- `REVISION_REQUIRED`
- `BLOCKED`

The Codex hook wrapper is:

```bash
.codex/hooks/validate-readiness.sh
```

The wrapper exits `0` only for `READY`.

## Hook Inspection

`inspect-hooks` reports the repo-local `.codex/hooks` contract:

```bash
moondex api inspect-hooks --json
```

The response lists hook `name`, `path`, executable bit, target operation, smoke command, and status. Current repo-local validators are:

- `.codex/hooks/validate-role-transfer.sh`
- `.codex/hooks/validate-readiness.sh`

This command does not assume private Codex lifecycle behavior. Until native hook auto-discovery is verified, operators should run these validators explicitly before or after `orchestrator-step` as described in [codex-hook-auto-discovery.md](/Users/moon/Workspace/moondex/docs/execution/codex-hook-auto-discovery.md).

## Next Action

`next-action` is advisory and non-mutating. It reads runtime state and returns one recommended state-first action.

```bash
moondex api next-action --json
```

Priority:

1. repair audit issues
2. review hook warnings
3. consume orchestrator mailbox
4. wait for dispatch ACK
5. dispatch pending task role
6. wait

`orchestrator-step` applies exactly one safe next action when `apply` is true:

```bash
moondex api orchestrator-step --input '{"apply":true}' --json
```

Applied actions are limited to:

- `consume_mailbox`
- `dispatch_implementer`
- `dispatch_code_reviewer`
- `dispatch_compliance_reviewer`
- `dispatch_tester`
- `repair_state` when `allow_repair` is true

It intentionally does not auto-ACK dispatch requests, auto-review hook warnings, or make reviewer/tester judgments.

`orchestrator-loop` repeats bounded steps:

```bash
moondex api orchestrator-loop --input '{"apply":true,"max_steps":10}' --json
```

The loop stops on wait, ACK wait, hook warning review, disabled repair, repeated-action guard, or `max_steps`.

## Stale Roles

`moondex api list-stale-roles --input '{"older_than_seconds":60}' --json` reports role status entries whose `updated_at` is older than the threshold.

## Audit And Repair

`audit-state` reports mailbox issues, dispatch issues, and hook warnings separately. Hook warnings do not increment mailbox or dispatch issue counts.

`repair-state` fixes legacy invalid mailbox and dispatch state. Hook warnings are reviewed by an operator; they are not repaired automatically.

## Worktree Isolation

Moondex v1 supports three documented isolation modes:

- `no_worktree`: current documentation/runtime workspace mode
- `external_worktree`: target product repository provides git worktrees
- `future_managed_worktree`: planned future Moondex-managed worktree mode

`moondex` does not require git worktrees while it is not itself a git repository. Worktree isolation belongs to the target product repository execution layer. cmux role surfaces remain required for visible role separation.

## Runtime Retention

Must keep active tasks, in-progress claims, pending/notified dispatch requests, unread or unconsumed mailbox messages, current role identity/status, and audit-relevant invalid state until repaired.

Manual archive candidates include completed tasks older than an operator-chosen cutoff, consumed mailbox messages linked to completed tasks, delivered dispatch requests linked to completed tasks, reviewed hook warnings, and evidence files once referenced elsewhere.

Do not silently delete failed dispatch requests, blocked tasks, `retry_exhausted` records, or repair/audit evidence.

Implemented archive command:

```bash
moondex api archive-state --input '{"apply":false,"older_than_seconds":2592000}' --json
```

Dry-run reports archive candidates. Apply writes records under `.moondex/state/archive/<archive-id>/` and prunes only eligible active records:

- completed tasks older than the threshold
- consumed mailbox messages older than the threshold
- delivered dispatch requests older than the threshold
- hook warnings only when `include_hook_warnings` is true

Blocked tasks, pending/notified/failed dispatch requests, and unconsumed mailbox messages remain active.

`events.jsonl` remains active and is never selected as an archive candidate. Use `list-events` before and after archive operations when reconstructing runtime history.

`audit-state` reports legacy invalid state entries:

- mailbox messages with invalid `kind`
- mailbox messages whose `body` is not a valid JSON object for their `kind`
- dispatch requests with unsafe trigger text
- dispatch requests marked `notified` with a known invalid surface fallback

`repair-state --input '{"apply":false}'` runs a dry-run. `repair-state --input '{"apply":true}'` applies safe repairs.

## Evidence Capture

`moondex cmux capture --surface <surface> --lines <N>` captures terminal output with `cmux capture-pane`, stores the text file under `.moondex/state/evidence/`, and appends metadata to `evidence/index.json`.

## Rust Modules

Initial crate layout:

```text
crates/moondex/
  src/main.rs
  src/cli.rs
  src/envelope.rs
  src/fs_state.rs
  src/model.rs
  src/cmux.rs
```

## Acceptance Criteria

- `moondex init` creates `.moondex/state`.
- `moondex api create-task` writes a task.
- `moondex api claim-task` requires expected version and returns a claim token.
- `moondex api transition-task` requires the claim token.
- `moondex dispatch <role> <task-id>` writes role inbox and dispatch request.
- `moondex api ack-dispatch` marks a request `delivered` only when the target role matches.
- `moondex api retry-dispatch` retries an existing non-delivered request with latest role identity.
- `moondex api write-role-status` writes role heartbeat/progress state.
- `moondex api write-mailbox` records worker output to a durable mailbox.
- `moondex api mark-mailbox-read` and `consume-mailbox` track mailbox processing without deleting messages.
- `moondex role register-current` registers the current cmux caller surface for a role.
- `moondex api list-stale-roles` reports role heartbeat entries older than a threshold.
- `moondex api audit-state` and `repair-state` detect and fix legacy invalid state.
- `moondex api next-action` recommends one non-mutating next action.
- `moondex api orchestrator-step` and `orchestrator-loop` apply bounded safe actions from `next-action`.
- `moondex api archive-state` dry-runs or applies selective runtime archival.
- `moondex cmux capture` stores terminal evidence under `.moondex/state/evidence`.
- `moondex cmux identify --json` shells out to `cmux identify`.
- Unit tests cover claim conflict, invalid transition, release requeue, dispatch without surface, ACK, role status, mailbox lifecycle, and evidence indexing.

## Verification Commands

Minimum:

```bash
cargo test -p moondex
```

Manual cmux smoke:

```bash
cargo run -p moondex -- init
cargo run -p moondex -- role register-current orchestrator --json
cargo run -p moondex -- cmux identify --json
cargo run -p moondex -- cmux capture --surface surface:2 --lines 20 --json
```
