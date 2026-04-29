---
name: moondex-diagnostics
description: Use when auditing Moondex plugin quality, runtime readiness, skill drift, documentation consistency, source-of-truth discipline, or when planning remediation from a diagnostics report.
---

# Moondex Diagnostics

Diagnose Moondex as an agent-operated runtime and Codex plugin.

## Modes

- `Setup`: propose missing structure for a new Moondex-like repo or plugin.
- `Audit`: score the current repo against Moondex diagnostic principles.
- `Maintenance`: find drift, stale docs, broken command references, and packaging inconsistencies.
- `Remediate`: apply fixes from a prior diagnostic report only after the user agrees on scope.
- `Self`: audit this plugin and its skills using the same criteria.

## Read First

- `../../README.md`
- `../../.codex-plugin/plugin.json`
- `../../docs/execution/moondex-cli-plan.md`
- `../../docs/execution/WORK_TRACKER.md`
- `references/audit-rubric.md`

## Core Checks

Always check these before scoring:

```bash
python3 -m json.tool .codex-plugin/plugin.json >/dev/null
rg -n "codex-moon-[a-z]+|Codex Moon [A-Z][a-z]+|moon-[a-z]+|h[a]rness|H[a]rness|하.스" . -g '!target' -g '!.git' -g '!.moondex'
rg -n "moondex api list-events|inspect-hooks|phase_advanced|events.jsonl" docs crates README.md skills
```

For runtime-impacting changes, also run:

```bash
cargo fmt --check
cargo test -p moondex
cargo build -p moondex
```

## Audit Output

Return a concise Markdown report:

- target and mode
- depth profile used: `Quick`, `Standard`, or `Deep`
- overall score out of 100 and grade `L1` through `L5`
- strengths
- findings ordered by severity
- remediation roadmap
- verification commands actually run
- residual risks

## Depth Profiles

- `Quick`: use P1, P4, P8, and P9 from `references/audit-rubric.md`.
- `Standard`: use all diagnostic principles.
- `Deep`: Standard plus adversarial checks for false source-of-truth assumptions, stale examples, and missing failure-path verification.

## Remediation Rules

Do not edit files in `Remediate` mode until the user agrees on:

- target score or minimum acceptable grade
- files in scope
- verification commands
- whether docs-only fixes are acceptable

Keep remediation commits small and re-run the relevant audit checks after edits.
