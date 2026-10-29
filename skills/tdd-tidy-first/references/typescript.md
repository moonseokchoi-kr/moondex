# JavaScript and TypeScript

Inspect `package.json` scripts, lockfiles, runtime and module format, workspace
boundaries, source/tests, runner configuration, and CI. Reuse the actual Node,
browser, Deno, or Bun environment and package manager. A TypeScript dependency or
lint script alone is not evidence of a product test suite.

## Code idioms

- Prefer pure functions and immutable data transformations when they express the
  behavior clearly. Use `map`, `filter`, `??`, and `?.` when their semantics fit:
  `??` preserves falsy values other than null/undefined, and `?.` must not silently
  hide a required value. Avoid unnecessarily copying growing accumulators.
- Keep clear `if`, `switch`, loops, and `try/catch`. Do not install libraries or
  invent Option/Result wrappers merely to imitate Rust. Follow an existing typed
  error architecture if the project already uses one.
- Preserve useful inference and explicit contracts at boundaries. Accept `unknown`
  and validate external data; an assertion alone does not make it safe. Do not
  ban runtime type guards or replace real validation with optional chaining.
- Keep functions small and dependencies explicit. Isolate effects at meaningful
  boundaries without introducing a dependency-injection framework for one test.
- Await or deliberately handle Promise outcomes, including rejected operations.
  `void` alone is not error handling. Keep recovery behavior observable rather
  than swallowing failures.

## Tests and actual checks

Use the project's adopted runner (for example, node:test, Vitest, Jest, Playwright,
or its runtime's test command), supported scripts, and assertion idioms. Do not
assume `npm test` exists or add a competing runner. Await asynchronous assertions
so a test cannot pass before its work completes. Use existing clock and API seams
when appropriate; mocks do not demonstrate real browser or service behavior.

Determine the full non-long-running suite from configuration and CI, not a
watch-mode default or changed-files filter. Run in a mode that terminates and
reports failure. Use the actual configured lint and type-check/build commands;
`tsc --noEmit` is not universally appropriate and does not execute product tests.
If only lint/type configuration exists, install guidance with that limitation;
`go` without a plan or behavioral test setup does not authorize scaffolding it.
