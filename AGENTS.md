# Moondex

Moondex is a Codex plugin of project-local workflow skills for idea discovery,
delegated execution, deterministic review convergence, enforcement, and harness audits.
The plugin manifest exposes `skills/` only. Files under `agents/` are role profiles that an
orchestrator may inject into collaborators; their presence does not register or authorize workers.

## Repository Rules

- Treat `.codex-plugin/plugin.json` as the plugin manifest source of truth.
- Keep plugin metadata name, folder name, and README examples aligned as `moondex`.
- Keep user-facing Codex instructions centered on `AGENTS.md`.
- Keep the manifest skills-only. Role profiles under `agents/` are injectable data, not
  registered or automatically authorized workers.
- The repo-local `.codex-plugin/marketplace.json` intentionally uses source path `../` because
  the marketplace file is inside the plugin root; resolved from its parent, it must equal this
  exact plugin root. A personal marketplace uses canonical `./plugins/moondex` instead.
- Keep generated project harness state under `.harness/state/`.
- Treat `docs/sdd/` as durable project artifacts and `.harness/` as local runtime evidence.
- In consumer projects, invoke `$moondex:execute` to prepare or continue an execution bundle. The loaded skill
  resolves `<moondex-runtime>` package-relatively; do not require a checkout cwd, `PYTHONPATH`,
  or user knowledge of the installed plugin path.
- Continue delegated runs with `$moondex:execute`: status is read-only; resume reconciles and may advance authorized work.
- Require a real user decision bound to the execution bundle digest. No fixed document phase order.
- Keep execution state under `.moondex/` and durable revisions/results under `docs/execution/`.
- Script owns shared state, scheduling and verification. Current AI performs assigned implementation and judgment.
- Required verification has no total-time/token cutoff. Two failed automatic repairs require a recorded decision.
- Retired SDD instructions are routing notices only; do not invoke the historical controller as a product mode.
- Keep raw reproduction evidence below `.harness/audit/`; render redacted CLI, report, result,
  sync, and export surfaces.
- Knowledge sync is opt-in through project-local configuration. Never infer a destination.
- Do not add unsupported manifest fields to `.codex-plugin/plugin.json`; validate against the plugin-creator spec after manifest changes.

## User Invocation Map

- `$moondex:idea-workshop` — idea discovery and validation.
- `$moondex:execute` — agreed intent, execution, verification, feedback and recording.
- `$moondex:pr-converge` — deterministic local review disposition and convergence.
- `$moondex:self-improve` — explicit project-local learning candidate processing.
- `$moondex:code-mapper` — graph probe or explicit approximate fallback.
- `$moondex:harness` — harness audit and project setup guidance.
- `$moondex:handoff` — durable continuation context.

Do not present `python3 -m harness_core` or checkout-relative `scripts/...` paths as consumer
commands. Those are implementation entry points for plugin development only.

## Plugin-development Validation

Run these checks from the Moondex checkout root before handing off plugin-level changes:

```bash
python3 -m json.tool .codex-plugin/plugin.json >/dev/null
python3 -m json.tool .codex-plugin/marketplace.json >/dev/null
python3 -c 'from pathlib import Path; import re,sys; errs=[]; [errs.append(f"{f}: missing frontmatter/name/description") for f in sorted(Path("skills").glob("*/SKILL.md")) if not f.read_text().startswith("---\n") or not re.search(r"^name:\s*.+$", f.read_text(), re.M) or not re.search(r"^description:\s*.+$", f.read_text(), re.M)]; print("\n".join(errs) if errs else "skill frontmatter ok"); sys.exit(1 if errs else 0)'
bash -n hooks/*.sh hooks/enforcement/*.sh hooks/enforcement/lib/*.sh
python3 -m py_compile hooks/enforcement/stop-pipeline.py
```

The versioned `skills/sdd/runtime/runtime-inventory.json` must remain aligned with the recursive
installed-runtime dependency closure. There is no public regeneration command to infer; update
the inventory in the same development change and let the tests verify its paths, sizes, and
hashes.

## Porting Notes

- `Claude Design` and `claude-design` are external visual-tool names and should not be renamed unless that workflow is replaced.
- The `hooks/` directory is preserved for compatibility experiments and optional local wrappers.
  The Codex plugin manifest intentionally exposes only `skills`.
