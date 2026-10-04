# Keyboard shortcuts

Press `?` on an empty prompt to see these in the terminal.

## At the prompt

| Key | Action |
|-----|--------|
| `Enter` | Send |
| `Alt+Enter`, `\` then `Enter` | New line (`Shift+Enter` after `/terminal-setup`) |
| `Tab` | Complete a `/command` or `@file` |
| `Up` / `Down` | Previous / next input |
| `Ctrl+R` | Search input history (`Enter` to pick, `Ctrl+G` or `Esc` to cancel) |
| `Ctrl+G` | Write the prompt in your editor (`$VISUAL`, `$EDITOR`, Notepad on Windows) |
| `Alt+V` | Attach the image in the clipboard (also `/paste`) |
| `Shift+Tab` | Cycle modes: default → accept edits → plan |
| `Esc` | Close the menu, or clear the input |
| `Ctrl+O` | Show the last request's tool output in full (output cut to a few lines is marked "ctrl+o to expand") |
| `Ctrl+L` | Clear the screen, keeping what you typed |
| `Ctrl+C` | Clear the input; twice on an empty prompt to exit |
| `Ctrl+D` | Exit on an empty prompt; otherwise delete the next character |
| `Ctrl+A` / `Ctrl+E` | Start / end of the line |

## While the agent works

| Key | Action |
|-----|--------|
| `Esc`, `Ctrl+C` | Stop the current request |
| `Ctrl+O` | Show tool output in full from now on (press again to fold it) |
| typing | Kept and put in the prompt when the agent finishes |

When a request runs 20 seconds or more, the terminal bell rings when it
finishes or needs your approval (`notifications: off` to disable,
`notify_after_seconds` to change the time).

## Vim mode

`/vim` (or `vim_mode: true` in `~/.joshu/config.yaml`) switches the input to
vi editing: `Esc` for NORMAL mode, then the usual motions and edits (`h` `l`
`w` `b` `0` `$`, `x` `dw` `dd` `cw`, `u` to undo, `i` `a` `A` to insert, `v`
to select). The prompt shows `N` in NORMAL mode.
