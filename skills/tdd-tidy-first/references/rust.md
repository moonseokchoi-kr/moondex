# Rust

Inspect workspace/package `Cargo.toml`, lockfile, toolchain and minimum supported
Rust version, source/tests, supported targets/features, and CI. Respect package
boundaries and feature combinations rather than assuming `--all-features` works.

## Code idioms

- Prefer functional transformations where clear. Use iterators and `Option` /
  `Result` combinators such as `map`, `and_then`, or `unwrap_or` when they express
  intent simply; use lazy alternatives when fallback evaluation matters.
- Retain `match`, `if let`, and loops when branching, ownership, multiple cases,
  or readability benefits. Functional preference is not a syntax ban. Propagate
  recoverable errors with `?` and existing error types rather than hiding failures.
- Keep ownership and dependencies explicit. Avoid unnecessary clones, but accept
  those required by the contract; do not introduce lifetimes or abstractions that
  obscure a simple implementation merely to remove a copy.
- Minimize mutable state and isolate effects without inventing a framework. Keep
  unsafe invariants and resource management consistent with existing conventions.

## Tests and actual checks

Reuse unit/integration tests, doctests, and any adopted async/property test
infrastructure. Assert the observable result or error variant. Do not count a
compiler error, missing feature, or harness failure as behavioral Red.

Derive Cargo test commands from the real workspace and supported CI matrix;
account for doctests and any ignored/long-running tests explicitly. A package-only
run is not a full workspace run. Reuse configured rustc, Clippy, and formatting
checks on supported targets/features. Do not upgrade toolchains, add a runner,
or blanket-enable lint groups as part of applying TDD instructions.
