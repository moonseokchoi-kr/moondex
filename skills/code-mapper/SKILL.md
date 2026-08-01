---
name: code-mapper
description: Map code impact using a graph probe or an explicit approximate grep fallback.
---

# Code Mapper

Run this workflow explicitly before implementation or review when impact is unclear. Give it a symbol and, if available, a graph probe command:

Resolve `<moondex-runtime>` to the absolute
`../sdd/runtime/moondex-runtime.py` path from this loaded skill directory, never
from the consumer cwd or a user-supplied installation path.

```sh
python3 <moondex-runtime> code-mapper --root . --symbol target --graph-command '["your-graph-cli", "status"]'
```

The adapter classifies graph output as `healthy`, `not_initialized`, or `unavailable`. A healthy graph command may return a JSON object with `entry_points`, `candidate_calls`, and `impact_scope` arrays; these facts are preserved without inference. Missing or malformed fields are reported as limitations. Every other outcome, including a missing executable, authentication failure, or network failure, returns actionable `BLOCKED` status with redacted command evidence and an explicitly approximate grep report under `fallback`. Fallback matches are lexical candidates, not proven call relationships, and therefore include limitations instead of fabricated entry points. The report is stdout-only and ephemeral; do not persist it as project state. Re-run the command when graph availability changes.
