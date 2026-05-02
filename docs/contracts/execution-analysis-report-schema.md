# Execution Analysis Report Schema

This document defines the AHE-lite contract for analyzing Moondex execution outcomes.

An execution analysis report turns raw runtime observations into a concise, evidence-backed explanation of what happened. It is the input that can later justify a harness change manifest.

## Purpose

Moondex already records runtime state, events, mailbox messages, dispatch requests, hook warnings, and cmux evidence. This schema defines how to distill those artifacts into a report that can answer:

- what succeeded or failed
- which evidence supports that conclusion
- which Moondex layer likely caused the issue
- whether a harness change is justified
- what benchmark or runtime scenario should be rerun

## Storage

Recommended location for benchmark-backed reports:

```text
docs/research/benchmarks/<run-id>/analysis/<analysis-id>.md
```

Recommended location for one-off Moondex self-analysis:

```text
docs/research/execution-analysis/<analysis-id>.md
```

Use stable IDs:

```text
AR-YYYYMMDD-001
```

Do not store analysis reports under `.moondex/state`. Reports may reference runtime state, but they are interpreted research artifacts rather than source-of-truth runtime records.

## Required Metadata

```yaml
analysis_id: AR-YYYYMMDD-001
run_id: optional benchmark run ID
subject: short description
created_at: YYYY-MM-DD
analyzer: orchestrator | diagnostics | human | other
scope: single_task | wave | benchmark_run | plugin_self_check | target_repo_run
source_refs:
  commits:
    - commit sha or null
  state_roots:
    - .moondex/state or snapshot path
  event_ids:
    - event ID
  mailbox_message_ids:
    - message ID
  evidence_ids:
    - evidence ID
  commands:
    - command that produced relevant output
outcome: success | partial | failure | inconclusive
confidence: low | medium | high
```

## Required Sections

### 1. Executive Summary

Required:

- one paragraph summary
- final outcome
- primary cause or reason for inconclusive result

### 2. Scenario Or Task Context

Required:

- user request or benchmark scenario
- expected Moondex behavior
- actual Moondex behavior
- task/plan/wave/runtime phase involved

### 3. Evidence Index

Required:

```yaml
evidence:
  - ref_type: event | mailbox | evidence_file | command_output | commit | document
    ref_id: durable ID or path
    relevance: why this ref matters
```

The report must not rely on terminal scrollback alone. If terminal output matters, capture or cite the corresponding evidence record.

### 4. Observed Timeline

Required:

- ordered events or actions
- where the behavior diverged from expectation
- whether the divergence was recovered

### 5. Failure Or Success Classification

Use one or more categories:

- `skill_trigger_miss`: relevant skill did not activate
- `task_creation_gap`: task set was missing, incomplete, or skipped
- `planning_gap`: executor-ready plan was missing or weak
- `wave_decision_gap`: dependency, ownership, or parallelism decision was wrong
- `readiness_gate_gap`: invalid work reached runtime or valid work was blocked
- `dispatch_transport_failure`: wake-up transport or surface delivery failed
- `role_contract_failure`: role output violated contract or omitted required fields
- `over_interruption`: user was asked for a low-level decision inside approved scope
- `under_interruption`: Moondex continued when high-impact operator input was required
- `verification_gap`: checks were missing, weak, or not connected to acceptance criteria
- `state_drift`: terminal, docs, or mailbox diverged from `.moondex/state`
- `bootstrap_packaging_gap`: install, setup, doctor, or plugin discovery failed
- `diagnostic_gap`: existing diagnostics did not expose the issue
- `no_issue`: behavior matched the expected contract

### 6. Root Cause Hypotheses

Required:

```yaml
root_causes:
  - category: one classification category
    hypothesis: concise explanation
    affected_component:
      path: optional path
      component_type: skill | runtime_cli | policy | validator | hook | bootstrap | plugin_manifest | diagnostic | documentation
    confidence: low | medium | high
    supporting_refs:
      - evidence ref
    contradicting_refs:
      - evidence ref or none
```

### 7. Harness Change Recommendation

Required:

- `none`: no harness change needed
- `manifest_recommended`: write a harness change manifest before editing
- `direct_fix_ok`: small docs or typo fix, no manifest required
- `needs_more_evidence`: rerun or capture more data first

If `manifest_recommended`, include:

```yaml
recommended_manifest:
  target_components:
    - path:
      component_type:
  expected_improvement:
  regression_risk:
  verification_signal:
```

### 8. Follow-Up

Required:

- next command or scenario to run
- whether this should become a benchmark case
- whether existing contracts should be tightened

## Minimal Template

````markdown
# AR-YYYYMMDD-001: Title

```yaml
analysis_id: AR-YYYYMMDD-001
run_id: null
subject: Title
created_at: YYYY-MM-DD
analyzer: diagnostics
scope: plugin_self_check
source_refs:
  commits:
    - null
  state_roots:
    - .moondex/state
  event_ids: []
  mailbox_message_ids: []
  evidence_ids: []
  commands: []
outcome: inconclusive
confidence: medium
```

## Executive Summary

## Scenario Or Task Context

## Evidence Index

```yaml
evidence: []
```

## Observed Timeline

## Failure Or Success Classification

## Root Cause Hypotheses

```yaml
root_causes: []
```

## Harness Change Recommendation

## Follow-Up
````

## Non-Goals

- This schema does not replace runtime events, mailbox records, hook warnings, or evidence records.
- This schema does not require every normal implementation task to produce an analysis report.
- This schema does not authorize automatic harness edits.
