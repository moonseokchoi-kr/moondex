# Python

Inspect `pyproject.toml`, dependency/lock files, supported Python versions, source
and test layout, runner configuration, and CI. Use the project's virtual
environment and runner. Do not assume pytest or a type checker is installed.

## Code idioms

- Prefer small functions, explicit arguments, and side effects at clear boundaries.
  Use comprehensions or generators for clear transformations; retain ordinary
  loops when state, early exit, or readability calls for them. Do not build
  chains of `map`/`filter` merely to imitate another language.
- Avoid shared mutable defaults and accidental mutation of callers' data. Choose
  simple existing structures; do not freeze or copy every object by policy.
- Follow existing exceptions and return-value contracts. Catch specific failures
  at useful boundaries and preserve context when translating exceptions. Use
  context managers for resource lifetime; do not introduce Option/Result wrappers
  in a codebase whose normal error model is exceptions.
- Preserve type annotations and runtime boundary checks appropriate to this
  project. A static annotation does not validate external data. Do not add a
  validation framework or require annotations throughout unrelated code.

## Tests and actual checks

Reuse unittest, pytest, or the adopted runner and its existing discovery paths,
fixtures, and async support. Assert behavior and meaningful errors rather than
over-specifying private calls. Await async work with the configured test support;
do not add an async plugin just to fit a preferred template.

Identify the full non-long-running suite and existing marker/exclusion semantics.
Use real repository commands; neither `python -m unittest discover` nor `pytest`
necessarily discovers every package. Reuse configured Ruff/Flake8/Pylint,
mypy/Pyright, and build checks where present. Missing tools are a limitation,
not a reason to impose new quality configuration during instruction installation.
