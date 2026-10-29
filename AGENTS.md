# Moondex

Moondex provides four self-contained skills for project-local coding guidance, language-specific
code quality setup, explicitly selected TDD/Tidy First, and deeper task reframing.
It has no execution runtime or hooks.

## Repository rules

- Keep `.codex-plugin/plugin.json` as the metadata source of truth and the
  `moondex` name aligned across metadata and documentation.
- Expose only `skills/`, with exactly `project-guidelines`, `code-quality-setup`,
  `tdd-tidy-first`, and `deeper-prompt`.
- Keep general coding principles in `project-guidelines`; language setup belongs
  in `code-quality-setup/references/`. Keep opt-in TDD workflow and code/test idioms
  in `tdd-tidy-first` and its own references. Load only relevant language references.
- Keep `deeper-prompt` explicitly selected and preserve its original prompt; present the rewritten prompt for the user to decide before execution.
- All skills must work without checkout scripts, runtime, or global configuration.
- Keep `tdd-tidy-first` explicitly selected; distinguish instruction installation
  from one-test `go` execution and preserve the other skills' defaults.
- Preserve target-project rules and existing configuration. Distinguish automated
  checks from review judgments without adding a recurring review pipeline.
- The repo-local marketplace source is intentionally `../`, resolved from the
  `.codex-plugin/marketplace.json` parent to this exact plugin root.
- Packaging checks prove discovery and file availability, not future model behavior.
- Keep manifest fields compatible with the Codex plugin specification. Do not add
  runtime inventories, workflow state, worker profiles, or hooks for these skills.

## User invocations

- `$moondex:project-guidelines` — write or merge local AGENTS.md coding principles.
- `$moondex:code-quality-setup` — configure local checks and uncovered review criteria.
- `$moondex:tdd-tidy-first` — merge opt-in TDD/Tidy First rules or execute one planned test on `go`.
- `$moondex:deeper-prompt` — analyze and rewrite a task for greater depth, then let the user decide.

## Validation

Run from this checkout before handing off plugin changes:

```bash
python3 -m json.tool .codex-plugin/plugin.json >/dev/null
python3 -m json.tool .codex-plugin/marketplace.json >/dev/null
python3 -m unittest discover -s tests -v
git diff --check
```
