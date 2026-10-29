---
name: code-quality-setup
description: Set up or refine project-local lint, type checks, and concise code review guidance for TypeScript, Python, Rust, or C++. Use when the user requests code quality setup or adaptation of anti-slop rules, not for ordinary coding, prose cleanup, or UI styling.
---

# Code Quality Setup

Leave the requested project with useful, runnable checks and a small set of review criteria that those checks cannot enforce. Preserve its conventions. This is a setup skill, not a recurring review pipeline; it needs no Moondex runtime or other skill.

Strict TDD/Tidy First belongs to the separately selected `tdd-tidy-first` skill. Do not install it automatically or weaken an existing local TDD workflow; quality setup alone does not authorize a test plan or product development.

## Scope and discovery

- Use the user's target project, otherwise the current project root. Read its applicable instructions and existing local changes before editing. Do not change global settings or apply policy to other projects.
- Inspect manifests, lockfiles, toolchain versions, lint/type-check configuration, build scripts, and CI. Identify maintained source directories and generated or vendored code. Read only the language references needed by those directories:
  - [TypeScript / JavaScript](references/typescript.md)
  - [Python](references/python.md)
  - [Rust](references/rust.md)
  - [C++](references/cpp.md)
- Ground setup in an actual unwanted pattern, user-selected policy, or existing diagnostic. If none is specified, use a small correctness baseline from the existing toolchain. Do not describe personal style preferences as correctness defects.
- Check the installed tool's help, version, and effective configuration before choosing flags or rules. Consult official documentation when local evidence cannot establish compatibility. References provide decision criteria, not a requirement to install every tool mentioned.

## Configure only what is useful

- Reuse the project's linter, formatter, type checker, package manager, and check commands. Merge configuration; preserve exclusions, overrides, existing strictness, lockfile choices, and user edits. Do not introduce competing tools for the same job.
- When setup was requested and tooling is absent, add the smallest suitable project-local development configuration and dependency consistent with its toolchain. If a usable check requires an unavailable toolchain, a material new dependency choice, or information about the supported build, report that limitation or ask the specific unresolved question. Continue independent work. If the user requested guidance only, make no dependency or config changes.
- Select rules by benefit and applicability, not blanket `all`, maximal strictness, or translation of TS syntax into other languages. Keep legitimate boundary validation, idiomatic iteration, and justified casts or mocks. Do not suppress warnings broadly to obtain a green result.
- Run existing checks before changes when practical to establish the baseline. Existing violations are not permission for a repository-wide rewrite. Fix only setup-related issues within the agreed scope; report other findings and choose explicitly scoped adoption rather than hiding them.
- If vendoring third-party rules, identify the upstream revision, retain its license/provenance, and preserve local adaptations on updates. Do not copy an entire anti-slop ruleset merely because it is available.

## Local review guidance

Keep general implementation and verification principles in the project's existing instructions. `project-guidelines` handles those principles separately; do not require or invoke it automatically. Add only missing, project-specific criteria to local `AGENTS.md`, in its language, and deduplicate existing guidance.

For each adopted policy, distinguish:

- **Automated:** the configured check, scope, and command actually detecting it.
- **Review:** a concrete question about behavior or intent that the tools do not settle.

Useful review questions include whether a type escape has an established invariant, repeated copying grows with input size, an abstraction solves a current need, error recovery hides failure, or a test verifies the real outcome. Select relevant questions; do not paste this entire list into every project. A configured lint pass is not proof that all such patterns are absent.

Keep `AGENTS.md` concise: check commands with scope/prerequisites and a few uncovered criteria. Detailed lint policy belongs in tool configuration. Apply review criteria to code work, not ordinary writing, research, or brainstorming. Add no mandatory review rounds, fixed report format, approval state, hooks, or repeated successful-check loops.

## Verify and finish

- Confirm configuration parses and selected rules are supported. Exercise each changed check against the applicable source or a representative target. A lint failure must be reported accurately, including whether it predates setup.
- Where practical, use a temporary isolated good/bad example to confirm a newly selected rule detects its intended violation while allowing the valid case. Do not add permanent tests that merely duplicate tool implementation. Do not claim a detector is verified just because its config parses.
- Review the diff for unrelated changes, duplicate instructions, accidentally excluded maintained source, and machine-specific paths. Reapplying the setup should produce no redundant entries or extra changes.
- Stop after the adopted checks and relevant setup verification are complete. Reuse unchanged evidence; retry only when new changes or evidence justify it. Report unchanged baseline failures, unavailable checks, and judgment-only coverage without claiming complete lint or behavioral success.

Report changed files, automated coverage and commands/results, remaining review criteria, and any adoption limitation. Distinguish tool configuration, executed checks, and application behavior. Do not install this setup into unrelated projects or refresh plugin installations unless requested.
