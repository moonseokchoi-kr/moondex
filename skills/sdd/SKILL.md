---
name: sdd
description: "Spec → design → plan → execute workflow with project-local, controller-first resume"
---

# SDD (Spec-Driven Development)

SDD organizes work as Spec → Design → Plan → Execute → Knowledge Sync. The named **SDD coordinator** delegates artifact authoring, validates phase evidence, and reports controller results and required user approvals.

## Controller-first operation

The project-local controller is the only lifecycle authority. It needs no host variables, session identity, or lifecycle integration.

In every command below, resolve `<moondex-runtime>` from this loaded skill:
it is the absolute `../sdd/runtime/moondex-runtime.py` path relative to this skill
directory. Never resolve it from the consumer working directory or require the
user to know the plugin installation path.

```bash
# Start is idempotent: it creates state only when this feature has no state.
python3 <moondex-runtime> state --project-root . start <feature>

# At the beginning of every ordinary Codex turn, inspect then calculate the next step.
python3 <moondex-runtime> state --project-root . status <feature>
python3 <moondex-runtime> state --project-root . resume <feature>

# Optional local integration is advisory only.
python3 <moondex-runtime> state --project-root . doctor <feature>
```

Read the JSON result before acting. `ACTION` contains an explicit next command or work item; `WAITING_USER` is the only reason to wait for a user approval; `BLOCKED_ARTIFACT`, `STATE_INVALID`, and `STATE_BUSY` require the stated remediation. `status` and `resume` are read-only. Do not claim background continuation between turns.

## Phase-scoped transition authority

The project-local controller remains the lifecycle source of truth and serializes every write. The **SDD coordinator** is the sole authorized caller of `state transition` while the current phase is `SPEC`, `DESIGN`, or `PLAN`. It may call a transition only after the controller preflight recognizes the required feature-scoped artifacts and the user explicitly approves the immediately requested gate in the current turn. Approval is never inferred or pre-registered.

Workers never invoke `state transition`. They return artifacts and evidence to the current authority owner and never mutate `.harness/state/` or `docs/sdd/ORCHESTRATOR_STATE.md`.

The three pre-execution transitions below are the complete transition surface owned by the SDD coordinator.

<!-- authority-transition SPEC->DESIGN owner="SDD coordinator" -->
```bash
python3 <moondex-runtime> state --project-root <project-root> transition --feature <feature> --expected SPEC --target DESIGN --approve spec
```

<!-- authority-transition DESIGN->PLAN owner="SDD coordinator" -->
```bash
python3 <moondex-runtime> state --project-root <project-root> transition --feature <feature> --expected DESIGN --target PLAN --approve design
```

<!-- authority-transition PLAN->EXECUTE owner="SDD coordinator" -->
```bash
python3 <moondex-runtime> state --project-root <project-root> transition --feature <feature> --expected PLAN --target EXECUTE --approve plan --worktree <worktree>
```

On a successful `PLAN → EXECUTE` result, perform exactly one **authority handoff: SDD coordinator -> execution orchestrator**. From that result onward the SDD coordinator stops invoking transitions and stops writing orchestration state. The execution orchestrator becomes the sole transition and `ORCHESTRATOR_STATE.md` writer through `RESULT`; the two owners must never be active as writers at the same time.

## Phase gates

1. **Spec** — delegate the spec, run blocker review, then request explicit spec approval.
2. **Design** — delegate architecture (and UX/API when required), review it, then request design approval.
3. **Plan** — delegate task and DAG creation, verify `ORCHESTRATOR_STATE.md`, then request plan approval.
4. **Execute** — invoke `sdd-orchestrator`; it runs implement → compliance → review → test loops in the assigned worktree.
5. **Result and knowledge sync** — after all tasks are complete and verified, the orchestrator creates the result. Knowledge sync is `SKIPPED` when no compound root is explicitly supplied or configured.

The controller enforces one forward phase transition at a time. An explicit user approval is supplied only for the immediately requested transition (`spec`, `design`, or `plan`). Never infer approval from a prior turn.

## Normal-turn resume

When a user says “continue”, run `state status` then `state resume` for the active feature. Follow the returned `next_step`:

- `ACTION`: delegate or perform the named scoped operation.
- `WAITING_USER`: present the exact approval required; do not advance until the user answers.
- `BLOCKED_ARTIFACT`: delegate creation or repair of only the named artifact, then re-run `resume`.
- `COMPLETE`: report the result; knowledge sync remains optional.

`status` and `resume` are read-only routing operations, not transition authority. In an ordinary turn, route their result by the controller phase:

- `SPEC`, `DESIGN`, or `PLAN`: the SDD coordinator consumes the result, delegates the named artifact work, and requests the immediate approval when `WAITING_USER` is returned.
- `EXECUTE` or `RESULT`: route the unchanged result to the execution orchestrator. The SDD coordinator does not perform another state write after handoff.

An `ACTION` in `RESULT` means the execution orchestrator must generate or report the result artifact; it does not authorize another transition. After the artifact exists, route the controller's `COMPLETE` outcome to the same execution orchestrator for final reporting and optional configured knowledge sync.

At `PLAN`, `resume` can report `BLOCKED_ARTIFACT` until an isolated worktree has been selected because the worktree path is supplied atomically with the `PLAN → EXECUTE` transition. The SDD coordinator validates that directory and the task/DAG artifacts first, then requests explicit plan approval and passes the validated path as `--worktree`; it does not treat the blocked result as approval.

An absent optional local integration is an advisory result from `doctor`, not a phase-gate failure. It may not select a label, bypass approval, or mutate state.

## Artifact layout

```
docs/sdd/
├── spec/{date}-{feature}.md
├── design/arch/{date}-{feature}.md
├── design/ui/{date}-{feature}.md       # FULL mode only
├── design/api/{date}-{feature}.md      # FULL mode only
├── context/{date}-{feature}.md         # FULL mode only
├── task/{feature}/{date}-T-{N}-{task}.md
├── ORCHESTRATOR_STATE.md
└── result/{date}-{feature}.md

.harness/state/
└── pipeline.json                        # controller-owned lifecycle state
```

## Execution rules

- Do not skip spec, design, plan, task/DAG, or required approval gates.
- All implementation is isolated in the worktree recorded by the controller.
- Every task completes implementation → compliance → review → independent test verification.
- After three failed iterations, preserve evidence and escalate to the user.
- Do not write lifecycle state directly. Use the controller command only where this skill authorizes it.
