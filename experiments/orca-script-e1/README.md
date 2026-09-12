# E1: Orca script authority and durable delivery experiment

Development-only experiment. This is not the Moondex production executor.

## Authorized objective

The user accepted d1's recommended direction. Approval is recorded in
`docs/execution/delegated-execution-redesign/approvals/design-d1.json`; d1 and requirements r1 remain unchanged.

Observe whether a script child of the current legitimate Orca session can create/bind a Run,
start one supervised worker, persist its result, restart before acknowledging the Delivery,
verify the actual output, and release only the worker it owns.

## Execution contract — resource limits approved 2026-09-07

- Input: fixture JSON `{experiment, nonce, value:21}`.
- Worker output: one JSON file `{experiment, nonce, doubled:42}`.
- Worker scope: only `.harness/audit/execution/orca-script-e1/fixture/output.json`.
- Current worktree; no new worktree, no original-session takeover, no other worker resources.
- Agent: Codex with the configured default model; record the effective launch receipt.
- Maximum concurrent workers: 1. Automatic launch/task retries: 0.
- Proposed worker wall deadline: 600 seconds. At the deadline stop only the exact owned Dispatch,
  preserving its receipt and output. Poll timeouts are progress checkpoints, not task failures.
- A monetary/token cap is not claimed without proven usage telemetry.
- User approved these limits: “응 진행해줘, 사용량에 여유가 있어서 괜찮아”.

The original handoff has no lifecycle obligations. E1 has its own newly created Run and,
when launched, its own Task/Dispatch. Only that E1 worker will send worker_done.

## Procedure

1. Persist each RPC intent before executing the CLI. Preserve stdout/stderr and exit code.
   An unknown mutation is never automatically repeated.
2. Start a fixture Task/worker through the experimental script after resolving its limits.
3. The collection script stores all messages in the Delivery transactionally, deduplicated by message ID.
4. Intentionally exit after durable inbox storage but before release/ack. Restart the script in a new process.
5. Verify that Orca returns the same unacknowledged Delivery and local effects are applied only once.
6. Treat worker_done as a submission. Run `verify_fixture.py` as a separate process, on the actual output.
7. Capture `worker-show` and release the exact settled worker before acknowledging; unknown release
   must follow the receipt, never a generic terminal close.
8. Save a result separating parent-session-alive restart from detached/parent-ended authority.
   This experiment must not kill or impersonate the user's current session to simulate detachment.

## Local checks already performed

The oracle rejects missing output, wrong arithmetic, and an old nonce; accepts correct output.
`rpc.py` executed Run creation from a Python subprocess without `--from` or injected credentials.
Read-only run inspection and inbox peek succeeded. This proves only those capabilities in the
currently live authenticated parent context, not worker launch or detached persistence.

Evidence lives in `.harness/audit/execution/orca-script-e1/` and
`.harness/state/execution/orca-script-e1/experiment.sqlite`.
The latter records intents before external effects; it is experiment-local state, not legacy SDD approval.

## Observed result, 2026-09-07

One live Task/Dispatch completed. After commit and process exit 86, a new collector process
received the same Delivery ID and identical messages. Inbox and local effect counts were 1.
The separate fixture command passed; worker-release returned released/closed_agent_terminal;
acknowledgement returned an empty inbox. No worker restart or second task occurred.

An initial full-response comparison rejected replay transport metadata (`replayed`, request ID).
The corrected comparison preserves run/Delivery/message/count identity. Local negative checks
ensure changed identity or content still fails. This is an experiment implementation repair,
not a lowered acceptance criterion.

Only the authenticated parent-alive context was exercised. Parent-ended/idle authority,
unknown launch side-effect recovery, monetary telemetry, and worker reuse remain unproven.
Scripts are staged development probes with operator receipt inspection, not a completed
unattended production scheduler. `supervise.py` automates bounded collection/restart, but
its deadline is not yet a production-grade independent watchdog.
