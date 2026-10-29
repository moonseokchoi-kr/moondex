---
name: tdd-tidy-first
description: Apply explicitly chosen Kent Beck TDD and Tidy First rules to local project instructions, or execute one planned test on go under those rules. Adapt to JavaScript/TypeScript, Python, Rust, or C++ and existing tools; not a default for ordinary coding or quality setup.
---

# TDD and Tidy First

An opt-in, strict development workflow, independent of other Moondex skills and
requiring no runtime, hooks, or global configuration. Use only when the user
explicitly selects this workflow. General coding guidance belongs to
`project-guidelines`; configuring lint/type checks belongs to `code-quality-setup`.
Do not invoke either automatically or replace their defaults wholesale.

## Choose the requested operation

- **Apply/install instructions:** write or merge the requested project's local
  `AGENTS.md`. Applying this skill alone does not authorize product code, tests,
  a new `plan.md`, dependency/tool installation, or a development cycle.
- **Execute:** when the user says `go` under an explicitly selected or already
  installed workflow, process exactly one next unfinished test from `plan.md`.
  An application request containing a quoted `go` example is not execution.
- If the operation or target cannot be inferred, ask only for that missing choice;
  continue independent discovery. Never modify a reference project just because
  its instructions were supplied as an example.

## Discover the actual project

1. Read applicable `AGENTS.md` files, existing local changes, relevant project
   documentation, and `plan.md` if present. Preserve unrelated work and rules.
2. Inspect manifests, lockfiles, runtime/toolchain versions, maintained source and
   test files, runner configuration, build scripts, and CI. A manifest dependency
   alone does not establish a language's usage or a runnable test suite. In a
   mixed repository, identify the affected packages and cross-package checks.
3. Establish real commands and prerequisites for the full test suite, compiler or
   type checker, and linter. Identify long-running tests by existing project
   grouping or concrete evidence; state their exclusions explicitly. Do not
   quietly narrow "full suite" to a changed file or one package.
4. Read only the relevant idiom references:
   - [JavaScript / TypeScript](references/typescript.md)
   - [Python](references/python.md)
   - [Rust](references/rust.md)
   - [C++](references/cpp.md)
   These cover the same languages as Moondex quality setup, with a separate focus
   on code and test idioms. For another language, retain the common workflow,
   identify existing conventions and tools, and disclose the lack of a maintained
   language reference. Do not mechanically translate Rust syntax or invent a
   supported toolchain.
5. Separate found commands from commands actually executed. If only quality
   configuration exists, record that product tests are absent. Lint/type checking
   is not a behavioral test, and installing instructions does not create one.

## Apply local instructions without accumulation

Use the existing document's language, or the user's language for a new file.
Merge the common workflow below into an existing TDD/Tidy First section, plus only
the relevant language idioms and actual check commands/prerequisites. Keep the
installed guidance self-contained: it must not require this checkout, plugin
cache, or sibling skills to execute later. Do not copy example-app requirements.

Preserve existing rules. If a proposed rule conflicts with one, explain the
specific conflict and obtain the user's choice before replacing it, unless the
current request already resolves that conflict. Continue independent edits.
For general verification advice that permits evidence reuse or selective tests,
make the stricter full-suite frequency below an explicit exception only for the
selected TDD development workflow. Do not impose it on instruction-only edits,
ordinary writing, research, or unrelated work.

Merge equivalent content in place, including existing language review criteria;
do not append a second version on reapplication. Record missing tests or commands
as limitations rather than fabricating commands, scaffolding tests, or generating
a test plan. Read the final file and diff for conflicts, duplicate rules, lost
content, and whether another application would produce no additional content.
Instruction-only edits require document verification, not product-suite execution.

## Common development workflow to install or execute

### One go, one planned test

- Always read and follow `plan.md` for development. On each `go`, select the first
  unfinished test (`- [ ]`) from top to bottom. Do not reorder it, complete a
  second item, or implement future items in that cycle.
- If `plan.md` is absent, has no unfinished tests, or the next item is too vague
  to identify a test's observable behavior, report the gap and stop dependent
  development. Do not invent features, tests, or a plan. Planning is a separate
  user request, not an implicit part of `go` or instruction installation.
- Check the existing test baseline before changes. An existing failure must not
  be relabeled as the new test's Red. If it prevents a trustworthy cycle, report
  it and resolve only within the authorized scope before proceeding.

### Red, Green, Refactor

- **Red:** write the smallest single failing test for the selected behavior. Name
  it for an observable outcome and make the failure explain the missing behavior.
  Execute it and confirm that it fails for the intended behavioral reason before
  implementing product code. Missing tools, broken imports, invalid test syntax,
  or environment/configuration errors do not establish Red. Repair prerequisites
  only within scope, or report the blocker.
- **Green:** implement only enough code to pass that test and preserve existing
  behavior. Do not anticipate later tests, add speculative abstractions, or
  weaken the assertion merely to obtain a passing result.
- **Refactor:** only after tests are Green, consider necessary duplication removal
  or clarity improvements. Use one named, appropriate refactoring at a time
  (for example, Rename or Extract Function) and test after every step. Skip this
  phase's edits when no useful cleanup is needed.
- At **every Red confirmation, Green confirmation, and individual refactoring
  step**, run the full test suite excluding only identified long-running tests.
  A focused test run may aid diagnosis but does not replace that full run. At Red,
  confirm the intended new failure and no unexpected regressions; Green and
  refactoring require all included tests to pass. Do not reuse old evidence to
  skip these development checks. Report the excluded commands/suites and the
  unverified behavior, including unavailable checks; never imply they passed.
- Mark only the selected `plan.md` item `- [x]` after the test, included full suite,
  and required verification pass. A blocked or incomplete item stays unfinished.
  Disclose any agreed long-running exclusions with completion; this does not
  satisfy the stricter commit gate below. Stop after this item.

### Tidy First and code design

- Distinguish **structural** changes (rename, extract, move without changing
  behavior) from **behavioral** changes (add or correct behavior). If both are
  needed, first establish a Green baseline, make necessary structural changes,
  and run tests before and after to verify behavior preservation. Then begin the
  failing test and behavioral change. Do not refactor while Red. Cleanup after
  Green is another separate structural change.
- Prefer the simplest solution satisfying the current requirement: clear names
  and structure, small functions with one responsibility, explicit dependencies,
  minimal mutable state and side effects, and removal of meaningful duplication.
  Keep real input/error handling. Do not force a functional abstraction or create
  needless refactoring merely to demonstrate the workflow.

### Commit boundaries

- When committing is authorized, use small commits with one logical purpose.
  Never mix structural and behavioral changes in one commit. Expose the kind in
  the message, such as `structural: extract parser` or `behavioral: reject empty input`,
  while respecting any compatible existing message convention. Track the two
  kinds separately from the start so they remain reviewable and separable.
- Commit only after **all tests pass** and compiler/type-checker and linter
  warnings/errors are resolved. Long-running tests excluded during development
  still need to pass before commit. If tests/checks cannot run, or baseline
  warnings/failures remain, report them and do not claim commit readiness. Do not
  suppress diagnostics or rewrite unrelated code to bypass this gate.
- These rules constrain commits; they do not require an automatic commit or grant
  permission to push, publish, deploy, modify plugin caches, install global
  configuration/hooks, or change unrelated projects.

## Finish with evidence

For application, report the instruction file, merged rules, detected languages and
real tools, unresolved conflicts, and missing commands. For execution, report the
one selected item, actual Red/Green and refactoring results, commands/scope,
exclusions, completion status, and any commit limitation. Distinguish instruction
installation, packaging checks, and demonstrated product behavior. Neither prose
nor a discovered command proves future model compliance or test success.
