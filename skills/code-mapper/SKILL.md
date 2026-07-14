---
name: code-mapper
description: Map code impact using a graph probe or an explicit approximate grep fallback.
---

# Code Mapper

Classify supplied graph-probe output as `healthy`, `not_initialized`, or `unavailable`. For either non-healthy state, use `harness_core.code_mapper.grep_fallback` and label all results approximate. Reports are ephemeral and do not modify project state.
