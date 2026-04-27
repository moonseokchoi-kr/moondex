# cmux Operations Playbook

This playbook is the repeatable operator path for Moondex execution on cmux surfaces.

The source of truth is `.moondex/state`, not what is visible on a cmux screen. cmux panes are transport and observation surfaces. Every important decision must be backed by task, dispatch, mailbox, evidence, hook warning, audit, or event state under `.moondex/state`.

## 1. Prepare Surfaces

Create one stable surface for the orchestrator and one for each active role:

- `orchestrator`
- `implementer`
- `code-reviewer`
- `compliance-reviewer`
- `tester`

In every role surface, enter the target repo and register the current surface:

```bash
moondex role register-current implementer --json
moondex role register-current code-reviewer --json
moondex role register-current compliance-reviewer --json
moondex role register-current tester --json
```

Confirm state, not the screen:

```bash
moondex status --json
moondex api list-stale-roles --input '{"older_than_seconds":900}' --json
```

If a role lacks `surface_ref`, dispatch can still create a pending request, but the operator must fix the role identity before expecting delivery.

## 2. Create And Dispatch Work

Create or confirm a task:

```bash
moondex api create-task --input '{"task_id":"T-01","subject":"Implement slice","description":"Executor-ready task details.","role":"implementer"}' --json
moondex api read-task --input '{"task_id":"T-01"}' --json
```

Run one orchestrator step or a bounded loop:

```bash
moondex api next-action --json
moondex api orchestrator-step --input '{"apply":true}' --json
moondex api orchestrator-loop --input '{"apply":true,"max_steps":10}' --json
```

The orchestrator loop applies state-first actions only. If it stops on `ack_dispatch_wait`, `review_hook_warnings`, `surface_ref_missing`, or `retry_exhausted`, resolve the state condition before continuing.

## 3. Worker ACK, Claim, Status

When a worker sees a dispatch in its inbox, it acknowledges the dispatch request:

```bash
moondex api ack-dispatch --input '{"request_id":"dispatch-implementer-123","role_id":"implementer"}' --json
```

Then it claims the task using the current task version:

```bash
moondex api read-task --input '{"task_id":"T-01"}' --json
moondex api claim-task --input '{"task_id":"T-01","worker":"implementer","expected_version":1}' --json
moondex api write-role-status --input '{"role_id":"implementer","state":"working","task_id":"T-01","message":"editing implementation"}' --json
```

When work completes:

```bash
moondex api transition-task --input '{"task_id":"T-01","from":"in_progress","to":"completed","claim_token":"<claim-token>","result":"implementation done","error":null}' --json
```

Report role output through mailbox state, not through screen text:

```bash
moondex api write-mailbox --input '{"from_role":"implementer","kind":"result","task_id":"T-01","body":"{\"summary\":\"done\",\"changed_files\":[\"crates/moondex/src/fs_state.rs\"],\"tests\":[\"cargo test -p moondex\"]}"}' --json
```

The orchestrator consumes the mailbox message and advances phase when the output contract allows it:

```bash
moondex api consume-mailbox-for-task --input '{"role_id":"orchestrator","task_id":"T-01","from_role":"implementer","kind":"result"}' --json
moondex api list-events --input '{"task_id":"T-01","kind":"phase_advanced"}' --json
```

Again, `.moondex/state` is the source of truth; a cmux pane may lag, scroll away, or show stale text.

## 4. Reviewer Payloads

Code reviewer approval that requires compliance:

```bash
moondex api write-mailbox --input '{"from_role":"code-reviewer","kind":"review_approved","task_id":"T-01","body":"{\"summary\":\"approved with compliance required\",\"checks\":[\"reviewed diff\"],\"compliance_review_required\":true,\"tester_required\":false,\"changed_files\":[\"docs/execution/moondex-cli-plan.md\"]}"}' --json
```

Code reviewer approval that requires tester:

```bash
moondex api write-mailbox --input '{"from_role":"code-reviewer","kind":"review_approved","task_id":"T-01","body":"{\"summary\":\"approved but needs test evidence\",\"checks\":[\"reviewed behavior\"],\"compliance_review_required\":false,\"tester_required\":true,\"changed_files\":[\"crates/moondex/src/fs_state.rs\"]}"}' --json
```

Compliance reviewer approval:

```bash
moondex api write-mailbox --input '{"from_role":"compliance-reviewer","kind":"review_approved","task_id":"T-01","body":"{\"summary\":\"contract impact accepted\",\"checks\":[\"checked docs and CLI contract\"],\"tester_required\":true}"}' --json
```

Tester result:

```bash
moondex api write-mailbox --input '{"from_role":"tester","kind":"result","task_id":"T-01","body":"{\"summary\":\"verification passed\",\"changed_files\":[],\"tests\":[\"cargo test -p moondex\",\"cargo build -p moondex\"]}"}' --json
```

Changes requested:

```bash
moondex api write-mailbox --input '{"from_role":"code-reviewer","kind":"review_changes_requested","task_id":"T-01","body":"{\"summary\":\"needs correction\",\"changes\":[\"Add event log coverage for malformed JSONL\"],\"severity\":\"high\"}"}' --json
```

Blocked:

```bash
moondex api write-mailbox --input '{"from_role":"tester","kind":"blocked","task_id":"T-01","body":"{\"reason\":\"test environment unavailable\",\"needs\":\"operator to restore toolchain\"}"}' --json
```

## 5. Common Stops

`ack_dispatch_wait`: a dispatch is pending or notified but not delivered. The worker should read `.moondex/state/roles/<role-id>/inbox.md`, then run `ack-dispatch`. If the role never saw the dispatch, inspect role identity and retry the dispatch.

`review_hook_warnings`: run `moondex api audit-state --json`, review `.moondex/state/hooks/warnings.json`, and either accept the warning as a documented operator decision or repair the payload/source condition. Do not continue as if warnings are invisible.

`surface_ref_missing`: run `moondex role register-current <role-id> --json` in the role surface, then retry or recreate dispatch as appropriate.

`retry_exhausted`: inspect the dispatch request, role identity, and cmux surface. Do not reset the request blindly; capture evidence and create a fresh dispatch only after the root cause is understood.

## 6. Evidence, Audit, Archive, Reset

Capture screen evidence when cmux output matters:

```bash
moondex cmux capture --surface surface:2 --lines 120 --json
moondex api list-evidence --json
```

Audit state before and after a meaningful phase:

```bash
moondex api audit-state --json
moondex api list-events --input '{"task_id":"T-01","limit":50}' --json
```

Archive only eligible old records:

```bash
moondex api archive-state --input '{"apply":false,"older_than_seconds":2592000}' --json
moondex api archive-state --input '{"apply":true,"older_than_seconds":2592000}' --json
```

`archive-state` does not archive `events.jsonl`. The active event stream remains the runtime history ledger.

For reset, remove or move only the runtime state the operator explicitly intends to reset. Preserve evidence and events unless the operator has a separate retention decision. After reset, run:

```bash
moondex init
moondex status --json
moondex api audit-state --json
```

