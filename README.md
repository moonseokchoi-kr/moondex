# Moondex

Moondex is a Codex plugin for turning rough product ideas into structured planning and design artifacts. It focuses on the work before implementation: idea discovery, validation, requirements, architecture, information architecture, UI briefs, API contracts, harness audits, and handoff notes.

The plugin is the Codex port of the original Moon Harness. The current Codex manifest exposes the `skills/` directory as the supported plugin surface.

## What It Provides

| Area | Skill | Purpose |
|------|-------|---------|
| Idea discovery | `/idea-workshop` | Guide an idea from brainstorming through reframing, research, validation, and PRD writing. |
| Requirements and design | `/spec-design` | Produce implementation-ready requirements and design artifacts without writing production code. |
| Isolated planning work | `/git-worktree` | Create a feature branch and worktree for separated design work. |
| Project harness | `/harness` | Set up or audit an agent-friendly project environment. |
| Session continuity | `/handoff` | Write a continuation document for a future agent/session. |
| Deep review | `/adversarial-review` | Challenge an implementation approach when normal review loops are not resolving the issue. |
| Stitch utilities | `/design-md`, `/enhance-prompt`, `/stitch-loop`, `/react:components`, `/remotion` | Support design-system extraction, prompt improvement, Stitch build loops, React conversion, and walkthrough videos. |

## Workflow

```text
Idea stage                         Design stage
────────────────────────────       ────────────────────────────
/idea-workshop                     /spec-design
  Phase 1: Diverge                   Phase 1: Requirements
  Phase 2: Reframe                   Phase 2-A: Architecture
  Phase 3A: Research team            Phase 2-B: IA / UI
  Phase 3B: Evidence-based review    Phase 2-C: API contracts
  Phase 3C: PRD                      Implementation happens elsewhere
```

`/idea-workshop` is for product exploration. It can expand a vague idea, reframe it from different angles, send research work to specialist prompts, and produce a PRD when the idea is ready.

`/spec-design` is for implementation preparation. It tracks state through documents and labels, then produces requirements, architecture, IA, UI, and API outputs under `docs/spec-design/`.

## Installation

Install from the Codex plugin marketplace entry:

```text
/plugin install moondex@moondex
```

Or add the marketplace manually in `~/.agents/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "moondex": {
      "source": {
        "source": "github",
        "repo": "moonseokchoi-kr/moondex"
      }
    }
  },
  "enabledPlugins": {
    "moondex@moondex": true
  }
}
```

Restart Codex after enabling the plugin.

## Repository Layout

```text
.
├── .codex-plugin/plugin.json     # Codex plugin manifest
├── AGENTS.md                     # Project instructions for Codex
├── README.md                     # User-facing overview
├── agents/                       # Specialist prompt definitions retained from the harness
├── hooks/                        # Host-compatibility hook scripts and pipeline experiments
├── skills/                       # Codex skills exposed by the plugin manifest
└── .harness/state/               # Generated harness state
```

The manifest source of truth is `.codex-plugin/plugin.json`. Keep the plugin name, folder name, and README examples aligned as `moondex`.

## Hooks Status

The `hooks/` directory is retained from Moon Harness for host compatibility experiments. The current Codex plugin manifest intentionally exposes only `skills`, because unsupported hook manifest fields are rejected by the Codex plugin validator.

This means the hook scripts are part of the repository, but they are not currently part of the supported plugin activation surface unless a host integrates them separately.

## Development

Clone the repository:

```bash
git clone https://github.com/moonseokchoi-kr/moondex
cd moondex
```

Validate plugin-level changes before handing off:

```bash
python3 /Users/moon/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py /Users/moon/Workspace/moondex
bash -n hooks/*.sh hooks/enforcement/*.sh hooks/enforcement/lib/*.sh
python3 -m py_compile hooks/enforcement/stop-pipeline.py
```

When changing the manifest, do not add Claude Code-only fields to `.codex-plugin/plugin.json`.

## License

MIT
