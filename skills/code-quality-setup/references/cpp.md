# C++

Read for maintained C++ code only. Inspect CMake/Meson/other build configuration, compiler/version, language standard, supported platforms, presets, existing warnings, `.clang-tidy`, `.clang-format`, and CI.

## Tool selection and policy

- Reuse compiler warnings and existing clang-tidy/formatting policy. Do not switch compilers, impose a formatter, or enable all checks as part of ordinary quality setup.
- Reliable clang-tidy analysis needs the project's real compilation flags and includes. Reuse or generate a compilation database through the supported build configuration; for CMake, `CMAKE_EXPORT_COMPILE_COMMANDS` depends on generator support. Do not invent include paths or analyze a different build and claim coverage of the intended one.
- Add selected diagnostics relevant to correctness, bug-prone constructs, or demonstrated performance issues. Treat naming, readability, modernization, and architecture choices as project preferences. Preserve exceptions, RTTI, language-standard, and platform constraints.
- Respect `.clang-tidy` inheritance, overrides, compiler-specific options, and generated/third-party boundaries. A header filter limits reported header diagnostics; it does not by itself select translation units or guarantee all headers are analyzed.
- Keep casts, ownership transfers, copies, lifetime hazards, and ignored failures as review questions where automation cannot settle them. A `static_cast`, copy, or raw pointer is not intrinsically slop; require reasoning appropriate to the actual contract.
- Do not introduce clang-tidy-driven mass rewrites, blanket `-Werror`, or global warning suppression to make adoption pass. Preserve the existing formatting style.

## Verification and remaining judgment

Use repository targets or clang-tidy against representative maintained translation units with the correct build directory, for example `clang-tidy <source.cpp> -p <build-directory>` when supported. Verify the effective check list with the installed version. A clean single-file result must not be reported as whole-project coverage.

Review lifetime, ownership, concurrency, ABI assumptions, and runtime cost where relevant. clang-tidy and compiler warnings do not prove absence of undefined behavior or validate all build variants.

Source: [clang-tidy documentation](https://clang.llvm.org/extra/clang-tidy/). Confirm build database generation in the project's build-system documentation before changing configuration.
