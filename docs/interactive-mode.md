# Interactive Mode

Complete guide to Joshu's interactive mode.

## Starting Interactive Mode

```bash
joshu interactive

# With options
joshu interactive --model llama-3-70b --verbose
```

## Interface Overview

```
Joshu Interactive Mode
Type /help for commands, /exit to quit
Mode: AGENT

[AGENT] >
```

**Components:**
- **Mode indicator**: Shows current mode (AGENT, ASK, PLAN)
- **Prompt**: Where you type commands
- **Output area**: Results and responses

## Three Modes

### 🤖 Agent Mode

**Purpose:** Autonomous task execution

**Behavior:**
1. Generates execution plan
2. Executes commands safely
3. Handles errors automatically
4. Provides execution summary

**Example:**
```
[AGENT] > create a Flask project with SQLite

🎯 Goal: create a Flask project with SQLite
📝 Generating execution plan...
🚀 Executing 4 step(s)...

[Step 1/4] mkdir flask_project
✅ Completed

...

📊 Summary: 4/4 successful
```

**Switch to:** `/agent`

### 💬 Ask Mode

**Purpose:** Q&A without execution

**Behavior:**
- Provides explanations
- No command generation
- No system modifications

**Example:**
```
[ASK] > how does Docker work?

💬 Docker is a containerization platform...
[Detailed explanation without commands]
```

**Switch to:** `/ask`

### 📋 Plan Mode

**Purpose:** Task planning without execution

**Behavior:**
1. Breaks down goal into steps
2. Presents numbered list
3. User executes manually

**Example:**
```
[PLAN] > set up CI/CD pipeline

📋 Plan:
1. Create .github/workflows directory
2. Create ci.yml workflow file
3. Configure build steps
4. Set up deployment
5. Add environment variables
```

**Switch to:** `/plan`

## Slash Commands

### Session Management

```
/session              # Current session ID
/session list         # All sessions
/session new          # Start new session
/session end          # End and create new
/session switch <id>  # Switch to session
/session delete <id>  # Delete session
/session help         # Session help
```

### Memory Commands

```
/memory                      # Memory help
/memory search <query>       # Semantic search
/memory status               # Memory stats
/memory clear                # Clear all memories
```

### Mode Switching

```
/agent    # Switch to Agent mode
/ask      # Switch to Ask mode
/plan     # Switch to Plan mode
```

### Utility Commands

```
/history  # Command history
/clear    # Clear history
/help     # Show help
/config   # Configuration
/model    # Switch model
```

## Special Commands

### Execute Bash Commands

```
!ls -la                # Execute command
!!                     # Repeat last command
!3                     # Execute 3rd command from history
```

### File Injection

```
@config.yaml           # Inject file content
@@deploy.sh            # Inject and execute
@app.py:10-20          # Inject lines 10-20
```

## Keyboard Shortcuts

### Navigation

| Shortcut | Action |
|----------|--------|
| `Ctrl+R` | Reverse search |
| `Ctrl+J` | Line down |
| `Ctrl+K` | Line up |
| `Up/Down` | History navigation |

### Execution

| Shortcut | Action |
|----------|--------|
| `Ctrl+B` | Background bash |
| `Ctrl+C` | Interrupt |
| `Ctrl+D` | Exit |
| `Enter` | Execute |

### Editing

| Shortcut | Action |
|----------|--------|
| `Ctrl+L` | Clear screen |
| `Ctrl+T` | Toggle suggestions |
| `Ctrl+A` | Beginning of line |
| `Ctrl+E` | End of line |

## Vim Mode

Enable in `~/.joshu/config.yaml`:

```yaml
vim_mode: true
```

### Modes

- `ESC` — NORMAL mode
- `i` — INSERT mode
- `:` — COMMAND mode

### Navigation (NORMAL mode)

- `h/j/k/l` — Left/Down/Up/Right
- `w/b` — Word forward/backward
- `0/$` — Line start/end
- `gg/G` — File start/end

## Auto-Completion

Press `Tab` for completions:

```
> /sess[Tab]
> /session

> /memory s[Tab]
> /memory search
```

## Multiline Input

Enable multiline mode:

```yaml
multiline_input: true
```

**Usage:**
```
> def hello():
...     print("Hello!")
...     return True
... [Empty line to execute]
```

## History

### View History

```
> /history

Command History:
1: create a Python script
2: /memory search Docker
3: /session new
```

### Search History

`Ctrl+R` then type search term

### Clear History

```
> /clear
✅ Command history cleared.
```

## Configuration in Session

```
> /config
[Shows all configuration]

> /config model
model: poolside/laguna-s-2.1:free

> /config model llama-3-70b
Set model = llama-3-70b
```

## Session Persistence

### Automatic Save

- Sessions saved automatically
- History persists across sessions
- Semantic memories preserved

### Manual Session Management

```
> /session new
🆕 New session: 7f3a2b1c...

> /session list
[Shows all sessions with timestamps]

> /session switch 7f3a2b1c
✅ Switched to session: 7f3a2b1c...
```

## Examples

### Development Workflow

```
> /agent
> create a REST API with Flask validation and error handling
[Generates and executes plan]

> /ask
> explain the error handling approach
[Gets explanation]

> /memory search Flask error handling
[Recalls past discussions]
```

### Multi-Session Work

```
# Session 1: Setup
> /session new
> set up development environment

# Session 2: Development
> /session new
> work on feature X

# Return to Session 1
> /session list
> /session switch [first-id]
```

## Next Steps

- **[Commands Reference](commands.md)** — All commands
- **[Keyboard Shortcuts](keyboard-shortcuts.md)** — Complete shortcuts
- **[Session Management](sessions.md)** — Advanced session features
