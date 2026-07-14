---
name: self-improve
description: Process project-local learning entries with deterministic tier and benchmark safety checks.
---

# Self Improve

Read `.harness/config.json` and project-local learning input. Use `harness_core.learning` to process each entry once. Project-tier changes require rollback evidence; harness-tier changes always return `PROPOSAL`. When knowledge sync is not configured, record `SKIPPED` and continue.
