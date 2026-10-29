# TypeScript and JavaScript

Read for maintained TS/JS code only. Detect the runtime, package manager, workspace boundaries, ESLint/Oxlint/Biome configuration, formatter, and `tsconfig`/build scripts.

## Tool selection and policy

- Keep the existing lint stack. Type checking and linting cover different questions; reuse the actual project type-check/build command rather than assuming `tsc --noEmit` fits every workspace or framework.
- With no linter, choose a small baseline compatible with the project. Do not install Oxlint just to use upstream anti-slop rules when the existing stack already covers the desired policy.
- Treat [dmmulroy/anti-slop](https://github.com/dmmulroy/anti-slop) as an opinionated source of optional Oxlint rules, not a universal standard. Verify its current plugin API and dependency versions before vendoring selected rules. Preserve MIT license and upstream revision alongside the copied source.
- Prefer rules that address demonstrated loss of type information, unjustified assertions, or growing accumulator copies. Check false positives against actual project boundary parsers, data dictionaries, testing seams, and runtime support.
- Do not indiscriminately ban `unknown`, runtime type guards, module mocks, or `filter().map()`. Untrusted input needs representation and validation; callbacks and iteration changes can alter semantics. Optional Effect policy applies only where the project actually uses Effect and agrees with that architecture.
- Preserve inference and existing type contracts where useful. Do not add schema dependencies, `SAFETY` comments everywhere, or unrelated refactors just to satisfy imported preferences.

## Verification and remaining judgment

Use the repository's lint and type-check scripts on their intended packages. Verify rule activation and version compatibility with the tool itself. Document a type checker only if configured and actually available.

Review whether asserted types are backed by validation, growing copies have a material cost, and mocks leave the user-visible contract untested. AST-based lint cannot establish all runtime types, ownership, performance, or behavior.

Sources: [Oxlint configuration](https://oxc.rs/docs/guide/usage/linter/config.html), [anti-slop rules and analysis boundaries](https://github.com/dmmulroy/anti-slop#rules). Check the installed version before applying upstream examples.
