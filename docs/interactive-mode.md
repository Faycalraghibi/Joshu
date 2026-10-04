# Interactive Mode

Complete guide to Joshu's interactive mode.

## Starting Interactive Mode

```bash
joshu                     # same as joshu interactive
joshu interactive --model fast --verbose
joshu --continue          # pick up the last conversation here
```

## Interface Overview

```
╭──────────────────────────────────────────────────────────────────────────╮
│     ✦     ✦ Welcome to Joshu  v0.3.0                                     │
│   ╭─┴─╮   /help for commands · ? for shortcuts · shift+tab to switch mode│
│   │•‿•│                                                                  │
│   ╰───╯   cwd    /home/me/project                                        │
│           model  nvidia/nemotron-3.5-lightning-30b-a3b  nvidia           │
╰──────────────────────────────────────────────────────────────────────────╯

──────────────────────────────────────────────────────────────
> fix the failing test in calc.py
──────────────────────────────────────────────────────────────
  ⏵⏵ accept edits on (shift+tab to cycle)        nvidia/nemotron…

● Read(calc.py)
  ⎿  Read 6 lines

● Update(calc.py)
  ⎿  Updated calc.py with 1 addition and 1 removal
     2 -     return a - b
     2 +     return a + b

● Bash(python -m pytest -q)
  ⎿  2 passed in 0.03s

● Fixed: add() subtracted instead of adding.
```

- **Input**: type after `>`; the line below shows the mode and the model.
  `?` lists shortcuts.
- **While the agent works**: a line saying what it's doing, e.g.
  `✦ Running pytest -q… (12s · esc to interrupt)`.
- **Tool calls**: `● Tool(argument)` with the result under `⎿`: line counts
  for reads, a colored diff for edits, the first lines of command output,
  and a checklist for the agent's todos.
- **Replies**: rendered as Markdown.
- **Approvals**: a panel with the diff or command, then a menu (arrow keys,
  a number, or Esc): *Yes*, *Yes, and don't ask again* for that tool (or
  command, e.g. `git status`) this session, or *No, and tell Joshu what to
  do differently*, whose note is passed to the agent.

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

Type `/` to open the command menu (with descriptions); `/help` shows the same
list. Custom commands (`.joshu/commands/`) and skills appear there too.

**Conversation**

| Command | What it does |
|---|---|
| `/clear` | Start a new conversation; the old one stays saved (also `/reset`, `/new`) |
| `/compact [focus]` | Summarize the conversation to free context, optionally saying what to keep |
| `/rewind [n]` | Go back to an earlier request (a menu; or drop the last n) and restore the files the agent changed since. Also Esc Esc on an empty prompt |
| `/undo` | Revert the file edits of the last request |
| `/resume [id]` | List saved conversations here, or continue one |
| `/export [file]` | Save the conversation as Markdown |
| `/session [list\|switch <id>\|delete <id>]` | Manage saved sessions |

**Context**

| Command | What it does |
|---|---|
| `/context` | How much of the context window is used: system prompt, tools, conversation |
| `/cost` | Tokens and cost so far |
| `/todos` | The agent's current todo list |
| `/memory` | The agent's saved memories (`/memory forget <name> [user]` deletes one) |
| `/init [notes]` | Have the agent write or update AGENTS.md |

**Model & mode**

| Command | What it does |
|---|---|
| `/model [id]` | Show or switch the model for this conversation |
| `/models [search]` | List the provider's models |
| `/agent`, `/plan`, `/ask` | Switch mode (Shift+Tab cycles default / accept edits / plan) |
| `/permissions [mode]` | Show or set the permission mode and rules |

**Project**

| Command | What it does |
|---|---|
| `/review [focus]` | Have the agent review the current changes for bugs |
| `/security-review [focus]` | Review the current changes for security issues (injection, auth, secrets, ...) |
| `/pr-comments [number]` | Bring a pull request's review comments into the chat (uses `gh`) |
| `/add-dir <path>` | Let the agent read and edit files in another directory this session |
| `/bashes [kill <id>]` | Commands the agent started in the background; stop one |
| `/hooks [add <event> <command> \| remove <event> <n>]` | Show, add or remove hooks |
| `/skills`, `/agents`, `/commands` | List skills, sub-agents, custom commands |
| `/mcp` | MCP servers, whether they're connected and how many tools each has |
| `/search <query>` | Search the web |

**Settings**

| Command | What it does |
|---|---|
| `/status` | Version, directory, session, provider, model, mode, theme, loaded config |
| `/doctor` | Check the setup: provider, API key, a live model check, git / rg / node |
| `/config [key [value]]` | Show or set a setting |
| `/theme [name]` | Choose the color theme (dark, light, colorblind, plain) |
| `/vim` | Toggle vim keys in the input |
| `/output-style [name]` | How replies are written: `default`, `concise`, `explanatory`, `learning`, or your own |
| `/statusline [command\|off]` | Show a command's output under the input |
| `/sandbox [mode]` | Show or set the shell sandbox (`off`, `auto`, `bubblewrap`, `seatbelt`, `docker`) |
| `/terminal-setup` | How to make Shift+Enter insert a new line in your terminal |

**Other**: `/help`, `/history [clear]`, `/release-notes`, `/exit` (or `/quit`).

### Output styles

Custom styles are Markdown files in `.joshu/output-styles/` or
`~/.joshu/output-styles/`; the file name is the style name, an optional first
line `description: ...` describes it, and the rest is added to the system
prompt.

### Status line

`/statusline <command>` runs the command (at most every 5 seconds, 1 second
timeout) with the session as JSON on stdin (`model`, `cwd`, `mode`,
`session_id`, `theme`) and shows its first output line at the right of the
line under the input, e.g.:

```
/statusline git branch --show-current
```

### Background commands

The agent can start long-running commands (dev servers, watchers, long test
runs) with `background: true`, read their output while they run
(`bash_output`) and stop them (`kill_bash`). `/bashes` lists them.

`/rewind` removes the requests and everything the agent did for them from the
conversation, restores files the agent edited meanwhile, and puts the first
removed request back in the prompt so you can edit and resend it. Changes
made by shell commands are not undone, and requests already summarized by
compaction can't be rewound.

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

See [Keyboard shortcuts](keybindings.md) for the full list. The most used:

| Shortcut | Action |
|----------|--------|
| `Esc` | Interrupt the agent (while it works); clear the input (at the prompt) |
| `Shift+Tab` | Cycle modes: default → accept edits → plan |
| `Alt+Enter`, `\` + `Enter` | New line (Shift+Enter after `/terminal-setup`) |
| `Ctrl+G` | Write the prompt in your editor |
| `Ctrl+R` | Search input history |
| `Ctrl+O` | Show the last request's tool output in full |
| `Alt+V` | Attach the image in the clipboard (also `/paste`; needs `pip install pillow`) |
| `?` | Show shortcuts |

### While the agent works

`Esc` (or `Ctrl+C`) stops the current request. The conversation stays usable:
send a follow-up, or `/rewind` to drop the interrupted request.

The reply appears as it is written, and the line under it shows the elapsed
time and output tokens so far (or the task in progress from the todo list).
Models that stream their reasoning show it as dim text while they think; it
then folds to one line ("Thought for 3s"). Tool output is cut to a few lines; `Ctrl+O` shows it in full from then on.
Anything you type while the agent works is kept
and appears in the prompt when it finishes, ready to edit and send.

## Vim Mode

Toggle with `/vim`, or set in `~/.joshu/config.yaml`:

```yaml
vim_mode: true
```

The input then uses vi editing: `Esc` for NORMAL mode (the prompt shows `N`),
the usual motions and edits, and `i` / `a` to insert again.

## Auto-Completion

Typing `/` opens a menu of commands with descriptions; `@` completes file
paths in the project (skipping `.git`, `node_modules` and build folders):

```
> /re
  /reset              same as /clear
  /resume [id]        List saved conversations, or continue one
  /review [focus]     Review the current changes for bugs
  /rewind [n]         Go back to an earlier request and restore its files

> explain @cal
  src/calc.py
```

## Themes

`/theme` opens a picker with a preview; the choice is saved as `theme` in your
user config.

| Theme | |
|---|---|
| `dark` | Default |
| `light` | For light terminal backgrounds |
| `colorblind` | Blue / orange instead of green / red for diffs and status |
| `plain` | No colors |

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
> /history clear
Input history cleared.
```

## Configuration in Session

```
> /config
[Shows all configuration]

> /config model
model: nvidia/nemotron-3.5-lightning-30b-a3b

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
