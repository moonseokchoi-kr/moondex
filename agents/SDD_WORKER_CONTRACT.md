# SDD Worker Contract

All active Moondex role profiles use this host-neutral contract.

- Inputs are supplied by the coordinator: feature, scoped artifact/task, project root, worktree when applicable, and prior evidence.
- A worker may write only its task-owned artifacts and files.
- A worker must not create, edit, write, update, persist, save, record, or overwrite `docs/sdd/ORCHESTRATOR_STATE.md`, any `STATE.md`, or anything under `.harness/state/`.
- Every worker returns the same result envelope:

  ```text
  Status: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED
  Verdict: <optional role/stage verdict>
  Changed paths: <task-owned paths, or none>
  Validation: <commands and observable evidence>
  Evidence / blocker: <facts needed by the orchestrator>
  ```

- `Status` is the lifecycle-independent completion status. `DONE` means the assigned
  work passed, `DONE_WITH_CONCERNS` means it passed with non-blocking concerns,
  `NEEDS_CONTEXT` means required input is missing, and `BLOCKED` means the assigned
  gate or work did not pass.
- Canonical Status vocabulary: `DONE` | `DONE_WITH_CONCERNS` | `NEEDS_CONTEXT` |
  `BLOCKED`. Active role profiles may declare a subset, but must not introduce
  another `Status` value.
- `Verdict` is optional and never replaces `Status`. Stage roles use one of
  `READY`, `COMPLIANCE_PASS`, `COMPLIANCE_FAIL`, `REVIEW_PASS`, `REVIEW_FAIL`,
  `TEST_PASS`, `TEST_FAIL`, `SYNC_APPLIED`, `SYNC_SKIPPED`, `PASS`, or `REWORK`.
- Declared Verdict vocabulary: `READY` | `COMPLIANCE_PASS` | `COMPLIANCE_FAIL` |
  `REVIEW_PASS` | `REVIEW_FAIL` | `TEST_PASS` | `TEST_FAIL` | `SYNC_APPLIED` |
  `SYNC_SKIPPED` | `PASS` | `REWORK`. Role profiles may declare only the subset
  that their output contract uses.
- Passing verdicts require `DONE` or `DONE_WITH_CONCERNS`. Failing verdicts require
  `BLOCKED`. Team readiness is `Status: DONE` plus `Verdict: READY`; `READY` is not
  a lifecycle status. A skipped knowledge sync is `Status: DONE` plus
  `Verdict: SYNC_SKIPPED`.
- Adversarial review uses `Status: DONE` plus `Verdict: PASS` when the approach is
  acceptable, and `Status: BLOCKED` plus `Verdict: REWORK` when structural changes
  are required. An inability to propose a viable alternative is `Status: BLOCKED`
  with no verdict.
- The orchestrator is the sole lifecycle writer and decides whether to invoke the project-local controller.
- Organization knowledge sync requires an explicit `compound_root`; when absent it reports `Status: DONE` with `Verdict: SYNC_SKIPPED`.
