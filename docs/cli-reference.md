# CLI Reference

## Overview

Joshu provides several built-in commands for discovering features, viewing examples, and getting help with shell commands.

## Discovery Commands

### examples

Show practical usage examples:

```bash
joshu examples
```

Output shows:
- Basic command examples
- File system intelligence examples
- Code generation examples
- Interactive mode examples

**Example output**:
```
Joshu Usage Examples
====================

Basic Commands:
  joshu "list all files"
  joshu "show disk usage"
  joshu "what is my IP address"

File System Intelligence:
  joshu "find large files"
  joshu "show Python files in current directory"
  joshu "create backup of config directory"

Code Generation:
  joshu "generate binary search in Python"
  joshu "create a REST API with FastAPI"

Interactive Mode:
  joshu interactive
```

---

### commands

List available command categories or commands in a category:

```bash
# Show all categories
joshu commands

# Show commands in specific category
joshu commands file
joshu commands system
joshu commands network
```

**Categories available**:
- `file` - File system operations
- `system` - System information and management
- `network` - Network operations
- `process` - Process management
- `text` - Text processing

**Example output**:
```bash
$ joshu commands file

File System Commands:
=====================

List files: joshu "list files"
Find files: joshu "find files by extension"
File info: joshu "show file information"
Directory structure: joshu "show directory tree"
Backups: joshu "create backup"
```

---

### explain

Get explanation of what a shell command does:

```bash
joshu explain <command>
```

**Examples**:

```bash
# Explain tar command
$ joshu explain tar
Explanation of 'tar':
The tar command is used to create and manipulate tar archives.
It can compress/extract files and preserve permissions.

Common usage:
  tar -czf archive.tar.gz directory/  # Create compressed archive
  tar -xzf archive.tar.gz              # Extract archive
  tar -tzf archive.tar.gz              # List contents

# Explain ls
$ joshu explain ls
Explanation of 'ls':
Lists directory contents. Common flags:
  -l  Long format (detailed info)
  -a  Show hidden files
  -h  Human-readable sizes
  -t  Sort by modification time
```

For unknown commands:
```bash
$ joshu explain unknowncommand
No specific explanation available for 'unknowncommand'.
Try asking about common commands like ls, cd, grep, etc.
```

---

### help

Show general Joshu help:

```bash
joshu --help
```

Lists all available commands and options.

## Main Commands

### run (default)

Execute natural language command:

```bash
joshu "your natural language request"

# Examples
joshu "list all Python files"
joshu "show disk usage"
joshu "compress directory"
```

**Options**:
- `-y, --yes` - Auto-execute without confirmation
- `--sandbox` - Run in sandbox mode (safe commands only)

---

### interactive

Start interactive mode:

```bash
joshu interactive
```

Starts a persistent session with:
- Conversation history
- Context awareness
- Slash commands
- Tab completion

See [Interactive Mode](interactive-mode.md) for details.

---

### search

Search the web:

```bash
joshu search "your query"

# Examples
joshu search "Python async best practices"
joshu search "how to install Docker"
```

See [Web Search](web-search.md) for details.

---

### history

Show command history:

```bash
# Show all history
joshu history

# Show last N commands
joshu history --limit 10
```

---

### repeat-last

Repeat the last command:

```bash
joshu repeat-last
```

---

### explain-last

Show explanation of the last command:

```bash
joshu explain-last
```

## Global Options

These work with any command:

```bash
--verbose          # Show detailed output
--quiet            # Minimal output
--model <name>     # Use specific model
--config <path>    # Use custom config file
```

## Usage Patterns

### Quick One-Shot Commands

```bash
joshu "show system info" -y
```

### Explore Available Commands

```bash
# See what's possible
joshu examples

# Browse by category
joshu commands

# Look up specific commands
joshu commands file
```

### Get Help with Shell Commands

```bash
# Before using unfamiliar command
joshu explain tar

# After failed command
joshu explain-last
```

### Repeat Previous Work

```bash
# Run last command again
joshu repeat-last

# See what last command did
joshu explain-last
```

## Tips

1. **Start with examples**: Run `joshu examples` to see what's possible
2. **Browse commands by category**: Use `joshu commands <category>`
3. **Explain before executing**: Use `joshu explain <cmd>` for unfamiliar commands
4. **Use -y for automation**: Add `-y` flag to skip confirmations

## Related Documentation

- [Quick Start](quick-start.md) - Getting started guide
- [Interactive Mode](interactive-mode.md) - Interactive session features
- [Configuration](configuration.md) - Configure Joshu behavior
