# Moondex

Moondex is the Codex port of the original Moondex. It packages workflow skills for idea discovery, requirements, architecture, UX, API contracts, handoff, and project harness audits.

## Repository Rules

- Treat `.codex-plugin/plugin.json` as the plugin manifest source of truth.
- Keep plugin metadata name, folder name, and README examples aligned as `moondex`.
- Keep user-facing Codex instructions centered on `AGENTS.md`.
- Keep generated project harness state under `.harness/state/`.
- Do not add unsupported manifest fields to `.codex-plugin/plugin.json`; validate against the plugin-creator spec after manifest changes.

## Validation

Run these checks before handing off plugin-level changes:

```bash
python3 -m json.tool .codex-plugin/plugin.json >/dev/null
python3 -m json.tool .codex-plugin/marketplace.json >/dev/null
python3 -c 'from pathlib import Path; import re,sys; errs=[]; [errs.append(f"{f}: missing frontmatter/name/description") for f in sorted(Path("skills").glob("*/SKILL.md")) if not f.read_text().startswith("---\n") or not re.search(r"^name:\s*.+$", f.read_text(), re.M) or not re.search(r"^description:\s*.+$", f.read_text(), re.M)]; print("\n".join(errs) if errs else "skill frontmatter ok"); sys.exit(1 if errs else 0)'
bash -n hooks/*.sh hooks/enforcement/*.sh hooks/enforcement/lib/*.sh
python3 -m py_compile hooks/enforcement/stop-pipeline.py
```

## Porting Notes

- `Claude Design` and `claude-design` are external visual-tool names and should not be renamed unless that workflow is replaced.
- The `hooks/` directory is preserved from Moondex for host compatibility experiments, but the current Codex plugin manifest intentionally exposes only `skills` because the validator rejects unsupported hook manifest fields.
