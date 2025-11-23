# Quick Start Guide

Get Joshu running in under 5 minutes.

## Installation

```bash
git clone https://github.com/Faycacalraghibi/joshu-assistant.git
cd joshu-assistant
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

# Code generation
joshu code "write a binary search function in Python"
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

## Configuration (Optional)

Create `~/.joshu/config.yaml`:

```yaml
model: "llama-3-8b"
safety_mode: true
max_tokens: 4096
```

Or use environment variables:

```bash
export OPENROUTER_API_KEY=your_api_key
export JOSHU_MODEL=llama-3-8b
```

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
