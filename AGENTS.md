# Moondex

Moondex is the Codex port of the original Moondex. It packages workflow skills for idea discovery, requirements, architecture, IA, UI, API contracts, handoff, and project harness audits.

## Repository Rules

- Treat `.codex-plugin/plugin.json` as the plugin manifest source of truth.
- Keep plugin metadata name, folder name, and README examples aligned as `moondex`.
- Keep user-facing Codex instructions centered on `AGENTS.md`, not `AGENTS.md`.
- Keep generated project harness state under `.harness/state/`.
- Do not add Codex-only manifest fields to `.codex-plugin/plugin.json`; validate with the Codex plugin validator after manifest changes.

## Validation

Run these checks before handing off plugin-level changes:

```bash
python3 /Users/moon/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py /Users/moon/Workspace/moondex
bash -n hooks/*.sh hooks/enforcement/*.sh hooks/enforcement/lib/*.sh
python3 -m py_compile hooks/enforcement/stop-pipeline.py
```

## Porting Notes

- `Claude Design` and `claude-design` are external visual-tool names and should not be renamed unless that workflow is replaced.
- The `hooks/` directory is preserved from Moondex for host compatibility experiments, but the current Codex plugin manifest intentionally exposes only `skills` because the validator rejects unsupported hook manifest fields.
