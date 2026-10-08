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

Explain a shell command or topic. Runs the agent in read-only (plan) mode, so
it may read files to answer but never runs or changes anything:

```bash
joshu explain "tar -czf backup.tar.gz src/"
joshu explain "what does git rebase --onto do"
```

---

### help

Show general Joshu help:

```bash
joshu --help
joshu run --help
```

## Main Commands

### run

Give the agent a task. It reads, searches, edits and runs commands until the
task is done, asking before edits and shell commands:

```bash
joshu run "add type hints to src/utils.py and run the tests"
joshu "list the largest files in this repo"     # same as `joshu run`
```

**Options**:
- `--provider <name>` - Model provider for this run (see `joshu providers`)
- `-m, --model <id>` - Model id
- `--permission-mode <mode>` - `default`, `accept_edits`, `plan` (read-only) or `bypass`
- `-y, --yes` - Bypass mode: run tools without asking (unsafe commands still ask)
- `-p, --print` - Headless: print only the final answer
- `--output-format json` - Print one JSON object (implies `--print`)
- `--output-format stream-json` - One JSON event per line as things happen (see [SDK and streaming](sdk.md))
- `--input-format stream-json` - Read requests from stdin, one JSON line each, into one conversation
- `-s, --sandbox` - Stricter shell safety check
- `--continue`, `-c` - Continue the most recent session in this directory
- `--resume <id>` - Continue a saved session
- `--image <path>` - Attach an image (repeatable); `@path.png` in the prompt works too
- `--max-budget-usd <usd>` - Stop when the session has cost this much
- `--max-request-tokens <n>` - Stop a request after it has used this many tokens
- `--background`, `-b` - Run it as a background job in its own worktree and return at once (`joshu jobs`)
- `-i, --interactive` - Start interactive mode instead
- `-v, --verbose` - Debug logging

See [Agent](agent.md) for permissions and tools.

---

### interactive

Start interactive mode:

```bash
joshu interactive
joshu interactive --provider ollama --model qwen3-coder
```

Starts a persistent session with conversation history, slash commands
(`/agent`, `/plan`, `/ask`, `/permissions`, `/undo`, `/resume`, `/commands`, `/agents`, `/reset`, ...) and tab completion.
See [Interactive Mode](interactive-mode.md).

---

### providers

List model providers, their API key variable and whether it is set; add or
remove your own:

```bash
joshu providers
joshu providers add <name> --base-url <url> [--api-key-env VAR] [--model <id>]
joshu providers remove <name>
```

---

### models

List the models a provider serves (live), and manage named models:

```bash
joshu models [-p <provider>] [-s <search>] [--tools] [--free] [--all]
joshu models add <name> <model-id> [-p <provider>] [--context-window N] [--check]
joshu models check <model-id|name> [-p <provider>]   # one test request with a tool
joshu models remove <name>
```

---

### use

Make a model (or named model) the default, saved in the user config:

```bash
joshu use <model-id> [-p <provider>] [--check]
joshu use <named-model> [--check]
```

See [Models & Providers](models-and-providers.md).

---

### config

```bash
joshu config --list
joshu config --set provider=openai
joshu config --set model=<model-id>
```

See [Configuration](configuration.md).

---

### search

Search the web:

```bash
joshu search "Python async best practices"
```

See [Web Search](web-search.md).

---

### trace

The timeline of a saved session: every model call (seconds, tokens in and
out, tool calls, whether it thought first) and tool run (seconds, failed),
then totals (time per call with and without thinking, slowest tools).

```bash
joshu trace              # the latest session in this directory
joshu trace 3f9a1c       # a session by id or prefix
joshu trace --json       # one JSON object per line
```

---

### sessions

List saved agent sessions (resume with `--resume <id>` or `--continue`):

```bash
joshu sessions
joshu sessions --all
```

---

### history

Show your previous requests:

```bash
joshu history
joshu history --limit 10
```

---

### serve

Run the A2A server so other agents and tools can give Joshu tasks over HTTP
(needs `pip install -e .[a2a]`):

```bash
joshu serve --port 8080
```

See [A2A Server](a2a-server.md).

---

### mcp

Manage MCP servers: `joshu mcp list|add|remove|status|connect|disconnect|discover`.
See [MCP Servers](mcp-servers.md).

---

### plugin

Install bundles of skills, commands, output styles, hooks and MCP servers:
`joshu plugin install <git-url | dir> [--yes] [--force]`, `list`, `update <name>`,
`enable <name>`, `disable <name>`, `remove <name>`. See [Plugins](plugins.md).

## Usage Patterns

### Scripts and CI

```bash
joshu run -p --permission-mode plan "summarize the changes in the last commit"
joshu run --output-format json "list TODO comments in src/" | jq -r .result
```

### Explore Available Commands

```bash
joshu examples
joshu commands file
```

## Tips

1. **Start in plan mode** for unfamiliar repos: `/plan` or `--permission-mode plan`
2. **Use "always"** at an approval prompt to stop being asked for a tool this session
3. **Explain before executing**: `joshu explain "<command>"`
4. **Pick a provider** with `joshu providers`; any OpenAI-compatible endpoint works

## Related Documentation

- [Quick Start](quick-start.md) - Getting started guide
- [Agent](agent.md) - Permissions, tools and headless mode
- [Interactive Mode](interactive-mode.md) - Interactive session features
- [Configuration](configuration.md) - Configure Joshu behavior
