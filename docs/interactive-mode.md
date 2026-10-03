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

Sessions are the saved agent conversations: the same ones `joshu sessions`,
`--resume` / `--continue` and `/resume` use (see [Agent](agent.md#sessions)).

```
/session              # Current session id
/session list         # Saved sessions in this directory
/session new          # Start a new conversation (also /reset, /new-session)
/session switch <id>  # Continue a saved session (also /resume <id>)
/session delete <id>  # Delete a saved session
/session help         # Session help
```

An id prefix is enough.

### Conversation

```
/undo              # Revert the agent's file edits from its last request
/rewind [n]        # Drop the last n requests (default 1) and restore the files they changed
/compact [focus]   # Summarize the conversation now, optionally saying what to keep
/init [notes]      # Have the agent write or update AGENTS.md for this project
```

`/rewind` removes the requests and everything the agent did for them from the
conversation, restores files the agent edited meanwhile, and puts the first
removed request back in the prompt so you can edit and resend it. Changes
made by shell commands are not undone, and requests already summarized by
compaction can't be rewound.

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
| `Esc` | Interrupt the agent (while it works) |
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

### While the agent works

`Esc` (or `Ctrl+C`) stops the current request. The conversation stays usable:
send a follow-up, or `/rewind` to drop the interrupted request.

Anything you type while the agent works is kept and appears in the prompt when
it finishes, ready to edit and send. Approval prompts read their answer as
usual.

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

Press `Tab` to complete slash commands, including your custom commands:

```
> /rew[Tab]
> /rewind
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
New session: 7f3a2b1c9d0e

> /session list
[Saved sessions in this directory, newest first]

> /session switch 7f3a2b
Resumed session 7f3a2b1c9d0e (12 messages): set up development environment
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
