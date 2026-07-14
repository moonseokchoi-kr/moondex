---
name: pr-converge
description: Evaluate normalized PR signals through a deterministic convergence state machine.
---

# PR Converge

Collect conversation, inline, and review-body comments through an explicit hosting adapter. Normalize them with `harness_core.pr`; only `CONVERGED` with green CI, no actionable signals, and no escalations is complete. Authentication and network failures return `BLOCKED` with command evidence.
