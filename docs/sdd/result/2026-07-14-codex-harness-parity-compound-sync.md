# Codex Harness Parity — Knowledge Sync

## Status

`SKIPPED`

Phase 5 knowledge synchronization was not run because project-local opt-in is
unset/disabled. The expected `.harness/config.json` is absent, so there is no
enabled `knowledge_sync` configuration and none of its required fields can be
resolved:

- `destination`
- `credential_source`
- `retention_policy`

This is the required F8 behavior, not an implementation failure. Phase 4
completion and its verified F1–F10 result remain valid.

## No-write evidence

- Configuration inspection was limited to project-local SDD artifacts,
  `.harness/state/pipeline.json`, and the presence check for
  `.harness/config.json`.
- No external destination was resolved.
- No external repository, wiki, provider, shared location, or export target was
  inspected, read, created, or mutated.
- No credential source was resolved or read.
- No source snapshot or wiki update was attempted.
- The only Phase 5 writes are this local report and the project-local learning
  buffer at
  `.harness/state/sdd/codex-harness-parity/2026-07-14-codex-harness-parity/learning-buffer.md`.

## How to opt in later

Create a project-local `.harness/config.json` and explicitly enable sync with
all three required fields. Placeholder values must be replaced by
project-approved concrete values before execution:

```json
{
  "schema_version": 1,
  "knowledge_sync": {
    "enabled": true,
    "destination": "<explicit approved destination>",
    "credential_source": "<explicit approved credential reference>",
    "retention_policy": "<explicit approved retention policy>"
  }
}
```

A later Phase 5 run must validate all three fields, destination authority, and
the applicable redaction policy before resolving or writing the destination.
No destination is inferred from a user account, home directory, or machine
convention.
