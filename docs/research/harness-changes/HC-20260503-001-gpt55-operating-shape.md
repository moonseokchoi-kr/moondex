# HC-20260503-001: GPT-5.5 Operating Shape

```yaml
change_id: HC-20260503-001
title: GPT-5.5 Operating Shape
status: applied
created_at: 2026-05-03
applied_at: 2026-05-03
owner: orchestrator
target_components:
  - path: docs/execution/gpt-5.5-operating-shape.md
    component_type: policy
  - path: skills/moondex-implementation-workflow/SKILL.md
    component_type: skill
  - path: skills/moondex-runtime/SKILL.md
    component_type: skill
  - path: skills/moondex-wave-dispatcher/SKILL.md
    component_type: skill
change_type: add
linked_analysis_reports:
  - null
linked_commits:
  - null
```

## Motivation

- observed: OpenAI published GPT-5.5 prompt guidance for coding and agentic tasks, emphasizing outcome-first prompts, concise preambles, tool persistence, and explicit completion criteria.
- evidence:
  - `https://developers.openai.com/api/docs/guides/prompt-guidance`
  - prior Moondex runtime behavior needed stronger low-interruption and workflow-first rules.
- current contract gap: Moondex skills already enforce task/plan/wave/runtime order, but they do not explicitly distinguish GPT-5.5-friendly outcome-first execution from procedural narration.

## Inferred Root Cause

- category: `policy`
- hypothesis: Moondex skill prompts can become overly procedural unless they give the model a compact operating shape that preserves invariants while allowing shortest-safe-path execution.
- confidence: medium

## Intended Fix

- change: Add `docs/execution/gpt-5.5-operating-shape.md` and link it from the implementation workflow, runtime, and wave dispatcher skills.
- expected behavior: GPT-5.5 agents should satisfy Moondex invariants without producing unnecessary upfront plans or stopping after advisory guidance.
- must not change: `.moondex/state` remains runtime source of truth; planless dispatch and pre-readiness enqueue remain forbidden.
- scope boundary: This change is prompt/policy guidance only. It does not add full automatic evolution, auto-rollback, or rollout aggregation.

## Predicted Improvements

```yaml
predicted_fixes:
  - scenario_id: proceed-command-existing-sdd-repo
    expected_change: agent proceeds to missing task/plan/wave/runtime artifact resolution instead of returning implementation advice
    verification_signal: workflow skill reads gpt-5.5-operating-shape.md and still enforces task/plan/wave/runtime invariants
  - scenario_id: approved-wave-low-interruption
    expected_change: agent continues through reversible in-scope decisions with short progress updates
    verification_signal: low-interruption-policy.md remains linked and high-impact blocker rules remain intact
```

## Predicted Regressions

```yaml
predicted_regressions:
  - risk: outcome-first guidance could be misread as permission to skip mandatory readiness or runtime checks
    affected_surface: skill
    detection_signal: readiness validation, runtime enqueue, or dispatch occurs without task/plan/wave evidence
  - risk: shorter preambles could reduce operator visibility during long-running work
    affected_surface: user_flow
    detection_signal: fewer meaningful progress updates despite long tool-heavy execution
```

## Verification Plan

- commands:
  - `rg -n "gpt-5.5-operating-shape|GPT-5.5 Operating Shape|shortest safe path|outcome-first" README.md docs skills`
  - `python3 -m json.tool .codex-plugin/plugin.json`
  - `cargo fmt --check`
  - `cargo test -p moondex`
  - `scripts/doctor.sh --json`
- scenario: no live benchmark run in this patch.
- pass criteria: documentation links exist, version is 0.2.1, tests and doctor pass.
- fail criteria: skill links missing, markdown diff check fails, or runtime tests fail.

## Attribution Plan

- revisit after: first real Moondex run using GPT-5.5 on an SDD-style repo after `v0.2.1`.
- keep if: agent respects task/plan/wave/runtime invariants while reducing procedural narration and avoidable user questions.
- refine if: agent still stops at implementation advice or asks local implementation questions inside approved wave scope.
- revert if: agent skips readiness/runtime truth checks because the shortest-safe-path guidance is too permissive.
