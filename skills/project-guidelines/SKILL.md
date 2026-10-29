---
name: project-guidelines
description: Create or update a project's local AGENTS.md with concise coding and verification guidelines adapted to its existing rules and actual checks. Use when the user asks to apply these principles to a project; not for ordinary coding tasks or global settings.
---

# Project Guidelines

Write project-local instructions that improve implementation decisions without adding a staged workflow. This skill is self-contained and requires no Moondex runtime, hooks, or other skills.

Strict TDD/Tidy First is a separate explicit choice (`tdd-tidy-first`). Do not add it automatically. Preserve already selected local TDD rules, including their test frequency, as scoped exceptions to the general verification guidance below.

## Apply to the requested project

- Use the project or directory named by the user; otherwise use the current project's root. Ask only when the target is ambiguous. Apply to a subdirectory only when that narrower scope was requested.
- Read the applicable existing instructions and target `AGENTS.md` before editing. Inspect project manifests, CI, and relevant documentation to identify actual verification commands. Do not treat existing tests alone as proof of the intended behavior.
- Preserve project rules, user edits, language, and unrelated content. Merge equivalent principles into existing sections rather than duplicating them. Where a proposed principle conflicts with an existing rule, explain the conflict and obtain the user's choice before replacing that rule; continue independent edits if possible.
- Create `AGENTS.md` if absent. Otherwise add or update a concise coding-and-verification section, using the draft below as a starting point. Adapt it to the project rather than copying conflicting or redundant instructions.
- Scope the generated rules to software implementation, code review, refactoring, debugging, and behavior verification. Working inside a code repository does not turn ordinary writing, research, or brainstorming into a coding task. Mention any inherited global coding rules that remain in effect; a local section alone cannot remove their broader scope.
- Write only the requested local instruction file(s). Do not edit global instructions, install hooks, initialize execution state, remove existing skills, or apply the guidelines to other projects.

## Draft principles

Use the existing document's language; use the user's language for a new document.

```markdown
## Coding and verification

Apply these rules to software implementation, code review, refactoring, debugging, and behavior verification. Ordinary writing, research, and brainstorming do not require the coding workflow below.

- Before substantial changes, identify the intended observable result, current behavior, and the gap. State material assumptions and tradeoffs. Ask when uncertainty changes scope or correctness; resolve routine reversible choices using project context.
- Define important behavior by what actually happens end to end. Designs, architecture labels, schemas, plans, and existing tests do not by themselves prove that behavior. When behavior feels wrong, check the intent-versus-outcome gap before tuning prompts or adding supporting structure.
- Choose the simplest solution that meets the request. Avoid speculative features, one-use abstractions, unrequested configurability, and defensive code for implausible scenarios. Retain error handling required by real inputs and dependencies.
- Change only what the request requires. Follow existing conventions, preserve unrelated edits, and remove unused code created by your changes. Mention unrelated cleanup opportunities without expanding scope.
- Define observable success criteria. For multi-step work, give a brief plan tied to those criteria; small tasks need no formal plan or mandatory document phases.
- Verify the changed behavior with checks appropriate to its impact. For a bug, reproduce the original symptom and confirm the fix; where a regression test is warranted, establish that it fails without the fix. Do not add tests that merely mirror implementation details or require tests for every low-impact edit.
- If a test confirms a reduced or mistaken interpretation of the requested outcome, identify that mismatch and replace or supplement the test. Verify the core user flow before investing in structure intended to support it.
- Before claiming a fix, passing tests, or completion, inspect actual verification results. A changed diff, another agent's report, or a clean linter alone does not prove the requested behavior. Report what was checked, its result, and any unverified scope.
- Reuse verification evidence when the checked code, relevant environment, and requirements remain unchanged. Rerun affected checks after changes, new failures, or unresolved concerns; do not repeat successful checks merely to provide a status update.
- Stop when the requested outcome and relevant checks are satisfied. If repeated attempts produce the same failure without new evidence or progress, report the blocker and the decision or information needed instead of continuing blind retries. Let legitimately running checks finish; elapsed time alone is not a failure.
```

## Project checks

This skill documents existing checks; it does not configure lint policy or install tools. Language-specific quality setup is a separate task handled by `code-quality-setup` when requested. Do not invoke it automatically or duplicate its language references here.

Include a short list of verified existing commands only when it adds useful project context. Identify what each command checks and any known prerequisites. Do not invent commands or turn every listed command into a mandatory check for every edit. If a command was found but not run, label that distinction in the report. If no suitable command exists, record the limitation instead of creating a test framework as part of this task.

## Verify the instruction edit

Read the final file and its diff. Confirm unrelated instructions remain intact, equivalent rules are not duplicated, and another application would produce no additional change. Check that the result introduces no fixed review rounds, unconditional full-suite reruns, or global dependencies. An instruction-only edit does not require running the product's full suite.

Report the target file, the principles added or merged, and unresolved conflicts or missing verification commands. Distinguish checking the document from proving how a future model will behave. Do not claim the project tests passed unless they actually ran.

## Sources

Adapted principles, not a verbatim installation of upstream skills:

- [Karpathy Guidelines](https://github.com/multica-ai/andrej-karpathy-skills/blob/main/skills/karpathy-guidelines/SKILL.md): simplicity, limited changes, explicit assumptions, and verifiable goals.
- [Verification Before Completion](https://github.com/obra/superpowers/blob/main/skills/verification-before-completion/SKILL.md): evidence before completion claims. This adaptation permits reuse of still-valid evidence.

Do not fetch these sources on every application; the instructions above are sufficient. Response styles and Anti Slop rules are separate choices and are not included implicitly.
