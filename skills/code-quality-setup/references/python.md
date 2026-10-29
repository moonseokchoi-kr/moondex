# Python

Read for maintained Python code only. Inspect `pyproject.toml`, dependency/lock files, supported Python versions, lint configuration, type-check configuration, and CI. Use the project's virtual environment and dependency runner.

## Tool selection and policy

- Preserve existing Ruff/Flake8/Pylint, formatting, and mypy/Pyright choices. If there is no linter, Ruff is a candidate for a small correctness baseline; a new type checker is a separate adoption decision, not a prerequisite for lint setup.
- Ruff supports `pyproject.toml`, `ruff.toml`, and `.ruff.toml`; inspect the effective file before editing. Nested configuration does not implicitly merge all parent settings. Preserve intentional inheritance and exclusions.
- Add selected rules with additive configuration where appropriate; avoid replacing the existing selection or enabling every family. Respect supported Python versions and the existing formatter.
- Start with useful syntax/name/import correctness checks. Add narrowly chosen bug or simplification checks only when their diagnostic and suggested fix fit the project. Check rule availability and preview status against the installed version.
- Keep type escapes, broad exception handling, and silent fallback behavior as review criteria unless the existing checker can enforce the chosen policy precisely. Dynamic interfaces and genuine exception boundaries can be legitimate.
- Do not translate TS restrictions into bans on `isinstance`, dictionaries, comprehension/iterator pipelines, or mocks. Avoid mandatory type annotations or new validation frameworks across otherwise untyped code.

## Verification and remaining judgment

Reuse repository commands. Examples, only if these tools and scopes are adopted, are `ruff check <source-path>` and the configured mypy/Pyright command. Formatting is separate and should use check mode during verification. Confirm which files actually receive the selected rules.

Review whether exceptions hide failed operations, dynamic data is checked at the right boundary, repeated copies grow with input, and tests assert behavior rather than mocks alone. Lint is not runtime validation or a substitute for tests.

Source: [Ruff configuration](https://docs.astral.sh/ruff/configuration/). Verify rule identifiers and effective settings locally rather than assuming current upstream defaults match the project.
