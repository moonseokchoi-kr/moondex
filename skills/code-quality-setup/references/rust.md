# Rust

Read for maintained Rust code only. Inspect workspace/package `Cargo.toml`, `Cargo.lock`, `rust-toolchain` files, minimum supported Rust version, Cargo features, target platforms, CI, and existing lint attributes/configuration.

## Tool selection and policy

- Reuse rustc diagnostics, Clippy, and rustfmt as already configured. Confirm the selected toolchain has Clippy before promising a runnable command. Do not upgrade the toolchain or add broad dependencies solely for lint setup.
- Preserve workspace lint inheritance and package-specific policy. Configure lint levels through supported Cargo lint tables or code attributes; `clippy.toml`/`.clippy.toml` configures lint parameters, not the enabled lint list.
- Add only relevant correctness, suspicious-code, or demonstrated performance checks. Do not blanket-enable restriction/pedantic groups or turn all existing warnings into errors as an incidental setup change.
- Scope Clippy to the project's real targets and supported feature combinations. `--all-features` may activate incompatible features; `--all-targets` may require unavailable dependencies. Use the CI build matrix or documented supported combination.
- Unnecessary clones, unchecked failures, and unsafe invariants are candidates for inspection, not global bans. Cloning can be required by ownership; `unwrap` can be justified in tests or established invariants. Preserve idiomatic lazy iterator chains and `Result` propagation.
- Keep existing safety documentation and require a concrete invariant where an unsafe operation actually needs one. Do not insert boilerplate explanations or force architecture changes.

## Verification and remaining judgment

Reuse the project Clippy command, or adapt `cargo clippy` to the supported package, targets, and features. `cargo fmt --check` checks formatting separately. Use `-D warnings` only when that is an adopted policy with a known baseline.

Review ownership and clone costs, actual unsafe preconditions, swallowed errors, and whether tests exercise behavior. Compilation and Clippy do not prove runtime correctness or every unsafe invariant.

Source: [Clippy configuration](https://doc.rust-lang.org/clippy/configuration.html). Verify lint availability and Cargo configuration support against the project's toolchain.
