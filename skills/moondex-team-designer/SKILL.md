---
name: moondex-team-designer
description: Use when a repository needs a Moondex team configuration based on its technology stack, project surfaces, verification tools, and task risk profile.
---

# Moondex Team Designer

Design a project-local Moondex team for the repository where Moondex is installed.

## Read First

- `../../docs/contracts/stack-profile-schema.md`
- `../../docs/contracts/team-spec-schema.md`
- `../../docs/execution/stack-aware-team-composition.md`

## Core Rule

Store durable team configuration in the target project under `.moondex/team/`.

Do not write team configuration into `.moondex/state/`; that directory is runtime state. Do not create `.codex/agents/*.toml` in v1 unless the user explicitly asks to promote a team member into a Codex native custom agent.

## Workflow

1. Inspect the target repository.
2. Build a stack profile from manifests, tool configs, framework signals, runtime surfaces, and verification commands.
3. Choose the smallest team that covers the current stack and risk profile.
4. Write `.moondex/team/stack-profile.json` and `.moondex/team/team-spec.json`.
5. Write human-readable team files under `.moondex/team/`.
6. If `.gitignore` ignores `.moondex/`, add or recommend an exception that keeps `.moondex/team/` committed while `.moondex/state/` remains ignored.
7. Preserve generation notes under `_workspace/moondex-team/` when useful for audit.

## Stack Signals

Read these before choosing a team:

- manifests: `Cargo.toml`, `package.json`, `pnpm-lock.yaml`, `yarn.lock`, `pubspec.yaml`, `pyproject.toml`, `go.mod`, `pom.xml`, `build.gradle`
- frameworks: React, Next.js, Vue, Svelte, Flutter, Axum, Clap, Tauri, FastAPI, Django, Rails, Spring
- test tools: Cargo test, Vitest, Jest, Playwright, Flutter test, pytest, Go test, JUnit
- runtime surfaces: CLI, web UI, mobile UI, API, worker, plugin, skill, MCP server
- contract surfaces: schema, migration, API route, CLI command, persisted state, archive format, plugin manifest

## Team Policy

Start with:

```text
implementer -> code-reviewer
```

Add `compliance-reviewer` when the task touches persisted state, schema, API, CLI contract, archive behavior, plugin manifest, permissions, policy, or cross-role handoff contracts.

Add `tester` when the task touches UI, E2E behavior, external IO, mobile/platform behavior, deployment, installation, or user-critical workflows.

Represent technical specialization as `specialist_lenses`, not as endless new role names. Examples:

- `rust_runtime`
- `cli_contract`
- `frontend_ui_accessibility`
- `browser_e2e`
- `flutter_widget_platform`
- `python_api_schema`
- `plugin_packaging`
- `skill_authoring`

## Target Files

Default output:

```text
.moondex/team/
  stack-profile.json
  team-spec.json
  README.md
  verification-plan.md
  members/
    implementer.md
    code-reviewer.md
    compliance-reviewer.md
    tester.md
_workspace/moondex-team/
  role-selection-matrix.md
  generation-notes.md
```

Only create member files for selected or available roles. If a role is not selected for the initial team, mention when it should be added in `team-spec.json` and `README.md`.

## Gitignore Rule

If the target repository ignores `.moondex/`, preserve runtime-state hygiene with this shape:

```gitignore
.moondex/*
!.moondex/team/
!.moondex/team/**
.moondex/state/
```

The team directory is durable configuration. The state directory remains uncommitted runtime data.

## Output Requirements

Every generated team must include:

- detected stack profile and confidence
- selected member list
- role chain
- specialist lenses per member
- required checks
- handoff expectations
- escalation rules
- unknown or ambiguous stack signals

If stack detection is weak, still create a fallback team and mark the profile as `unknown_with_signals`.

