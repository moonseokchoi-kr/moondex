# C++

Inspect CMake/Meson/other build configuration, language standard, compiler,
platforms, presets, source/test targets, and CI. Use the real build directory and
flags; do not infer the test suite from one executable.

## Code idioms

- Prefer small functions, explicit dependencies, and `const` where it conveys the
  contract. Use algorithms or supported ranges for clear transformations; retain
  loops and branching when clearer. Do not force a lazy pipeline or raise the
  project's language standard to imitate another language.
- Use RAII and existing ownership conventions. Express ownership with value types
  or appropriate smart pointers; non-owning views/references need valid lifetimes.
  Avoid needless copies without turning ordinary code into template machinery.
- Preserve the project's exceptions/error-value policy. `std::optional` represents
  absence and `std::expected` is an option only where the standard and conventions
  support it. Do not add a Result library, enable exceptions, or change ABI policy
  solely for functional style.
- Minimize mutable state and effects while keeping resource lifetime and failure
  paths explicit. A structural edit must preserve behavior, ownership, and any
  relevant interface/ABI contract, not just compile successfully.

## Tests and actual checks

Reuse the existing test framework and assertion style (for example, GoogleTest,
Catch2, or project executables). Build the required test targets before running
the configured suite; a stale executable cannot prove Red or Green. A compiler
or linker failure is not behavioral Red.

Use actual build/test presets and CTest or other runner configuration, including
the supported platform matrix and long-running labels. Report excluded variants.
Reuse compiler warnings and configured clang-tidy with correct compilation
flags/database where applicable. Do not switch compilers, invent include paths,
or add sanitizers/formatters as incidental instruction setup.
