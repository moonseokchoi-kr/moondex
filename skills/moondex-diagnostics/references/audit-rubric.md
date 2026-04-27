# Moondex Diagnostic Rubric

Score each principle from 0 to 5:

- `0`: absent or misleading
- `1`: mentioned but not operational
- `2`: partially implemented, high drift risk
- `3`: usable with manual care
- `4`: reliable and verified
- `5`: reliable, verified, and self-documenting

Convert to a 100-point score by averaging the selected principles and multiplying by 20.

Grades:

- `L1`: 0-39
- `L2`: 40-59
- `L3`: 60-74
- `L4`: 75-89
- `L5`: 90-100

## Principles

### P1. Runtime Source Of Truth

`.moondex/state` is consistently treated as the source of truth. cmux surfaces and terminal scrollback are evidence or transport only.

### P2. State Machine Consistency

Task, dispatch, mailbox, event, archive, and hook warning states are documented and enforced by code.

### P3. Role Boundary Clarity

Implementer, code reviewer, compliance reviewer, tester, orchestrator, task planner, and cmux operator responsibilities are explicit and non-overlapping.

### P4. Contract Validation

Role transfer, readiness, mailbox body schemas, hook wrappers, and plugin manifests have executable validation paths.

### P5. CLI Reproducibility

Core workflows can be replayed with `moondex` commands and JSON inputs without relying on hidden session state.

### P6. Event And Evidence Trail

Phase transitions, dispatch changes, mailbox consumption, archive creation, and cmux evidence have durable records.

### P7. Plugin Packaging

`.codex-plugin/plugin.json`, marketplace metadata, bundled skills, and install instructions agree with each other.

### P8. Drift Control

Names, paths, commands, and documented state contracts do not drift across README, docs, skills, hooks, and Rust code.

### P9. Verification Coverage

Tests and smoke commands cover both happy paths and failure paths for runtime behavior.

### P10. Recovery And Retention

Repair, retry, archive, malformed-state handling, and operator stops are documented and tested.

### P11. Scope Isolation

Moondex runtime work is separated from target product fixes, and role ownership boundaries are respected.

### P12. Self-Diagnostics

The plugin can audit its own skills, packaging, and documentation without depending on external memory.

## Severity

- `blocking`: prevents installation, execution, or source-of-truth integrity
- `high`: likely to cause incorrect orchestration or data loss
- `medium`: creates operator confusion or drift risk
- `low`: cleanup or clarity issue

