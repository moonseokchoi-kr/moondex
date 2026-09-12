---
name: execute
description: Execute an agreed task or DAG with immutable requirements, script-owned progress, actual verification and resumable evidence. Use for delegated implementation and continuation after requirements are clear.
---

# Delegated execution

Agree on observable outcomes, scope and acceptance criteria before implementation.
Preparation can be a conversation or any useful documents; do not impose phase documents.
Read [the execution contract](references/execution-contract.md) when preparing or revising a bundle.

Resolve `<moondex-runtime>` to `../sdd/runtime/moondex-runtime.py` relative to this loaded skill.
The directory name is a retained common launcher location, not an SDD execution mode.
Never require a consumer checkout cwd or PYTHONPATH.

```bash
python3 <moondex-runtime> execute --root <project-root> status
python3 <moondex-runtime> execute --root <project-root> prepare --file <bundle.json>
python3 <moondex-runtime> execute --root <project-root> approve --digest <returned-digest> --quote <actual-user-decision> --source <actual-source>
python3 <moondex-runtime> execute --root <project-root> advance
python3 <moondex-runtime> execute --root <project-root> submit --file <submission.json>
python3 <moondex-runtime> execute --root <project-root> resume
```

Use safely quoted argv for decision text. Approval records require actual user authorization
of the displayed bundle; never synthesize a decision or reuse approval for a changed baseline.
Status is read-only. Resume reconciles durable execution and may continue already-authorized work.

The current AI implements and analyzes. The script selects and durably assigns the next work.
Submit only the assigned node/attempt/bundle/action_key with a summary and criterion-by-criterion
review explaining the observed behavior. For repair work, inspect the actual failure receipt,
reproduce the defect, repair it and resubmit. Worker reports never replace script-run gates.
Do not edit `.moondex/STATE.json`, objects or event history. Invoke submit/advance instead.

- `ACTION`: perform the returned scoped implementation, diagnosis, integration review or record drafting.
- `WAITING_PROCESS`: continue rolling advance calls. Output silence and elapsed time are not failure.
- `WAITING_USER` / `RECOVERY_REQUIRED`: show the exact saved question, attempts, evidence and impact.
  Continue only unaffected authorized work. Link answers to the question and revision.
- `COMPLETED`: report the exact result and evidence. Do not automatically improve policy or invoke self-improve.
- `STATE_BUSY`: another script writer owns the update; repeat the same operation after its return.

Before/after substantial work and at tool wait points, advance to collect results. Do not invent
next-node choices, spawn role teams by default, or promise execution after this AI session ends.
Use Orca only for script-assigned parallel work with real Task/Dispatch provenance. Read its installed
version guide before the first live use. Missing authority or unknown launch outcome is recovery work,
not permission to create another worker. Preserve live worker/test ownership on resume.

No total-time or token cutoff applies. Required builds and tests run to an actual result.
Two failed automatic repairs require an explicit saved decision; waiting and session continuation
do not consume repairs. Baseline changes require new user agreement; same-baseline plan changes and
verification repairs must preserve intent, coverage and the attempt history.

Compound is opt-in. When requested, read its rules/template/index, draft separate criteria and result
records, and submit the configured wiki files with original hashes. Never write raw or overwrite a
concurrent user edit. Required recording is part of completion; optional recording failure is reported.
