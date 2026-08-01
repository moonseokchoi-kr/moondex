---
name: sdd-orchestrator
description: "Controller-authorized SDD execution: task waves, verification loops, results, and optional knowledge sync"
user-invocable: false
---

# SDD Execution Orchestrator

The named **execution orchestrator** is the sole lifecycle and orchestration-state writer after the controller has successfully entered `EXECUTE`, including when a later turn resumes in `RESULT`. It receives the controller `ACTION` result and the explicit **authority handoff: SDD coordinator -> execution orchestrator**, reads the feature's task/DAG record, executes each task through implement → compliance → review → test, and completes result reporting. It must not assume any host lifecycle integration or background continuation.

## Entry and resume

Start or re-enter only after the controller reports `ACTION` with phase `EXECUTE` or `RESULT`. `EXECUTE` requires the recorded feature worktree; `RESULT` is a resumable result-generation/reporting action and does not dispatch task workers. On every re-entry:

Resolve `<moondex-runtime>` to the absolute
`../sdd/runtime/moondex-runtime.py` path from this loaded skill directory. This
package-relative resolution must not depend on the consumer cwd, `PYTHONPATH`,
host variables, or user knowledge of the plugin installation directory.

```bash
python3 <moondex-runtime> state --project-root <project-root> status <feature>
python3 <moondex-runtime> state --project-root <project-root> resume <feature>
```

Respect `WAITING_USER`, `BLOCKED_ARTIFACT`, `STATE_INVALID`, and `STATE_BUSY` exactly as returned. The orchestrator may invoke `state transition` only in phase `EXECUTE`, after validating the worker evidence and required artifacts for `EXECUTE → RESULT`. It must not invoke `state transition` while the controller phase is `RESULT`.

If `status` or `resume` reports `SPEC`, `DESIGN`, or `PLAN`, return the unchanged result to the SDD coordinator. The execution orchestrator must not invoke a pre-execution transition or write orchestration state before handoff. Once the phase is `EXECUTE`, ordinary-turn `status`/`resume` results for both `EXECUTE` and `RESULT` route here and the SDD coordinator is no longer a writer.

## Authority boundary

- From the accepted `EXECUTE` handoff onward, the execution orchestrator alone updates `docs/sdd/ORCHESTRATOR_STATE.md` and invokes controller transitions.
- Engineers, compliance checkers, reviewers, and test automators return the `agents/SDD_WORKER_CONTRACT.md` envelope: completion `Status` (`DONE`, `DONE_WITH_CONCERNS`, `NEEDS_CONTEXT`, or `BLOCKED`), optional role/stage `Verdict`, changed paths, validation, and evidence. They do not write orchestration state or `.harness/state/`.
- Before dispatching an agent, record the task's in-progress stage in `ORCHESTRATOR_STATE.md`; after every result, record the result and evidence.
- Optional local integrations are advisory. Their absence never blocks execution or changes controller state.

## Wave loop

For each ready task (maximum four concurrent workers):

1. Dispatch the task implementer with the task contract, owned paths, worktree, and accumulated feedback.
2. On `DONE` or `DONE_WITH_CONCERNS`, record `verifying`, then dispatch the compliance checker. `COMPLIANCE_FAIL` with `BLOCKED` returns the task to the implementer and increments its retry through the controller.
3. On a passing status plus `COMPLIANCE_PASS`, record `reviewing`, then dispatch the reviewer. `REVIEW_FAIL` with `BLOCKED` returns the task to the implementer.
4. On a passing status plus `REVIEW_PASS`, record `testing`, then dispatch the test automator. Only a passing status plus independent `TEST_PASS` marks the task `complete`.
5. Never transition on a missing or contradictory stage verdict; treat it as `NEEDS_CONTEXT` and collect corrected evidence.
6. After three failed iterations, record escalation evidence and stop for the user rather than silently continuing.

Advance to the next wave only when all tasks in the current wave are complete. Do not mark a feature result-ready until the feature task table has one verified complete row for every task document.

## Result transition

After all waves, run project integration validation and confirm the feature task table satisfies the controller's completion preflight. Then invoke the only transition owned by this role:

<!-- authority-transition EXECUTE->RESULT owner="execution orchestrator" -->
```bash
python3 <moondex-runtime> state --project-root <project-root> transition --feature <feature> --expected EXECUTE --target RESULT
```

Generate `docs/sdd/result/{date}-{feature}.md` only after the result transition succeeds. Return the result and validation evidence to the SDD coordinator.

## RESULT resume and reporting

`EXECUTE → RESULT` and result document generation are separate durable steps, so interruption between them is expected and resumable.

<!-- authority-resume phase="RESULT" owner="execution orchestrator" transition="forbidden" action="generate-result-report" -->

When `status`/`resume` returns `ACTION` with controller phase `RESULT` and says the result artifact is required:

1. Re-enter the execution orchestrator; do not call `state transition` again.
2. Persist the controller result and verified result evidence as regular JSON files inside the repository, then invoke the narrow RESULT action:

```bash
python3 <moondex-runtime> result-action --project-root <project-root> --feature <feature> --controller-result <repository-result-action.json> --evidence <repository-verified-evidence.json>
```

The callable queries the public read-only controller `status` and `resume` APIs and normally requires the supplied value to be exactly the current live `RESULT`/`ACTION` for the same feature. On first success it computes `v1` SHA-256 over stable sorted UTF-8 canonical JSON of that exact ACTION and persists the digest in the immutable result, Compound snapshot, and project sync report. Verified evidence uses `schema_version: 1`, a stable `completion_identity`, `verified: true`, a non-empty summary, and one or more `{name, status: "PASS", evidence}` validation entries. It validates every target and permission before creating directories, atomically creates the result report, and never invokes a controller transition or task worker. Durable reports and snapshots use non-truncating structural redaction: non-secret source content and length semantics are retained while sensitive keys and credentials embedded in free text, headers, key/value text, Bearer values, and argv are removed. CLI error/outcome presentation may remain bounded. With no configured sync it returns `Status: DONE`, `Verdict: SYNC_SKIPPED` and embeds a durable redacted sync report. With explicit valid `compound_root`, `destination`, `credential_source`, and `retention_policy`, every configured and derived role is named: destination, index, log, lock, raw-projects/feature/run directories, snapshot, project result directory, result, and sync report. Their NFC+casefold relative identities are compared pairwise before writes; under the lock, every existing role must have its declared regular-file/directory type, must not be a symlink, and every existing pair is compared by device/inode. This catches aliases between any roles—not only destination—including index/log, snapshot/index, and result/report hardlinks, while ordinary distinct files sharing a parent remain valid. For macOS/local-filesystem portability, case variants and composed/decomposed names also fail closed. The callable serializes the complete Compound transaction with a root-scoped portable `fcntl.flock` on durable `.moondex-sdd-sync.lock` mode `0600`; the lock is acquired before mutable wiki/index/log reads and held through commit, rollback, or recovery verification. Lock-file presence is durable coordination metadata and is not rolled back. Under that lock it reads `CLAUDE.md` and `wiki/index.md`, writes a completion-identity-derived append-only `raw/projects/<feature>/sdd-<date>-<run-id>/snapshot.json`, updates the configured wiki page, `wiki/index.md`, and `wiki/log.md`, creates the project-side compound sync report, and only then returns `SYNC_APPLIED`. A fixed completion identity is idempotent; a distinct same-day identity gets a distinct run directory. After response loss, a supplied original ACTION may be replayed against live `RESULT/COMPLETE` only when its canonical digest agrees with every persisted digest and its feature and completion identity reproduce every prior durable project and compound output byte-for-byte; JSON key reordering is equivalent, while any field/value addition, removal, or change is not. This recovery performs no writes and returns the original verdict/run-id. Missing, changed, or tampered action digest, evidence, config, result, sync report, snapshot, wiki page, index, or log blocks recovery. Invalid, stale, outside-root, symlink, permission, duplicate-role, lock-timeout, or conflicting inputs fail closed; any write failure removes newly created paths and restores modified wiki/index/log bytes and modes.

3. Treat only a `Status: DONE` outcome as successful result generation.
4. Run `state status`/`state resume` again. `COMPLETE` is the terminal controller outcome for the local result artifact.
5. Report the result and validation evidence. Reporting back to the SDD coordinator does not return transition or state-write authority.

## Optional knowledge sync

Knowledge sync is optional. Run it only when an explicit `compound_root` is supplied and its operating rules are readable. Otherwise record `Status: DONE` and `Verdict: SYNC_SKIPPED` in the result sync report; this does not fail the implementation result. Never use a personal filesystem path as a default.
