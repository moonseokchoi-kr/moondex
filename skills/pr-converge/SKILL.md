---
name: pr-converge
description: Record strict local review evidence and evaluate deterministic convergence.
---

# PR Converge

Run one explicit local pass at a time; do not start a background loop. Provide a complete strict review collection, evidence keyed by its revision keys, an append-only local audit location, and the configured local commands:

Resolve `<moondex-runtime>` to the absolute
`../sdd/runtime/moondex-runtime.py` path from this loaded skill directory, never
from the consumer cwd or a user-supplied installation path.

```sh
python3 <moondex-runtime> pr-converge --repository-root . --collection .harness/review-collection.json --evidence .harness/review-evidence.json --audit .harness/audit/review.jsonl --report .harness/reports/pr-convergence.json --build-command '["make", "build"]' --lint-command '["make", "lint"]' --test-command '["python3", "-m", "pytest", "-q"]'
```

The collection must satisfy the T-4 strict schema and have `complete: true`; ordinary JSON parsing, natural-language review output, and an LLM suggestion do not authorize a fix or rejection. Evidence is keyed by the adapter's versioned `rk1:` identity: a SHA-256 digest over canonical JSON containing source identity, revision identity, body hash, and the typed comment ID. Do not construct keys by joining fields with delimiters. Duplicate derived keys or ambiguous/conflicting audit identities fail before append. Evidence for each revision must state spec/design alignment, ownership, and verification availability. An aligned, owned request becomes `SAFE_FIX` only after the requested change and its passing validation are recorded. A conflicting or out-of-scope request becomes `REJECTED` only with a concrete conflict reason and an alternative; unknown or disputed evidence becomes `ESCALATED` for a user decision.

Resolve an existing escalation without changing the review revision by supplying `--resolutions <file>`. The strict resolution collection has `schema_version: 1`, `complete: true`, and a `resolutions` array. Each immutable user resolution repeats the exact `source_identity`, `revision_identity`, `body_hash`, and `comment_id`, declares `authority: USER`, chooses `SAFE_FIX` or `REJECTED`, and includes a reason plus evidence. `SAFE_FIX` also includes canonical repository-root, changed-file, and passing-validation evidence; `REJECTED` includes an alternative. The adapter appends an `escalation_resolution` event. A mismatch, missing justification, or conflicting second resolution fails closed; resubmitting the identical resolution is idempotent.

All relative paths are resolved from the canonical `--repository-root`, not the caller's working directory. Collection, evidence, and optional resolution inputs must be regular files physically contained by that root. The raw append-only audit must resolve below the repository's canonical `.harness/audit/` tree; `--report` must resolve below canonical `.harness/reports/`. Out-of-root paths, symlink escapes, audit/report equality, and existing same-inode aliases are rejected before the audit is appended, so a rendered report can never overwrite or alias raw evidence.

The append-only `.harness/audit/` record is trusted local reproduction evidence and may retain the literal request evidence. Stdout and `--report` are presentation/export surfaces: they render alignment, decision, reason, alternative or applied-fix evidence with credential values redacted. Redaction is structural and command-aware: sensitive dictionary keys, nested evidence, split credential flags such as `--password value`, joined flags such as `--password=value`, authorization headers, and Bearer values are masked while harmless arguments remain usable as diagnostic context. `CONVERGED` requires terminal dispositions plus successful configured build, lint, and test commands. Incomplete/malformed collection input, an audit failure, an invalid safe-fix record, or an open escalation remains `BLOCKED` or `NEEDS_HUMAN`. Re-run the same command after correcting the evidence or resolving the escalation; the snapshot and append-only audit history identify what resumes. Provider collection or posting may be mirrored outside this adapter, but it is non-authoritative: credentials, network, or posting failures cannot erase the local audit or alter local convergence.
