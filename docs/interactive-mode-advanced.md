# interactive Mode

Joshu now includes an interactive mode with advanced terminal features powered by `prompt_toolkit`.

## Features

- Vim-style keybindings for efficient navigation
- Syntax highlighting for commands
- Multi-line input support
- Command history with persistent storage
- Auto-completion for common commands
- File path completion
- Reverse search through command history (Ctrl+R)
- Background command execution (Ctrl+B)
- Clear screen (Ctrl+L)
- Verbose mode toggle (Ctrl+V)
- Command suggestion toggle (Ctrl+T)

## Usage

To start the interactive mode, use one of these commands:

```bash
joshu interactive
joshu run --interactive
joshu run -i
```

## Persistent History

Commands are saved to a `.joshu_history` file in the current directory, providing per-directory persistent history.

## Requirements

The interactive mode requires the `prompt_toolkit` library. If this library is not available, Joshu will fall back to the basic interactive mode.
