# Codex Harness Parity — Verified Result

## Outcome

The trusted-local Codex baseline is complete for F1–F10. A deterministic sample
project runs through an opaque copied plugin installation with host hook,
plugin-root, Python-path, provider, credential, and session variables unset.
Controller state and SDD artifacts are written only in the consumer project.

The machine-readable criterion index is
`docs/sdd/result/2026-07-14-codex-harness-parity-evidence.json`.

## Observable acceptance

| Criterion | Result | Reproducible evidence |
|---|---|---|
| F1 | PASS | Manifest/skill/active-surface and recursive installed-runtime inventory tests |
| F2 | PASS | Separate start, status, resume, and advisory doctor processes; explicit SPEC → DESIGN → PLAN → EXECUTE → RESULT |
| F3 | PASS | Chrome 148 imports the same Panel module, observes visible Ready/false, coordinate-clicks its real button, and observes visible Complete/true; shared verify passes the same file, while no-op/browser/gate/default-branch/secret failures block |
| F4 | PASS | A schema-valid test-owned sole-writer simulation records validated worker/retry/escalation/resolution events; production controller blocks its incomplete task state |
| F5 | PASS | SAFE_FIX, justified REJECTED, ESCALATED, strict malformed/revision/audit-failure paths; convergence only after terminal disposition and passing build/lint/test |
| F6 | PASS | Canonical project-tier APPLY is separated from protected/traversal/absolute/symlink proposal-or-blocked outcomes |
| F7 | PASS | Healthy, not-initialized, and unavailable graph states; lexical fallback is marked approximate |
| F8 | PASS | Trusted-local raw evidence remains only in `.harness/audit/`; CLI/report/result surfaces are redacted; sync is `SKIPPED` |
| F9 | PASS | Offline train/held-out benchmark fixtures run under pytest without live evaluation |
| F10 | PASS | Host-neutral worker contracts, test-owned envelope/event simulation, and separately verified production controller transition authority |

## Validation

- `env -u HARNESS_HOOKS -u CODEX_PLUGIN_ROOT -u CLAUDE_PLUGIN_ROOT -u PYTHONPATH -u CODEX_SESSION_ID python3 -m pytest tests/e2e -q`
  — 10 passed.
- clean-environment `python3 -m pytest tests -q` — 270 passed.
- Exact linked criterion commands passed in this run: F1 37, F2 3, F3 12,
  F4 1, F5 8, F6 5, F7 1, F8 2, F9 14, and F10 4 test cases.
- Plugin and marketplace JSON, all public skill frontmatter, hook shell syntax,
  stop-pipeline Python compilation, and the plugin-creator validator passed.

No personal path, account, real credential, or real Compound destination is
used. The result and evidence index intentionally contain no raw review
credential value.

The rendered UI evidence is DOM behavior, computed visibility with nonzero
layout rectangles, and a real coordinate mouse click observed through bounded
Chrome CDP. It does not claim pixel or screenshot parity.

The sole-writer stage simulator used by T-11 is test-owned acceptance
infrastructure, not a production orchestrator event API. It validates worker
envelopes and renders the fixture task table deterministically; the production
controller then independently enforces that incomplete table when deciding
whether RESULT is reachable.

## Optional external limitation

Hosted CI required checks, remote head-SHA proof, provider comment posting,
remote export, and sharing were not executed. They are optional advisory
extensions outside the approved trusted-local baseline and do not block local
completion. Enabling any of them requires a separately configured destination,
authority, and sanitization contract.
