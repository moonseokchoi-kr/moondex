# Moondex Work Tracker

이 문서는 남은 Moondex runtime 작업을 자동으로 이어 구현하기 위한 실행 트래커다.

목표는 단순 TODO 목록이 아니라 다음 agent가 바로 하나씩 집어 구현할 수 있는 작업 큐를 유지하는 것이다. 각 작업은 입력, 산출물, 완료 기준, 검증 명령을 가진다.

## Operating Rule

- 한 번에 하나의 tracker item만 구현한다.
- 구현 전 관련 문서를 읽고 scope를 재확인한다.
- 구현 후 이 문서의 상태와 완료 메모를 갱신한다.
- 코드 변경이 있으면 `cargo fmt --check`, `cargo test -p moondex`를 기본 검증으로 수행한다.
- docs-only 변경은 관련 예시 payload 또는 `rg` 기반 문구 검증을 수행한다.
- `.codex/hooks`는 hook 정의와 enforcement entrypoint 위치다.
- `.moondex/state`는 runtime state 위치다.

Status values:

- `done`: 구현과 검증이 끝남
- `ready`: 바로 구현 가능
- `planned`: 구현 방향은 있으나 선행 item 필요
- `blocked`: 외부 결정이나 선행 정리가 필요

## Current State

Completed foundation:

- task lifecycle: create, claim, release, guarded transition
- dispatch lifecycle: request, ACK, retry limit, retry history
- role identity/status
- mailbox lifecycle: write, read, mark-read, consume, consume-for-task
- mailbox body schema hard validation
- audit/repair for legacy state
- cmux surface validation and evidence capture
- role transfer payload docs for execution loop
- `.codex/hooks/validate-role-transfer.sh`
- `moondex api validate-role-transfer`

Current gap:

- Codex native hook auto-discovery remains limited to a verified repo-local `.codex/hooks` contract until an official lifecycle manifest is confirmed.
- `next-action` remains available as advisory and non-mutating, while `orchestrator-step` and `orchestrator-loop` can now apply safe state-first actions.
- Runtime phase history is now append-only in `.moondex/state/events.jsonl` and queryable through `moondex api list-events`.
- AHE-lite contracts now exist for execution analysis reports, harness change manifests, and research benchmark runs. Full automatic evolution remains out of scope.
- GPT-5.5 operating shape guidance now keeps Moondex skills outcome-first while preserving runtime invariants.

Latest completed hardening:

- W-14 Phase Event Log: `events.jsonl`, `phase_advanced`, `list-events`, malformed event audit, archive preservation.
- W-15 cmux Operations Playbook: `docs/execution/cmux-operations-playbook.md`.
- W-16 Codex Hook Auto-Discovery: `moondex api inspect-hooks` plus `docs/execution/codex-hook-auto-discovery.md`.
- W-17 AHE-lite Baseline: analysis report schema, harness change manifest schema, and benchmark run README.
- W-18 GPT-5.5 Operating Shape: shared skill guidance plus harness change manifest.

## Implementation Queue

### W-18. GPT-5.5 Operating Shape

Status: `done`

Completion note:

- 2026-05-03: Added `docs/execution/gpt-5.5-operating-shape.md`, linked it from implementation workflow, runtime, and wave dispatcher skills, and recorded harness change manifest `HC-20260503-001`.

Purpose:

- Adapt OpenAI GPT-5.5 prompt guidance to Moondex without weakening task/plan/wave/readiness/runtime invariants.

Inputs:

- OpenAI Prompt guidance: `https://developers.openai.com/api/docs/guides/prompt-guidance`
- `docs/execution/low-interruption-policy.md`
- `docs/contracts/harness-change-manifest-schema.md`
- Moondex implementation workflow, runtime, and wave dispatcher skills

Implementation:

- Add shared GPT-5.5 operating shape guidance.
- Make relevant skills read the shared guidance.
- Add concise outcome-first execution rules to the skill surfaces.
- Record the change as an AHE-lite harness change manifest.

Done when:

- Skills link to the shared GPT-5.5 guidance.
- The guidance preserves all Moondex hard invariants.
- The release version is bumped to `0.2.1`.
- Verification passes.

Verification:

```bash
rg -n "gpt-5.5-operating-shape|GPT-5.5 Operating Shape|shortest safe path|outcome-first" README.md docs skills
python3 -m json.tool .codex-plugin/plugin.json
cargo fmt --check
cargo test -p moondex
scripts/doctor.sh --json
```

### W-17. AHE-Lite Baseline

Status: `done`

Completion note:

- 2026-05-02: Added AHE-lite documentation contracts for execution analysis reports, harness change manifests, and research benchmark runs. This records evidence-based harness improvement without introducing automatic edits, automatic rollback, or rollout aggregation.

Purpose:

- Establish a lightweight evidence trail for Moondex harness changes before adding any automatic evolution loop.

Inputs:

- `docs/research/meta-harness-benchmark-report.md`
- AHE analysis from PyTorchKR/arXiv discussion
- Existing `.moondex/state`, event, mailbox, evidence, and diagnostic contracts

Implementation:

- Add `docs/contracts/execution-analysis-report-schema.md`.
- Add `docs/contracts/harness-change-manifest-schema.md`.
- Add `docs/research/benchmarks/README.md`.
- Link the new contracts from README and mark the baseline in this tracker.

Done when:

- A Moondex operator can write an analysis report from runtime evidence.
- A non-trivial skill, policy, validator, runtime, or packaging change can be recorded as a harness change manifest.
- Benchmark run artifacts have a stable directory layout.
- The boundary between AHE-lite and full automatic evolution is explicit.

Verification:

```bash
rg -n "AHE-lite|execution analysis|harness change manifest|research benchmark|automatic evolution" README.md docs
test -f docs/contracts/execution-analysis-report-schema.md
test -f docs/contracts/harness-change-manifest-schema.md
test -f docs/research/benchmarks/README.md
```

### W-01. Planning Contracts Payload-Ready

Status: `done`

Completion note:

- 2026-04-26: Added planning payload examples to role transfer docs and added `validate-role-transfer` support for `task_planner_input`, `task_planner_output`, `wave_dispatcher_input`, and `wave_dispatcher_output`.

Purpose:

- Convert `task-planner` and `wave-dispatcher` contracts from document-level guidance into payload-ready examples.

Detailed plan:

- `docs/execution/work-items/W-01-planning-contracts-payload-ready.md`

Inputs:

- `docs/execution/role-transfer-contracts.md`
- `docs/contracts/plan-schema.md`
- `docs/contracts/wave-schema.md`
- `docs/templates/plan-template.md`
- `docs/templates/wave-template.md`
- `.codex/agents/task-planner.toml`

Implementation:

- Extend `role-transfer-contracts.md` with payload-ready examples for:
  - orchestrator -> `task-planner`
  - `task-planner` -> orchestrator
  - orchestrator -> `wave-dispatcher`
  - `wave-dispatcher` -> orchestrator
- Add examples that preserve `task_id`, `plan_id`, `wave_id`, dependency notes, ownership, verification commands, and blocked reasons.
- Update `validate-role-transfer` so it can recognize and validate `task_planner_input`, `task_planner_output`, `wave_dispatcher_input`, and `wave_dispatcher_output` payloads.

Done when:

- Each planning role has at least one valid payload example.
- Validator accepts valid examples and rejects missing required fields.
- README/HANDOFF no longer list planning contracts as unimplemented.

Verification:

```bash
cargo fmt --check
cargo test -p moondex
.codex/hooks/validate-role-transfer.sh '<valid-task-planner-input-json>'
```

### W-02. Readiness And Planning Quality Gate Validator

Status: `done`

Completion note:

- 2026-04-26: Added `moondex api validate-readiness`, `.codex/hooks/validate-readiness.sh`, READY/REVISION_REQUIRED/BLOCKED checks, and unit coverage.

Depends on:

- `W-01`

Purpose:

- Turn `docs/execution/task-readiness-gate.md` into an executable validator.

Detailed plan:

- `docs/execution/work-items/W-02-readiness-and-planning-quality-gate-validator.md`

Inputs:

- `docs/execution/task-readiness-gate.md`
- `docs/executor-direction.md`
- task/plan/wave schema docs
- W-01 planning payload validators

Implementation:

- Add `moondex api validate-readiness --input '<json>' --json`.
- Input should accept a JSON object containing task, plan, and optional wave payloads.
- Return `decision: READY | REVISION_REQUIRED | BLOCKED`, `errors`, `warnings`, and `missing_fields`.
- Hard fail missing executor-critical fields: objective, ownership/scope, verification commands, acceptance criteria, dependency/blocker status.
- Keep advisory warnings for weak tests, broad scope, or unclear parallel safety.
- Add `.codex/hooks/validate-readiness.sh` wrapper.

Done when:

- Valid task/plan payload returns `READY`.
- Missing plan verification returns `REVISION_REQUIRED`.
- Missing upstream decision/dependency returns `BLOCKED`.

Verification:

```bash
cargo fmt --check
cargo test -p moondex
.codex/hooks/validate-readiness.sh '<valid-ready-json>'
```

### W-03. Orchestrator Hook Integration

Status: `done`

Completion note:

- 2026-04-26: Connected role output validation to `write-mailbox`, added dispatch lifecycle guards, durable hook warnings at `.moondex/state/hooks/warnings.json`, and `audit-state.summary.hook_warnings`.

Depends on:

- `W-01`
- `W-02`

Purpose:

- Connect validators into the actual orchestrator flow instead of requiring manual hook calls.

Detailed plan:

- `docs/execution/work-items/W-03-orchestrator-hook-integration.md`

Inputs:

- `moondex api validate-role-transfer`
- `moondex api validate-readiness`
- dispatch/write-mailbox lifecycle

Implementation:

- Add hard validation before role handoff dispatch when a handoff payload is provided.
- Add hard validation before mailbox output write for canonical roles.
- Keep `.codex/hooks` scripts as external entrypoints.
- Record advisory warnings in `.moondex/state/hooks/warnings.json`.
- Add warnings to `audit-state` summary as `hook_warnings`, separate from mailbox/dispatch issues.

Done when:

- Invalid role/kind canonical output is blocked by `write-mailbox`, not only by manual validation.
- Invalid handoff payload is blocked before dispatch when supplied.
- Warnings are durable and visible in audit output.

Verification:

```bash
cargo fmt --check
cargo test -p moondex
./target/debug/moondex api audit-state --json
```

### W-04. Compliance-Reviewer Escalation Policy

Status: `done`

Completion note:

- 2026-04-26: Defined required/skipped/blocked compliance criteria, added code-reviewer `compliance_review_required` examples, and added validator warnings for missing or suspicious compliance decisions.

Purpose:

- Deepen the minimal compliance-reviewer criteria into an operational policy.

Detailed plan:

- `docs/execution/work-items/W-04-compliance-reviewer-escalation-policy.md`

Inputs:

- `docs/execution/role-transfer-contracts.md`
- `docs/execution/multi-agent-orchestration.md`
- `docs/executor-direction.md`

Implementation:

- Define required, optional, and skipped compliance-reviewer conditions.
- Add examples for:
  - code-reviewer only
  - compliance required
  - compliance blocked
- Add `compliance_review_required` decision examples for code-reviewer output.
- Update validator warning rules if the policy creates machine-checkable fields.

Done when:

- An orchestrator can decide whether to dispatch compliance-reviewer without inventing criteria.
- Role transfer examples include a compliance-required and compliance-skipped path.

Verification:

```bash
rg -n "compliance_review_required|compliance-reviewer" docs/execution docs/executor-direction.md
```

### W-05. Tester Contract And Integration/E2E Boundary

Status: `done`

Completion note:

- 2026-04-26: Promoted `tester` to a canonical role, added `tester_input` validation, fixed tester mailbox kinds, and documented integration/E2E dispatch criteria.

Purpose:

- Fix when tester exists as a separate role and what payload it consumes/produces.

Detailed plan:

- `docs/execution/work-items/W-05-tester-contract-and-integration-e2e-boundary.md`

Inputs:

- `docs/execution/role-transfer-contracts.md`
- `docs/examples/money-track-app-bootstrap-theme*/`
- `docs/execution/task-readiness-gate.md`

Implementation:

- Add tester input/output contract.
- Define tester-only triggers: integration, E2E, cross-flow, regression matrix, environment-specific verification.
- Define when implementer or code-reviewer can run tests without a tester.
- Add mailbox output examples for tester using existing `result`, `blocked`, `question`, and `status` kinds.

Done when:

- Tester dispatch is no longer ambiguous.
- Integration/E2E work has a clear handoff and output contract.

Verification:

```bash
rg -n "tester|integration|E2E|cross-flow" docs/execution docs/examples
```

### W-06. Orchestrator Next Action Automation

Status: `done`

Completion note:

- 2026-04-26: Added advisory, non-mutating `moondex api next-action --json` with priority over repair, hook warnings, mailbox consumption, dispatch ACK wait, role dispatch, and wait.

Depends on:

- `W-02`
- `W-03`
- `W-04`
- `W-05`

Purpose:

- Add a command that tells the operator the next state-first action to take.

Detailed plan:

- `docs/execution/work-items/W-06-orchestrator-next-action-automation.md`

Implementation:

- Add `moondex api next-action --json`.
- It should inspect tasks, dispatch, role status, mailbox, hook warnings, and readiness decisions.
- Output should recommend one action, such as:
  - consume mailbox
  - dispatch implementer
  - dispatch code-reviewer
  - dispatch compliance-reviewer
  - repair state
  - wait for ACK
  - mark blocked
- It should not mutate state.

Done when:

- On a temp runtime scenario, next-action gives a correct single next step through implementer -> review -> done.

Verification:

```bash
cargo fmt --check
cargo test -p moondex
./target/debug/moondex api next-action --json
```

### W-07. Worktree And Team Isolation Policy

Status: `done`

Completion note:

- 2026-04-26: Documented `no_worktree`, `external_worktree`, and `future_managed_worktree`, and clarified that this non-git docs/runtime repo must not require git worktrees.

Purpose:

- Decide and document how worktree/team isolation works when this repository is not a git repo.

Detailed plan:

- `docs/execution/work-items/W-07-worktree-and-team-isolation-policy.md`

Inputs:

- `docs/execution/cmux-runtime-alignment.md`
- `docs/execution/moondex-cli-plan.md`
- `docs/system-ext/HANDOFF.md`

Implementation:

- Document three modes:
  - no worktree: current repo docs/runtime mode
  - external worktree: target product repo supports git worktrees
  - future managed worktree: out of scope until repo/runtime supports it
- Add role identity metadata fields to document desired future shape, but do not add Rust fields unless required.
- Clarify that `moondex` cannot require git worktrees while it is not a git repo.

Done when:

- Operator can tell which isolation mode applies before dispatching a team.
- Docs stop treating worktree-first behavior as implicit.

Verification:

```bash
rg -n "worktree|isolation|team" docs/execution docs/system-ext/HANDOFF.md
```

### W-08. Runtime State Cleanup And Archive Policy

Status: `done`

Completion note:

- 2026-04-26: Documented runtime retention rules, manual archive candidates, no-silent-delete records, and future `archive-state` command shape.

Purpose:

- Define how `.moondex/state` grows, what can be archived, and what must remain durable.

Detailed plan:

- `docs/execution/work-items/W-08-runtime-state-cleanup-and-archive-policy.md`

Inputs:

- current `.moondex/state` layout
- audit/repair behavior
- evidence capture behavior

Implementation:

- Document retention policy for completed tasks, consumed mailbox messages, dispatch history, hook warnings, and evidence files.
- Add `moondex api archive-state --input '{"apply":false}' --json` plan if code implementation is chosen later.
- For v1 docs, define manual archive rules only.

Done when:

- Operators know whether to keep or prune completed smoke tasks and old mailbox entries.
- Future archive command has a clear behavior spec.

Verification:

```bash
rg -n "archive|retention|cleanup|completed tasks|hook warnings" docs
```

## Suggested Automation Order

W-01 through W-13 are complete. Next automation candidates should be added as W-14+ rather than reopening these items.

### W-09. Same-Task Review Phase Runtime

Status: `done`

Completion note:

- 2026-04-27: Added `Task.phase`, automatic same-task phase transfer on orchestrator mailbox consume, and tests for implementation -> code review -> done plus review -> compliance handoff.

Purpose:

- Keep implementer, reviewer, compliance, and tester passes under one logical `task_id` instead of creating separate review tasks.

Implementation:

- New tasks derive `phase` from their initial role.
- Consuming an implementer `result` for a completed implementation task requeues the same task as `pending`, `phase: code_review`, `role: code-reviewer`.
- Consuming a `code-reviewer` approval completes the task when `compliance_review_required` and `tester_required` are false.
- Consuming a `code-reviewer` approval with `compliance_review_required: true` requeues the same task for `compliance-reviewer`.
- Consuming a compliance approval can requeue to tester or mark done.
- Consuming a tester result marks the task done.
- Blocked mailbox outputs move the task to `blocked`.

Verification:

```bash
cargo fmt --check
cargo test -p moondex
```

### W-10. Compliance/Tester Phase End-To-End Validation

Status: `done`

Completion note:

- 2026-04-27: Added richer phase-aware role inbox payloads and preserved previous task mailbox context so code-reviewer, compliance-reviewer, and tester phases can inspect upstream outputs under one `task_id`.

Purpose:

- Make the pre-loop phase path inspectable and testable before automating the orchestrator loop.

Implementation:

- Role inbox now includes a machine-readable payload with task state, previous relevant mailbox messages, and the expected output contract for the target role.
- Reviewer and tester inboxes include recent upstream outputs for the same task.
- Unit coverage verifies reviewer inbox context and output contract rendering.

Verification:

```bash
cargo fmt --check
cargo test -p moondex
```

### W-11. Orchestrator Loop Execution

Status: `done`

Completion note:

- 2026-04-27: Added `moondex api orchestrator-step` and `moondex api orchestrator-loop`; `next-action` stays advisory, while the new commands can consume mailbox messages, dispatch roles, and optionally repair state.

Purpose:

- Convert the advisory next action into a bounded, operator-controlled execution loop.

Implementation:

- `orchestrator-step --input '{"apply":true}'` applies one safe action.
- `orchestrator-loop --input '{"apply":true,"max_steps":N}'` repeats bounded steps until it reaches wait, ACK wait, hook warning review, a repeated-action guard, or `max_steps`.
- The loop does not auto-ACK dispatch requests and does not auto-review hook warnings.
- `next-action` now includes mailbox metadata (`message_id`, `from_role`, `kind`) so the loop can execute consume actions without parsing command text.

Verification:

```bash
cargo fmt --check
cargo test -p moondex
```

### W-12. Archive-State Implementation

Status: `done`

Completion note:

- 2026-04-27: Implemented `moondex api archive-state` with dry-run/apply modes, archive manifests, and selective pruning for completed tasks, consumed mailbox messages, delivered dispatch requests, and optional hook warnings.

Purpose:

- Move retention policy from docs-only guidance into a runtime command.

Implementation:

- Dry-run reports candidates without mutation.
- Apply writes `.moondex/state/archive/<archive-id>/manifest.json` plus archived record files, then removes only eligible active records.
- Blocked tasks, pending/notified/failed dispatch, and unconsumed mailbox messages remain active.

Verification:

```bash
cargo fmt --check
cargo test -p moondex
```

### W-13. Rich Role Inbox Payload

Status: `done`

Completion note:

- 2026-04-27: Dispatch inboxes now include previous relevant outputs and an expected-output JSON contract, reducing reviewer/tester context lookup work.

Purpose:

- Give downstream roles enough structured context to review or test without reconstructing the prior phase manually.

Implementation:

- `dispatch` renders `roles/<role-id>/inbox.md` with human summary and a machine payload.
- The payload includes `task`, `previous_messages`, and `expected_output`.
- Previous messages are filtered by active target role and same `task_id`.

Verification:

```bash
cargo fmt --check
cargo test -p moondex
```

### W-14. Phase Event Log

Status: `done`

Completion note:

- 2026-04-27: Added append-only `.moondex/state/events.jsonl`, event emission for task/dispatch/mailbox/archive/phase transitions, `moondex api list-events`, malformed event audit reporting, and archive preservation.

Verification:

```bash
cargo fmt --check
cargo test -p moondex
```

### W-15. cmux Operations Playbook

Status: `done`

Completion note:

- 2026-04-27: Added `docs/execution/cmux-operations-playbook.md` with surface setup, role registration, task dispatch, worker ACK/claim/status/mailbox flow, reviewer payload examples, common stop handling, and evidence/audit/archive/reset procedures.

Verification:

```bash
rg -n "cmux-operations-playbook|source of truth|events.jsonl" docs README.md
```

### W-16. Codex Native Hook Auto-Discovery

Status: `done`

Completion note:

- 2026-04-27: Added repo-local hook discovery through `moondex api inspect-hooks --json` and documented the lifecycle bridge in `docs/execution/codex-hook-auto-discovery.md`. Native Codex lifecycle behavior remains explicit verification work, not guessed runtime behavior.

Verification:

```bash
cargo fmt --check
cargo test -p moondex
moondex api inspect-hooks --json
```

## Tracker Maintenance

After each item:

- change `Status` to `done`
- add a short completion note with date
- remove or update corresponding items in README and `docs/system-ext/HANDOFF.md`
- run the listed verification
