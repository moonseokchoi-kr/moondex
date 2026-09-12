# 2026-09-13 Push and reinstall

> Release work log, not an approval baseline change.

The user requested pushing main and reinstalling Moondex. Main `5afb1b1` was pushed to origin.
The personal marketplace resolves `moondex` to `/Users/moon/plugins/moondex`, a symlink to local main.
Default Codex and the current Orca account already have this plugin installed.

The documented plugin-creator helper set version `0.5.0+codex.20260912155004` for cache invalidation.
The runtime inventory binds the new manifest version and hash. The portability test now accepts
the documented `+codex.<token>` SemVer build metadata as well as plain numeric versions;
plugin naming, manifest fields, runtime integrity, and execution criteria are unchanged.

A bytecode-only retired skill directory and four old skill-local state files were moved to the
external backup before packaging. No tracked history or original phase4 worktree was modified.
The first test invocation selected the system Python without pytest; using the existing test
interpreter then exposed those state files and the overly narrow version regex. After the corrections:
**54 passed in 3.03s**. Plugin structure validation passed.

Backup, install receipts and post-install checks: `/Users/moon/Workspace/moondex-local-evidence/reinstall-20260913-005003`.
Configuration backups are private; hooks/notify are compared before and after installation.
Only release metadata, its format test and this log belong to the release commit. Main's pre-existing
local ignore and state-document edits remain uncommitted.

A new conversation is needed to load the updated skill catalog. Reinstall does not establish that
this running conversation has replaced its already-loaded instructions.
