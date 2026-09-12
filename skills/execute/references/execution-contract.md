# Execution contract v1

The script accepts JSON with `schema_version: 1`. Prepare the bundle as a reviewable artifact.
Identifiers use letters/digits/underscore/hyphen. Paths are project-relative, without traversal or symlinks.
An active run belongs to one worktree; a cancelled run with unresolved live resources prevents replacement.

## Bundle

| Field | Contract |
|---|---|
| feature, revision | Stable feature and unique baseline revision identifiers |
| goal, before, after | Observable user outcome |
| sources | List of `{source, text}` retaining actual agreements; do not invent message IDs |
| design, exclusions | Lists of agreed decisions and exclusions |
| criteria | `{id, requirement, input, action, expected, failure}` for every acceptance condition |
| inputs | Enumerated source roots/files including untracked outputs; exclude local runtime/logs/caches |
| policy | `{concurrency: 1, recovery_attempts: 2, time_limit: null, token_limit: null}` by default |
| verification | build/unit/integration/e2e entries with `required`; false requires an agreed `reason` |
| nodes | Contracts below; a single node is normal |
| gates, integration_gates | Gate definitions and IDs required on the integrated source snapshot |
| compound | `{enabled: false}` unless explicitly configured |

## Nodes and gates

Each node specifies `id`, `goal`, `executor` (`current` or `orca`), `inputs`, `write_scope`,
`outputs`, `depends_on`, `criteria`, `gates`, `locks`, `split_rationale`.
Inputs include its own output paths so verification detects later edits. Declare shared interfaces,
test data, lockfiles, ports and other shared resources. Orca nodes use the existing worktree;
model/effort may be explicitly selected, otherwise installed Codex defaults apply.

Each gate has `id`, `kind`, `criteria`, `argv`, optional `cwd` (default `.`), `format`, `min_tests`,
and `oracle: {argv, reason}`. Commands use argv, not an implicitly interpreted shell string.
Every command receives a fresh output path by replacing `{report}` in its argv.
Python gate scripts must be pinned in `definitions: {relative_path: sha256}`; include other test
definition dependencies there too. Pin external installed scripts in `tools: {absolute_path: sha256}`. Inline `python -c` assertions are fixed directly in the bundle.

- `json` report: `{tests: positive_integer, failures: 0, criteria: {criterion_id: true}}`.
- `junit` report: actual testcase elements, no failures/errors/skips, count at least min_tests.
- Positive command: exit 0, passing structured assertions, unchanged source snapshot.
- Negative oracle: exercise the named defect, emit nonzero collected assertions and a failing report,
  exit nonzero, and preserve the source snapshot. Missing command/report is not a successful oracle.

Choose assertions that observe user behavior. Review the mapping against criteria and demonstrate that
the negative oracle catches the defect; mere successful commands or agent-reported `verified` flags
cannot satisfy completion. Source/definition changes require appropriate invalidation or revision.

## Submissions and feedback

Implementation submission: `{node_id, attempt_id, bundle, action_key, summary, criteria_review}`.
Copy the assignment identifiers exactly. Each criteria_review value explains the observed behavior
against that criterion. Submit again only with identical content; corrections require another attempt.
An integration review uses `{kind: "integration_review", action_key, summary, criteria_review}`.

`feedback --kind implementation|verification|plan|baseline|ambiguous --nodes ... --reason ...`
registers scope and reason. Worker questions return AI judgment work; submit `{kind: "judgment", question_id, bundle, decision: "reply", text, summary}` to answer within the approved intent, or `decision: "request_user"` for an actual user decision. `--replacement` carries a new bundle for revision changes. Assertion weakening,
coverage removal, changed intent or expanded authority require baseline approval. Busy affected work must
settle first. Independent completed evidence is retained only when its inputs and contracts still match.

`answer --question ... --digest ... --text ... --source ... --decision ...` records an actual answer.
Decisions: `approve_revision`, `one_more_repair`, `confirmed_stopped`, or `continue`, according to the
saved question. Do not claim a process stopped without evidence or fabricate a user reply.
Cancellation records node and integration resources without killing them. Resolve each saved
`cancel_resources` question with observed stop evidence and `confirmed_stopped`; the run stays
cancelled. A new run is allowed only after every recorded resource is resolved.

## Compound

Configure enabled/required, root, rules, template, index, log, criteria_page, result_page, optional hub.
Paths except root are relative to that explicitly chosen destination; output pages must be under wiki/.
The returned record action includes context and its digest. Read the context before drafting.

Submit `{kind: "compound", context_digest, rules_digest, files: [{path, before_sha256, text}]}`.
rules_digest hashes canonical JSON of `{rules: rules_text, template: template_text}`. Include every
configured page/index/log/hub and match template frontmatter/sections. Preserve existing criteria by
appending revision history. Record results separately and include report/evidence references.
The script checks hashes, journals writes, preserves conflicts and resumes partial publication.
