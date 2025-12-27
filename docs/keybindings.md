# Joshu CLI Keybindings

> **Auto-generated** from source code introspection.
> Generated: 2025-12-27 02:48 UTC

This document lists all keyboard shortcuts available in Joshu CLI.

## Quick Reference

| Key | Action |
|-----|--------|
| `Ctrl+C` | Cancel/Exit |
| `Ctrl+D` | Exit (empty line) |
| `Ctrl+L` | Clear screen |
| `Ctrl+R` | Search history |
| `Escape` | Switch to NORMAL mode |

## Global

| Keybinding | Action | Description |
|------------|--------|-------------|
| `Ctrl+J` | line navigation down | Ctrl+J for line navigation down |
| `Ctrl+K` | line navigation up | Ctrl+K for line navigation up |
| `Ctrl+R` | reverse search | Ctrl+R for reverse search |
| `Ctrl+B` | Ctrl+B to send command to background bash | Ctrl+B to send command to background bash |
| `Ctrl+C` | graceful interrupt | Ctrl+C for graceful interrupt |
| `Ctrl+D` | exit | Ctrl+D for exit |
| `Ctrl+L` | clear screen | Ctrl+L for clear screen |
| `Ctrl+T` | command suggestion toggle | Ctrl+T for command suggestion toggle |
| `Escape` | Escape key to switch to NORMAL mode | Escape key to switch to NORMAL mode |

## NORMAL mode (Vim)

| Keybinding | Action | Description |
|------------|--------|-------------|
| `H` | left | Vim 'h' for left |
| `L` | right | Vim 'l' for right |
| `J` | down | Vim 'j' for down |
| `K` | up | Vim 'k' for up |
| `W` | word forward | Vim 'w' for word forward |
| `B` | word backward | Vim 'b' for word backward |
| `I` | Vim | Vim 'i' to enter INSERT mode |
| `A` | Vim | Vim 'a' to append after cursor |
| `:` | command mode | Vim ':' for command mode |
| `D` | Start of delete command | Start of delete command |
| `Y` | Start of yank command | Start of yank command |
| `P` | Vim | Vim 'p' to paste |

## Customization

Keybindings can be customized in your configuration file:

```yaml
# ~/.joshu/config.yaml
keybindings:
  send_message: 'ctrl+enter'
  cancel: 'escape'
  clear_screen: 'ctrl+l'
```

## Vim Mode

Joshu supports Vim-style navigation. Press `Escape` to enter NORMAL mode,
then use standard Vim keys (`h`, `j`, `k`, `l`, `w`, `b`, `i`, `a`, etc.).

To exit Vim mode, press `i` or `a` to return to INSERT mode.
