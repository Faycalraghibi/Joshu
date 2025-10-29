# Enhanced Interactive Mode

OpenCLI now includes an enhanced interactive mode with advanced terminal features powered by `prompt_toolkit`.

## Features

### Multiline Input Support
The enhanced interactive mode supports multiline input, allowing you to enter complex commands that span multiple lines.

### Reverse Search (Ctrl+R)
Use `Ctrl+R` to search through your command history.

### Comprehensive Keyboard Shortcuts
- `Ctrl+J` - Line navigation down
- `Ctrl+K` - Line navigation up
- `Ctrl+B` - Send command to background bash
- `Ctrl+C` - Interrupt current operation
- `Ctrl+D` - Exit
- `Ctrl+L` - Clear screen
- `Ctrl+V` - Toggle verbose mode
- `Ctrl+T` - Toggle command suggestions
- Standard `prompt_toolkit` shortcuts for navigation and editing

### Vim-style NORMAL/INSERT Modes
Toggle between Vim-style NORMAL and INSERT modes for power users:
- `ESC` - Switch to NORMAL mode
- `i` - Switch to INSERT mode
- `h/j/k/l` - Left/Down/Up/Right navigation
- `w/b` - Word forward/backward
- `:` - Command mode
- `d` - Delete command
- `y` - Yank command
- `p` - Paste

### Per-directory Persistent Command History
Commands are saved to a `.opencli_history` file in the current directory, providing per-directory persistent history.

Special commands:
- `/history` - Show command history
- `/clear` - Clear command history

### Direct Bash Integration
Execute bash commands directly by prefixing them with `!`:
```
!ls -la
```

Special bash command features:
- `!!` - Repeat last bash command
- `!n` - Execute nth bash command from history
- `!pattern` - Execute last bash command matching pattern

### File Injection
Inject file contents into your prompt by prefixing the file path with `@`:
```
@README.md
```

Advanced file injection features:
- `@file:n-m` - Inject lines n to m from file
- `@@file` - Inject and execute file content

### Command Substitution
Use backticks for command substitution:
```
echo "Current directory: `pwd`"
```

### DeepSeek AI Integration (Optional)
If you have a DeepSeek API key, you can use it for enhanced AI assistance:
- Set `DEEPSEEK_API_KEY` environment variable
- Set `DEEPSEEK_AUTO_EXEC` to "true" for automatic command execution

## Configuration

The enhanced interactive mode can be configured through the YAML configuration file:

```yaml
enhanced_interactive: true
multiline_input: true
vim_mode: false
persistent_history: true
history_limit: 1000
```

## Requirements

The enhanced interactive mode requires the `prompt_toolkit` library. If this library is not available, OpenCLI will fall back to the basic interactive mode.

## Usage

To use the enhanced interactive mode, you can use either of these commands:

```
opencli interactive
```

or

```
opencli run --interactive
```

or

```
opencli run -i
```

The enhanced features will be automatically enabled if prompt_toolkit is available. Users can configure the behavior through the YAML configuration file.

## Slash Commands

The enhanced interactive mode supports the following slash commands:

- `/help` - Show help information
- `/history` - Show command history
- `/clear` - Clear command history
- `/config` - Show/set configuration
- `/model` - Switch AI model