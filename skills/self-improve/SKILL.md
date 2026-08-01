---
name: self-improve
description: Process project-local learning entries with deterministic tier and benchmark safety checks.
---

# Self Improve

Run this workflow only when explicitly requested. It never runs automatically at the end of a task.

From the target repository, supply an append-only JSON array of learning entries and a JSON array of proposed changed paths:

Resolve `<moondex-runtime>` to the absolute
`../sdd/runtime/moondex-runtime.py` path from this loaded skill directory, never
from the consumer cwd or a user-supplied installation path.

```sh
python3 <moondex-runtime> self-improve --repository-root . --entries .harness/learning.json --cursor 0 --paths proposed-paths.json --train-improved --rollback-record change-123 --run-cap 3 --applied-count 0 --recurrence-confirmed --critic-passed
```

The JSON result includes `processed.next_cursor`; persist that cursor in the caller's project state only after any proposed change is safely recorded. Re-run with that cursor to resume, so already processed raw entries are not processed again. Explicit relative `--entries`, `--paths`, and `--config` values are resolved from the canonical `--repository-root`, never from the process working directory; each must be a regular file physically contained by that root. The adapter reads configuration from `<repository-root>/.harness/config.json` unless `--config` is explicit, and always passes that root through the shared T-7 canonical containment and protected-root policy; it has no path-policy fallback. A project-tier `APPLY` additionally requires a durable `--rollback-record`, available explicit `--run-cap`, no held-out regression, and both `--recurrence-confirmed` and `--critic-passed`. Any missing proof remains `PROPOSAL` or `BLOCKED`; this adapter never edits files or claims harness benchmark adoption. CLI JSON is a redacted presentation view; the caller-owned raw input remains unchanged. If no knowledge-sync configuration exists, `knowledge_sync.status` is `SKIPPED`, not a failure.
