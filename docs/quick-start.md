# Quick Start Guide

Get Joshu running in under 5 minutes.

## Installation

```bash
git clone https://github.com/Faycalraghibi/Joshu.git joshu
cd joshu
pip install -e .
```

## First Run

### Interactive Mode

```bash
joshu interactive
```

You'll see:
```
Joshu Interactive Mode
Type /help for commands, /exit to quit
Mode: AGENT

[AGENT] >
```

### Your First Commands

**Try these examples:**

1. **Agent Mode (autonomous execution):**
   ```
   > create a Python hello world script
   ```

2. **Ask Mode (Q&A):**
   ```
   > /ask
   > what is Docker and how does it work?
   ```

3. **Plan Mode (step-by-step):**
   ```
   > /plan
   > set up a Flask REST API project
   ```

## One-Shot Commands

Execute without entering interactive mode:

```bash
# Natural language commands
joshu "list all Python files modified today"
joshu "create a backup of the config directory"

# Code changes (asks before editing)
joshu "write a binary search function in search.py with a test"

# Headless, for scripts
joshu run -p --permission-mode plan "summarize what this repo does"
```

## Essential Commands

### Mode Switching
```
/agent    # Autonomous execution mode
/ask      # Q&A mode
/plan     # Planning mode
```

### Session Management
```
/session         # Show current session
/session list    # List all sessions
/session new     # Start new session
```

### Help & Info
```
/help     # Show all commands
/history  # Command history
/config   # Configuration
```

## Choose a Model Provider

Joshu works with any OpenAI-compatible provider. The default is OpenRouter
with a free model; set its key in `.env` at the project root:

```bash
OPENROUTER_API_KEY=your_api_key
```

To use another provider:

```bash
joshu providers                          # list providers and key status
joshu config --set provider=anthropic    # then set ANTHROPIC_API_KEY
joshu config --set model=claude-sonnet-5-5
```

See [Models & Providers](models-and-providers.md).

## Common Use Cases

### Execute System Commands
```
> find all files larger than 100MB
> show disk usage sorted by size
> create a new Python virtual environment
```

### Generate Code
```
> /agent
> create a REST API with Flask that handles user CRUD operations
```

### Get Explanations
```
> /ask
> explain how git rebase works
```

### Plan Complex Tasks
```
> /plan
> set up a CI/CD pipeline with GitHub Actions
```

## Next Steps

- **[Interactive Mode Guide](interactive-mode.md)** — Deep dive into interactive features
- **[Commands Reference](commands.md)** — Complete command list
- **[Configuration](configuration.md)** — Advanced configuration options
