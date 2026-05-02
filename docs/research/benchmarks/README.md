# Moondex Research Benchmarks

This directory is for AHE-lite benchmark runs and analysis artifacts.

Moondex benchmarks are not a second runtime state. Runtime truth remains under `.moondex/state`. Benchmark artifacts summarize, compare, and interpret runtime outcomes so Moondex harness changes can be grounded in evidence.

## When To Create A Benchmark Run

Create a benchmark run when evaluating Moondex harness behavior, especially:

- short proceed commands such as `진행해줘`, `continue`, or `implement`
- task creation completeness
- all-task planning quality
- wave grouping and parallel dispatch decisions
- low-interruption behavior inside an approved wave
- high-impact blocker handling
- dispatch, ACK, retry, and cmux evidence handling
- role transfer, review, compliance, and tester phase transitions
- bootstrap, doctor, setup, or plugin discovery behavior
- changes to skills, policies, validators, runtime CLI, hooks, or plugin packaging

Do not create benchmark runs for ordinary target product implementation unless the run is explicitly evaluating Moondex harness behavior.

## Directory Layout

Use one directory per run:

```text
docs/research/benchmarks/<run-id>/
  README.md
  request-summary.md
  scenario-matrix.tsv
  state-refs.md
  analysis/
    AR-YYYYMMDD-001.md
  harness-changes/
    HC-YYYYMMDD-001.md
  final-report.md
```

Use stable run IDs:

```text
BR-YYYYMMDD-001-short-name
```

## Required Run README

Each run should include:

```yaml
run_id: BR-YYYYMMDD-001-short-name
created_at: YYYY-MM-DD
purpose: what Moondex behavior is being evaluated
target_repo: path or URL
moondex_commit: commit sha
runtime_state_roots:
  - .moondex/state or snapshot path
scenarios:
  - scenario_id
status: planned | running | analyzed | closed
```

## Scenario Matrix

`scenario-matrix.tsv` should use these columns:

```text
scenario_id	description	expected_behavior	actual_behavior	outcome	analysis_report	harness_change_manifest
```

Allowed outcomes:

- `pass`
- `partial`
- `fail`
- `blocked`
- `inconclusive`

## State References

`state-refs.md` should list the durable evidence used by the run:

- commit hashes
- `.moondex/state` snapshot paths
- event IDs or `list-events` command output references
- mailbox message IDs
- evidence IDs
- hook warnings
- command outputs
- relevant source documents

Do not paste large raw logs into benchmark reports. Store or cite durable artifacts and summarize only the relevant observations.

## Analysis Reports

Write execution analysis reports using:

- `docs/contracts/execution-analysis-report-schema.md`

An analysis report should classify what happened and decide whether a harness change manifest is warranted.

## Harness Change Manifests

Write harness change manifests using:

- `docs/contracts/harness-change-manifest-schema.md`

Use manifests only for non-trivial Moondex harness changes. Small typo fixes or source link fixes do not need a manifest.

## Final Report

`final-report.md` should answer:

- which scenarios passed or failed
- which failures are product/repo issues versus Moondex harness issues
- which harness changes were proposed or applied
- what regressions remain plausible
- which scenarios should be rerun after changes
- whether any contract, skill, validator, or runtime behavior should be tightened

## AHE-Lite Boundary

This benchmark directory supports evidence-based harness improvement. It does not implement full automatic evolution.

Out of scope for AHE-lite:

- automatic benchmark scheduling
- automatic skill or runtime edits
- automatic rollback
- pass@1 aggregation across repeated rollouts
- model/provider comparison
- hidden state outside repo artifacts

Those can be added later only after the report and manifest contracts prove useful in real Moondex runs.
