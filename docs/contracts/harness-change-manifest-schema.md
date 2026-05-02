# Harness Change Manifest Schema

This document defines the AHE-lite contract for recording Moondex harness changes.

A harness change is a change to the agent operating environment, not a target product feature. Examples include skill instructions, runtime policy documents, CLI behavior, validator rules, hook contracts, bootstrap scripts, plugin metadata, and diagnostic rubrics.

## Purpose

Moondex should not accumulate harness changes only as informal rationale in chat or commit messages. Every non-trivial harness change should state:

- what observed failure or opportunity motivated it
- which harness component it changes
- what behavior it is expected to improve
- what regression it might introduce
- how the next run should judge whether it worked

This is not a full automatic evolution loop. It is the minimum evidence contract needed before Moondex can safely add automated attribution later.

## Storage

Recommended location:

```text
docs/research/harness-changes/<change-id>.md
```

Use stable IDs:

```text
HC-YYYYMMDD-001
```

Do not store this under `.moondex/state`. Runtime truth stays in `.moondex/state`; harness change manifests are research and governance artifacts that may reference runtime state, events, mailbox messages, evidence records, benchmark runs, or commits.

## Required Metadata

```yaml
change_id: HC-YYYYMMDD-001
title: short description
status: proposed | applied | kept | reverted | superseded
created_at: YYYY-MM-DD
applied_at: YYYY-MM-DD | null
owner: orchestrator | diagnostics | human | other
target_components:
  - path: skills/moondex-runtime/SKILL.md
    component_type: skill | runtime_cli | policy | validator | hook | bootstrap | plugin_manifest | diagnostic | documentation
change_type: add | modify | remove | split | tighten | relax
linked_analysis_reports:
  - AR-YYYYMMDD-001
linked_commits:
  - commit sha or null
```

## Required Sections

### 1. Motivation

Required:

- observed failure, friction, or repeated pattern
- evidence references
- why existing task, plan, wave, runtime, or diagnostic contracts did not already prevent it

Evidence references should point to durable artifacts when possible:

- `.moondex/state/events.jsonl` event IDs
- mailbox message IDs
- evidence IDs from `.moondex/state/evidence/index.json`
- benchmark run paths
- test output
- commit hashes
- source document links

### 2. Inferred Root Cause

Required:

- concise root cause hypothesis
- affected Moondex layer
- confidence: `low | medium | high`

Use one or more component categories:

- `skill_trigger`
- `planning_contract`
- `wave_decision`
- `runtime_state`
- `role_contract`
- `validator`
- `hook`
- `bootstrap`
- `diagnostics`
- `policy`
- `documentation`

### 3. Intended Fix

Required:

- exact component changes
- behavior that should change
- behavior that must not change
- scope boundary

### 4. Predicted Improvements

Required:

```yaml
predicted_fixes:
  - scenario_id: optional benchmark or runtime scenario ID
    expected_change: concrete observable improvement
    verification_signal: command, event, mailbox output, or report field
```

Examples:

- short proceed command creates a full task set instead of giving implementation advice
- approved wave continues without low-level user questions
- missing cmux surface stays pending instead of being treated as delivered

### 5. Predicted Regressions

Required:

```yaml
predicted_regressions:
  - risk: concrete behavior that might get worse
    affected_surface: skill | cli | validator | user_flow | runtime_state
    detection_signal: how the regression will be noticed
```

Every policy-tightening change must include at least one regression risk. If none is known, write `unknown` and explain why.

### 6. Verification Plan

Required:

- focused verification commands
- benchmark scenario to rerun, if available
- manual inspection points
- pass/fail criteria

Docs-only changes may use `rg` checks and schema/example inspection. Runtime-impacting changes should include `cargo fmt --check`, `cargo test -p moondex`, and `scripts/doctor.sh --json`.

### 7. Attribution Plan

Required:

- when to revisit the change
- what evidence should decide keep/refine/revert
- who or what is allowed to apply the decision

Valid attribution decisions:

- `keep`: predicted fixes observed and no material regression
- `refine`: partial improvement or manageable regression
- `revert`: no improvement or unacceptable regression
- `defer`: insufficient evidence

## Minimal Template

````markdown
# HC-YYYYMMDD-001: Title

```yaml
change_id: HC-YYYYMMDD-001
title: Title
status: proposed
created_at: YYYY-MM-DD
applied_at: null
owner: orchestrator
target_components:
  - path: path/to/component
    component_type: skill
change_type: modify
linked_analysis_reports:
  - AR-YYYYMMDD-001
linked_commits:
  - null
```

## Motivation

- observed:
- evidence:
- current contract gap:

## Inferred Root Cause

- category:
- hypothesis:
- confidence:

## Intended Fix

- change:
- expected behavior:
- must not change:
- scope boundary:

## Predicted Improvements

```yaml
predicted_fixes:
  - scenario_id:
    expected_change:
    verification_signal:
```

## Predicted Regressions

```yaml
predicted_regressions:
  - risk:
    affected_surface:
    detection_signal:
```

## Verification Plan

- commands:
- scenario:
- pass criteria:
- fail criteria:

## Attribution Plan

- revisit after:
- keep if:
- refine if:
- revert if:
````

## Non-Goals

- This schema does not apply to ordinary target product feature changes unless they modify Moondex harness behavior.
- This schema does not authorize automatic edits, automatic rollback, or benchmark execution.
- This schema does not replace `.moondex/state`, `events.jsonl`, mailbox records, or evidence records.
