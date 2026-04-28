# Meta Harness Benchmark Report

Date: 2026-04-28

Source repository: `https://github.com/SaehwanPark/meta-harness`

Temporary clone used for analysis: `/tmp/moondex-meta-harness-analysis`

## Executive Summary

`meta-harness` is most useful to Moondex as a benchmark framework for dynamic team composition, durable handoff artifacts, and validation scenarios. It should not be copied as Moondex runtime architecture.

Moondex already has stronger runtime enforcement than `meta-harness`: task phases, leases, dispatch, mailbox contracts, readiness validation, hook wrappers, event logs, archive policy, and cmux role surfaces. The useful benchmark target is policy quality: when to invoke roles, which pattern a task or wave should use, what handoff artifacts must exist, and how normal and failure flows should be validated.

## What Meta Harness Provides

The upstream repository is a portable meta-skill package for designing repo-local agent workflows. It is mostly documentation plus small Python installer and validation scripts.

Important components:

- `AGENTS.md`: intentionally short repo-wide guidance.
- `.agents/skills/harness/SKILL.md`: the main skill for designing domain workflows, specialist skills, team specs, and deterministic handoff artifacts.
- `.agents/skills/harness/references/`: progressive-disclosure references for architecture patterns, AGENTS authoring, skill writing/testing, QA, autonomous experimentation, team examples, and orchestrator templates.
- `docs/harness/README.md`: generated artifact contract for team specs, role briefs, `_workspace/` handoffs, and experiment ledgers.
- `docs/harness/starter-research/team-spec.md`: minimal research team spec with roles, workflow, failure policy, and validation.
- `scripts/install_harness.py`: installs the canonical skill tree into project or user scopes.
- `scripts/test_install_harness.py`: smoke-tests installer behavior.
- `scripts/validate_codex_port.py`: validates required files, links, skill frontmatter, headings, pattern coverage, and banned legacy tokens.

## Workflow Benchmark

`meta-harness` uses a six-phase workflow:

1. Domain Analysis
2. Team Architecture Design
3. Role and Artifact Definition Generation
4. Skill Generation
5. Integration and Orchestration
6. Validation and Testing

Moondex should benchmark against this as a policy design loop, not as a replacement for `.moondex/state`.

Recommended Moondex mapping:

| Meta Harness Phase | Moondex Equivalent |
| --- | --- |
| Domain Analysis | task/readiness analysis, task planner input quality |
| Team Architecture Design | dynamic role chain and wave pattern selection |
| Role and Artifact Definition | task/plan/wave plus role mailbox contracts |
| Skill Generation | optional Moondex specialist skills only when reusable |
| Integration and Orchestration | `next-action`, `orchestrator-step`, `orchestrator-loop`, dispatch and mailbox state |
| Validation and Testing | validator results, event log, audit-state, benchmark scenario outcomes |

## Architecture Pattern Mapping

Moondex can use the six upstream patterns as a role-composition vocabulary:

| Pattern | Moondex Use |
| --- | --- |
| Pipeline | `task -> plan -> wave -> implementation -> review -> optional compliance/test` |
| Fan-out/Fan-in | independent wave tasks, planner pool, parallel review angles, then synthesis |
| Expert Pool | conditional `compliance-reviewer`, `tester`, or future domain specialists |
| Producer-Reviewer | `implementer -> code-reviewer` with bounded revision |
| Supervisor | orchestrator managing backlog, leases, stale roles, retry, archive, and phase transfer |
| Hierarchical Delegation | use sparingly for domain splits; keep coordination shallow |

The strongest immediate fit is `Expert Pool` plus `Producer-Reviewer`. Moondex already has fixed roles; the benchmark should test when those roles should be attached.

## Recommended Benchmark Tracks

### 1. Role Selection Benchmark

Goal: verify dynamic team composition.

Input:

- task metadata
- ownership scope
- changed files
- shared contract flags
- user-visible behavior flags
- verification requirements
- prior mailbox outputs

Expected output:

- selected role chain
- skipped-role rationale
- escalation trigger

Scenarios:

- local low-risk code change: `implementer -> code-reviewer`
- docs-only contract change: `implementer -> code-reviewer -> compliance-reviewer`
- persisted state, schema, CLI, API, or archive behavior: require `compliance-reviewer`
- integration/E2E/external IO/user-critical flow: require `tester`
- ambiguous changed files: route to compliance instead of guessing
- reviewer requests changes: return to implementation with bounded rework

### 2. Pattern Selection Benchmark

Goal: decide whether a task set should use Pipeline, Fan-out/Fan-in, Supervisor, or hybrid composition.

Scenarios:

- strict dependency chain: Pipeline
- independent wave tasks: Fan-out/Fan-in
- changing backlog or stale leases: Supervisor
- implementation plus mandatory review: Producer-Reviewer
- conditional compliance/test roles: Expert Pool

### 3. Handoff Quality Benchmark

Goal: score whether role handoff artifacts are complete enough for downstream independence.

Rubric:

- named input
- named output
- owner role
- task id and phase
- scope boundary
- verification evidence
- failure path
- downstream role can proceed without hidden context

This should build on existing `validate-role-transfer` and `validate-readiness` checks, but extend them into cross-artifact consistency.

### 4. Review Boundary Benchmark

Goal: prevent reviewer roles from overlapping or skipping risk.

Expected boundaries:

- `code-reviewer`: implementation correctness, regression risk, tests, maintainability
- `compliance-reviewer`: spec/design/contract/schema/API/CLI/state/archive/policy-sensitive boundaries
- `tester`: independent integration/E2E/user-flow evidence when warranted

Scenarios:

- code reviewer skips compliance on sensitive path: should flag risk
- compliance reviewer duplicates code review instead of contract review: should fail benchmark
- tester runs unit-level checks only for an E2E-required change: should fail benchmark

### 5. Failure Flow Benchmark

Goal: enforce deterministic fallback instead of ad hoc blocking.

Scenarios:

- implementer lease expires
- dispatch remains pending/notified without ACK
- reviewer requests changes beyond the current plan
- compliance finds scope drift
- tester finds integration failure
- planner task is too broad and needs split
- hook warning exists but orchestrator attempts to continue

Assertions:

- state transition is explicit
- event log records the change
- mailbox output has valid schema
- next action is deterministic
- operator stop reason is actionable

## Artifact Strategy

Do not adopt `_workspace` as the Moondex source of truth. Use `.moondex/state` for runtime truth.

Use `_workspace`-style artifacts only for benchmark runs, and make them derived or auditable against runtime state:

```text
docs/research/benchmarks/{run-id}/
  request-summary.md
  team-spec.md
  role-selection-matrix.md
  scenario-results.tsv
  final-report.md
```

This preserves the useful upstream idea, deterministic intermediate artifacts, without duplicating or replacing `.moondex/state`.

## Proposed Moondex Additions

### Documentation

- `docs/contracts/team-spec-schema.md`
- `docs/execution/dynamic-team-composition.md`
- `docs/research/benchmarks/README.md`

### Skills

- `skills/moondex-team-designer`
  - chooses role chain and team pattern for a task or wave
  - produces a team spec or role-selection matrix
  - keeps `.moondex/state` as runtime truth

### Future CLI

Only after the docs and skill are exercised:

```bash
moondex api propose-team --input '{"task_id":"T-01"}' --json
moondex api apply-team --input '{"task_id":"T-01","team_spec":{...}}' --json
```

The first CLI should be non-mutating. The second should only write durable state after the proposed contract is stable.

## Risks

- Copying `meta-harness` directly would regress Moondex toward markdown-only orchestration.
- `_workspace` can drift from `.moondex/state` if it becomes a parallel truth source.
- More roles can reduce throughput if role selection is not machine-checkable.
- Hierarchical delegation can hide ownership and should remain rare.
- Scenario benchmarks can become prompt tests unless they assert state transitions, mailbox outputs, audit output, and events.

## Best Next Benchmark

Use the `money-track-app-bootstrap-theme-raw-replan` example as the first benchmark run.

Compare:

1. manual planning
2. planner pool
3. split-retry planning

Score:

- role selection correctness
- handoff completeness
- validation outcomes
- review changes
- hung/retry rate
- final confidence
- whether `.moondex/state` could represent the execution cleanly

This benchmark directly tests dynamic team composition without changing Moondex runtime mechanics.

## Recommendation

Add `moondex-team-designer` and `team-spec-schema.md` next. Keep it docs-first and read-only at first. Use it to produce benchmark specs and role-selection matrices before adding Rust automation.

Do not import upstream files wholesale. Keep upstream as a benchmark reference, and adapt only the durable concepts that strengthen Moondex's existing state-first runtime.

