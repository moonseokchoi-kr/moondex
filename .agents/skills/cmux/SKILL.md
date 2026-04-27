---
name: cmux
description: Use when working in a cmux environment to inspect terminal layout, split panes, send commands to another terminal surface, read terminal output, or control a browser surface. Also use when the user mentions cmux, panes, surfaces, workspaces, screen reading, or tmux-style terminal multiplexing.
---

# cmux

Use `cmux` to operate multiple terminal or browser surfaces during multi-agent work.

## Use This Skill When

- The user mentions `cmux`.
- You need to monitor or drive multiple terminal sessions.
- You need to send a command to another pane or surface and read back the result.
- You need to translate a `tmux` workflow into `cmux`.

## First Checks

1. Confirm `cmux` exists with `command -v cmux`.
2. Inspect the current layout with `cmux identify` or `cmux tree`.
3. Prefer the current workspace and surface unless you need to target another one explicitly.

## Core Model

`cmux` uses this hierarchy:

- `window`
- `workspace`
- `pane`
- `surface`

Target handles look like `workspace:2`, `pane:3`, or `surface:4`.

When running inside a cmux terminal, current context may already be available through:

- `CMUX_WORKSPACE_ID`
- `CMUX_SURFACE_ID`
- `CMUX_SOCKET_PATH`

## Common Commands

### Inspect layout

- `cmux identify`
- `cmux tree`
- `cmux list-workspaces`
- `cmux list-panes --workspace <workspace>`
- `cmux list-pane-surfaces --pane <pane>`

### Read or write another terminal

- `cmux read-screen`
- `cmux read-screen --scrollback --lines <N>`
- `cmux capture-pane --surface <surface>`
- `cmux send --surface <surface> "command\\n"`

Important:

- Include `\n` in `cmux send` when you want Enter pressed.
- After `send`, wait briefly before `read-screen` if the command needs time to run.

### Create or focus layout

- `cmux new-workspace --cwd <path>`
- `cmux new-split right`
- `cmux new-split left`
- `cmux new-split up`
- `cmux new-split down`
- `cmux new-surface --type terminal`
- `cmux new-surface --type browser`
- `cmux focus-pane --pane <pane>`

### Browser surfaces

- `cmux browser open <url>`
- `cmux browser goto <url>`
- `cmux browser snapshot -i`
- `cmux browser click <selector>`
- `cmux browser type <selector> <text>`
- `cmux browser fill <selector> <text>`
- `cmux browser screenshot --out <path>`

## tmux Translation

If a task suggests `tmux`, convert it to `cmux`:

- `tmux send-keys -t P "cmd" C-m` -> `cmux send --surface P "cmd\n"`
- `tmux capture-pane -t P -p` -> `cmux capture-pane --surface P`
- `tmux split-window -h` -> `cmux new-split right`
- `tmux split-window -v` -> `cmux new-split down`
- `tmux select-pane -t P` -> `cmux focus-pane --pane P`
- `tmux new-window` -> `cmux new-workspace`

## Multi-Agent Pattern

Use `cmux` as an operations layer, not as the planning contract itself.

Recommended flow:

1. Create or identify dedicated surfaces for planner, implementer, and reviewer work.
2. Send commands to the right surface with `cmux send`.
3. Read results with `cmux read-screen` or `cmux capture-pane`.
4. Keep task, plan, and wave state in project documents rather than only in terminal history.

## Avoid

- Assuming the active surface is the correct target without checking.
- Sending long commands without `\n`.
- Using raw `tmux` commands in a cmux environment.
- Treating terminal layout as the source of truth for execution state.
