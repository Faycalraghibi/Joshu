# Agent

Joshu's agent works on a task with tools: it reads and searches files, edits
them, and runs commands, and it sees each result before deciding the next step.
It keeps going until it can answer without calling another tool.

## Running it

```bash
joshu run "add a --verbose flag to the CLI and test it"   # one task, approvals in the terminal
joshu interactive                                          # conversation; /agent mode is the default
```

Headless (scripts, CI):

```bash
joshu run -p "summarize what src/joshu/core/agent.py does"
joshu run --output-format json "list the TODOs in src/"
```

`-p` / `--print` prints only the final answer. `--output-format json` prints one
JSON object: `result`, `turns`, `tool_calls`, `usage`, `model`, `session_id`.
Headless runs can't ask for approval, so tools that need it are denied unless
the permission mode allows them.

Flags for scripts and CI (Claude Code's `claude -p` spellings work too):

| Flag | What it does |
|---|---|
| `--allowed-tools` / `--allowedTools` | Tools that run without asking, as permission rules: `read_file`, `run_shell_command(git log*)`, or Claude Code's `Read`, `Bash(git log:*)`. Repeatable or comma-separated |
| `--disallowed-tools` / `--disallowedTools` | Tools that are refused; a bare name isn't offered to the model at all |
| `--system-prompt` | Replace the system prompt |
| `--append-system-prompt` | Add instructions at the end of the system prompt |
| `--max-turns N` | Stop the request after N model turns |
| `--add-dir PATH` | Let the file tools work in another directory too (repeatable) |
| `--mcp-config FILE` | MCP servers from a JSON file (`{"mcpServers": {...}}`, as in `.mcp.json`) |
| `--settings JSON\|FILE` | Settings for this run only (a JSON object, or a JSON / YAML file) |
| `--session-id ID` | Save the new conversation under this id (`--resume ID` continues it) |
| `--fork-session` | With `--resume` / `--continue`: continue in a copy, the saved conversation stays as it was |

None of them change your saved configuration.

```bash
joshu run -p --allowedTools "Bash(npm test:*),Edit" --max-turns 30 \
  --append-system-prompt "Don't touch the migrations." "fix the failing test"
```

## Images

Attach screenshots, diagrams or mockups by referencing them as `@path` in a
request, or with `--image` (repeatable):

```bash
joshu run "why does the layout in @screenshots/home.png overflow on mobile?"
joshu run --image error.png "explain this error dialog"
```

The same `@path` syntax works in interactive mode. PNG, JPEG, GIF and WebP
files up to 5 MB are sent to the model with the request; references to other
file types are left as text. The model must support images (most current
OpenAI, Anthropic and Gemini models, and many models on OpenRouter, do).

## Model provider

The agent works with any provider that has an OpenAI-compatible API and a
model with tool calling: OpenRouter, OpenAI, Anthropic, Gemini, Groq, Mistral,
local servers like Ollama or LM Studio, or a custom endpoint. Pick one with
`provider` and `model` in config, or `--provider` / `--model` per run; list
them with `joshu providers`. See [Models & Providers](models-and-providers.md).

## Permissions

Every tool call passes a permission check before it runs.

| Mode | Behavior |
|---|---|
| `default` | Read-only tools run freely; edits, shell commands, web fetch and MCP tools ask first |
| `accept_edits` | File edits run without asking; shell commands still ask |
| `auto` | File edits run without asking; other actions that would ask (shell commands, web fetch, MCP tools) are reviewed by a model against your request: allowed ones run, blocked ones ask you with the reason (and are refused in headless runs). `auto_mode_model` picks the reviewing model (default: the main one) |
| `plan` | Read-only: anything that changes state is denied |
| `bypass` | Everything runs |

In every mode, a shell command flagged by the safety check asks for an explicit
yes (and is denied in headless runs).

Approval prompts show a diff for edits and the command line for shell calls.
Answer `y` (yes), `a` (always: stop asking for this tool, or for this
program and subcommand such as `git status`, for the rest of the session) or
`n` (no; the model is told the call was denied).

Set the mode with `--permission-mode`, `-y` (bypass), the `permission_mode`
config value, or `/permissions <mode>` in interactive mode. `/plan` switches to
plan mode.

In plan mode (interactive), the agent investigates, then shows its plan with
`exit_plan_mode` and asks whether to carry it out: **Yes, accept edits**
switches to accept-edits mode, **Yes, ask before edits** to default mode, and
the agent starts on the plan in the same request; **No, keep planning** (or
typing what to change) keeps it in plan mode with your feedback.

### Secrets

Files that usually hold credentials are protected: `.env` and `.env.*`,
`*.env`, private keys (`*.pem`, `*.key`, `id_rsa*`, `id_ed25519*`, ...),
`.npmrc`, `.pypirc`, `.netrc`, `.git-credentials`, `credentials`,
`service-account*.json`, and everything under `.ssh`, `.aws`, `.gnupg`,
`.azure`, `.kube` and `.docker`. Templates such as `.env.example` are not.

- Reading or editing a protected file asks first in every mode, bypass and
  plan included, and the answer applies to that call only.
- Shell commands that name a protected file (`cat .env`) or print the
  environment (`env`, `printenv`, `set`, `Get-ChildItem Env:`) ask first too.
- `search_file_content` skips protected files.
- API keys, tokens, private keys and `KEY=value` lines with secret-looking
  names are masked in every tool result (`[redacted NVIDIA key]`), so they
  never reach the model or saved sessions. Code such as
  `os.environ["API_KEY"]` is left alone.

```yaml
protected_paths: ["*.secret.yaml"]   # more patterns
allow_paths: [".env.test"]           # exceptions
mask_secrets: true
```

An allow rule (`permissions: allow: ["read_file(.env.test)"]`) also lets a
specific protected file through.

### Permission rules

Rules that last beyond the session go under `permissions` in config:

```yaml
permissions:
  allow:
    - run_shell_command(git status*)
    - run_shell_command(npm test*)
    - write_file(docs/*)
  deny:
    - write_file(.env*)
    - run_shell_command(git push*)
```

A rule is a tool name, optionally with a glob over its main argument (the
command for `run_shell_command`, the path for file tools, the URL for
`web_fetch`). Deny rules block the call without asking, in every mode. Allow
rules skip the prompt; commands flagged as unsafe still ask. In interactive
mode, `/permissions allow <rule>` and `/permissions deny <rule>` save a rule
to your user config.

## Tools

| Tool | Purpose | Asks first |
|---|---|---|
| `read_file`, `list_directory`, `glob`, `search_file_content` | Explore the workspace | no |
| `replace` | Exact-string edit | yes |
| `write_file` | Create or overwrite a file | yes |
| `delete_file` | Delete one file in the workspace (not a folder); undone by `/rewind` | yes |
| `multi_edit` | Several exact-text edits to one file, all or nothing (loaded on demand) | yes |
| `notebook_edit` | Replace, insert or delete a Jupyter notebook cell (loaded on demand) | yes |
| `code_nav` | Definition, references or hover from the language server (loaded on demand) | no |
| `run_shell_command` | Run a command (fresh shell each call; `background: true` for long-running ones) | yes |
| `bash_output`, `kill_bash` | Read the output of / stop a background command (loaded when one starts); `bash_output` can wait, `until` its output matches a regex (a server's "Listening on") or, with `timeout` alone, until it ends | no |
| `web_search` / `web_fetch` | Search the web / fetch a URL | no / yes |
| `write_todos` | Track steps | no |
| `memory` | Save, read or delete notes kept across sessions | no |
| `skill` | Load a skill's instructions (when skills exist) | no |
| `task` | Delegate research to a read-only sub-agent, or (`edit: true`) changes to one working in its own git worktree; `background: true` runs a read-only one while the agent goes on | no |
| `task_output` | The answer of a background task, or that it's still running (loaded when one starts) | no |
| MCP tools | Tools from configured MCP servers (loaded on demand with `load_tools` when there are many) | yes |

### Parallel tool calls

When the model asks for several read-only calls in one turn (`read_file`,
`list_directory`, `glob`, `search_file_content`, `web_search`, `web_fetch`,
`bash_output`, `skill`, `task`), they run at the same time, up to 4 at once;
results are shown and sent back in the original order. Edits, shell commands,
calls that need approval (such as reading a protected file) and custom
sub-agents with write tools run one at a time. The gain is largest for slow
calls: three sub-agents in one turn finished in 9.5s instead of 26s. Turn it
off with `parallel_tools: false`.

### Recovering from tool-call mistakes

Smaller and open models often get tool calls slightly wrong. Joshu repairs
what it safely can instead of rejecting the call:

- Arguments that aren't quite JSON: code fences, trailing commas, Python-style
  `{'path': 'a.py', 'x': True}`, text around the object, double-encoded JSON,
  or output cut off before the closing brace.
- Near-miss tool names: `ReadFile`, `functions.read_file`, `bash`,
  `str_replace`, `grep` and similar map to the matching built-in tool (only
  among the tools the agent offers, and still subject to permissions).
- Errors say what to do next: an unknown tool lists the available ones, bad
  arguments list the tool's parameters, and a `replace` whose `old_string`
  isn't found shows the closest matching lines (or the lines that differ only
  in indentation) to copy from.
- The same call returning the same result 3 times in a row gets a warning
  appended for the model; at 5 the request stops (`stopped: loop` in JSON
  output).

`replace` keeps a file's line endings (LF or CRLF) as they are.

See [benchmarks/](../benchmarks/README.md) for measuring how a model does on
real tasks.

## Instructions

Put instructions for the agent in Markdown files; all that apply are added to
its system prompt, least specific first:

| File | Applies to |
|---|---|
| `~/.joshu/AGENTS.md` | every project |
| `AGENTS.md` or `JOSHU.md` in the repository root | the repository |
| `AGENTS.md` or `JOSHU.md` in a subdirectory | work in that directory (and below) |
| `config/JOSHU.md` | the repository (older location) |

The repository root is the nearest directory with `.git` above the working
directory. Facts saved by older versions with `save_memory` (in
`~/.joshu/JOSHU.md`) are still included.

## Context

- The system prompt includes the working directory, OS, shell, date, git
  branch, instruction files and saved memory (see Instructions).
- When the conversation reaches `compact_threshold × context_window` (estimated
  tokens), older turns are replaced by a model-written summary; the most recent
  turns stay verbatim.
- Long tool output is cut to `tool_output_limit` characters (head and tail kept).

## Undo

Before `replace` or `write_file` changes a file, the agent records the file's
original content (or that it didn't exist). `/undo` reverts every file the
agent edited for its most recent request, newest first on repeated use, and
the model is told at the start of the next request. Changes made through shell
commands are not tracked.

## Sessions

Every conversation is saved after each request to
`~/.joshu/sessions/<id>.json` (set `JOSHU_HOME` to move it, or
`save_sessions: false` to turn it off). An interrupted request is saved too.

```bash
joshu sessions                         # sessions started in this directory (--all for every one)
joshu run --continue "and now the tests"
joshu run --resume 3f2a9c "pick up where we left off"
joshu interactive --continue
```

In interactive mode, `/resume` lists recent sessions and `/resume <id>`
continues one. A unique prefix of the id is enough. Headless JSON output
includes `session_id`, so scripts can continue a conversation across calls.

## Custom commands

Reusable prompts are files in `.joshu/commands/` (project) or
`~/.joshu/commands/` (user); project files win on a name clash. Run one as
`/name args` in interactive mode, or `joshu run "/name args"`; `/commands`
lists them.

Markdown: the body is the prompt, `$ARGUMENTS` or `{{args}}` is replaced by
the text after the command name (or the text is appended if neither appears).

```markdown
---
description: Review a file for bugs
---
Review $ARGUMENTS for bugs and risky patterns. Report file:line for each issue.
```

TOML: same format as extension commands, with an optional `shell` step whose
output fills `{{shell_output}}`. The shell step needs the same approval as the
agent's shell tool.

```toml
description = "Explain the working tree changes"
shell = "git diff --stat"
prompt = "Explain these changes:\n{{shell_output}}\n{{args}}"
```

Built-in commands (`/help`, `/undo`, ...) can't be overridden.

## Memory

The agent keeps notes across sessions with its `memory` tool: what you ask it
to remember, and things it learns that aren't in the code (your preferences,
corrections to how it works, project decisions, where to find things).

| Scope | Location | Applies to |
|---|---|---|
| project (default) | `~/.joshu/projects/<project>/memory/` | this repository |
| user | `~/.joshu/memory/` | every project |

Each memory is a Markdown file with a name, a one-line description and a type
(`user`, `feedback`, `project`, `reference`); `MEMORY.md` in each directory
indexes them. At the start of a session short memories are added to the
system prompt in full and longer ones by description, for the agent to read
when relevant. Saving under an existing name replaces that memory.

In interactive mode, `/memory` lists memories and `/memory forget <name> [user]`
deletes one; the files can also be edited directly. Turn memory off with
`joshu config --set auto_memory=false` (the older `save_memory` tool is then
used instead).

## Skills

A skill is a set of instructions for a kind of task, loaded only when needed:

```
.joshu/skills/release-notes/
    SKILL.md
    template.md        # optional supporting files
```

```markdown
---
name: release-notes
description: Write release notes from the git log. Use when asked for release notes or a changelog.
---
1. Find the last tag with `git describe --tags --abbrev=0`.
2. ...follow template.md
```

Only each skill's name and description are in the system prompt. When a task
matches, the agent calls the `skill` tool to load the instructions (and any
supporting file), so skills cost little context until used.

Skills are read from `.joshu/skills/` and `.agents/skills/` in the working
directory and the repository root, then `~/.joshu/skills/` (a project skill
replaces a user skill with the same name). A skill needs a `description`.

In interactive mode, `/skills` lists them and `/<skill> [request]` runs one.
A skill with `disable-model-invocation: true` in its frontmatter only runs when
you type `/<skill>`; the agent doesn't see it.

### Installing skills

Skill pages usually show an `npx skills add` command. Joshu takes the same
sources and puts the skills where it reads them:

```bash
joshu skills add mattpocock/skills --skill grill-me     # into .agents/skills/
joshu skills add mattpocock/skills --skill grill-me -g  # for you: ~/.joshu/skills/
joshu skills add mattpocock/skills                      # pick from a menu (or --all)
joshu skills                                            # list
joshu skills remove grill-me
```

In interactive mode: `/skills add <source> [--skill name] [-g]` and
`/skills remove <name>`. You can also paste the page's command as is
(`/skills add npx skills add o/r --skill x`, or `!npx skills add ...`), or just
ask ("add this skill: npx skills add o/r --skill x"): when the agent runs
`npx skills add`, Joshu installs the skill itself. Either way the skill is
usable right away, without restarting.

Sources are anything `npx skills add` accepts (a GitHub `owner/repo`, a
repository URL, ...); Joshu runs that tool in a temporary directory and copies
the skills out, so nothing else is added to your project. Without Node.js,
GitHub sources are fetched with `git clone`, and a local directory works too.
Skills run with the agent's permissions: read a skill's SKILL.md before
using it.

## Sub-agents

The `task` tool hands a self-contained job to a sub-agent and returns its final
answer, keeping the main conversation small. By default it is a read-only
researcher. Joshu delegates when it sees fit, or when you ask ("use a
sub-agent to find every caller of `parse`"), and you can run one yourself:

```
/agents                               # built-in and your sub-agents
/subagent research where are sessions saved and when?
/subagent editor rename `load_cfg` to `load_config` everywhere
/agents new reviewer Reviews a change for bugs and risky patterns
/subagent reviewer review the last commit
```

Its answer is added to the conversation, so Joshu knows what it found or did.
`research` is read-only; `editor` works in its own git worktree (see below). Define specialized ones in `.joshu/agents/` (project) or
`~/.joshu/agents/` (user):

```markdown
---
description: Reviews a change for bugs and risky patterns
tools: read_file, glob, search_file_content
model: openai/gpt-4.1          # optional: another model of the same provider
max_turns: 15                  # optional
---
You are a careful code reviewer. Report only real problems, with file:line.
```

The main agent sees each sub-agent's description and picks one by name. A
sub-agent with a `tools` list gets exactly those tools and uses the main
agent's permission gate, so its edits and commands still ask you. Without a
`tools` list it is read-only. `/agents` lists the defined sub-agents. YAML/JSON
definitions in the `joshu.agents` format also work (use `model_name: inherit`
for the main model).

### Sub-agents that delegate

A sub-agent can hand part of its own task to a sub-agent in turn, for example a
researcher that splits a large survey in parts. These nested sub-agents are
read-only. How deep it goes is the `subagent_depth` setting: `2` (default) lets
sub-agents start their own, which can't go further; `1` keeps sub-agents from
delegating at all.

### Background sub-agents

With `background: true` the main agent starts a read-only sub-agent and goes on
with other work (or finishes its reply) while it runs. The answer comes back by
itself: between the agent's turns, or with your next message if the request
has ended. The agent can also read it, or wait for it, with `task_output`.
Before finishing a reply while some are still running, the agent is told once,
so it can wait for an answer it needs. The bar under the input shows
`N agents working`. A background sub-agent shows no tool calls of its own.

With `edit: true` too, it works in its own git worktree like an editing
sub-agent (below), and its changes are applied to your working tree when it
finishes (or kept on its branch if they don't apply); the report says which.
It can't ask for approval from the background, so what would ask is refused:
use it in accept-edits, auto or bypass mode.

### Sub-agents that edit

In a git repository (and outside plan mode), `task` with `edit: true` gives
the sub-agent the full set of tools in its own **git worktree**: a separate
checkout of `HEAD` on a new branch `joshu/<task>-<id>`, under
`~/.joshu/worktrees/`. It edits and runs commands there, with the main agent's
permission gate (so it asks you like the main agent does), and several such
tasks can run at once without touching each other.

When it finishes, its changes are committed on the branch and applied to your
working tree, uncommitted, like any other edit (and recorded in the request's
checkpoint, so `/rewind` undoes them). Then the worktree and the branch are
removed. If the patch doesn't apply, nothing is applied: the work stays on the
branch and the result says how to merge it (`git merge joshu/...`).

The worktree starts as the project is: `HEAD` plus your uncommitted changes
and untracked files (not ignored ones, nor files over 5 MB), committed there
as a first "seed" commit. Only the sub-agent's own work, the diff from that
seed, is applied back, on top of your uncommitted changes. If you change the
same lines while it works, the patch doesn't apply and its work stays on the
branch.

## Background jobs

A request can run on its own, and keep running after you close the terminal:

```bash
joshu run --background "migrate the tests to pytest"    # or /background ... in a session
joshu jobs                    # list: running, done, failed, stopped
joshu jobs show <id>          # its answer, changed files, log while it runs
joshu jobs apply <id>         # put its work into your working tree (uncommitted)
joshu jobs approve <id>       # let a waiting job run the command it asks for (or: deny)
joshu jobs stop <id>          # end a running one
joshu jobs log <id>           # the job process's output
```

A job works in its own git worktree (the project as it is, uncommitted
changes included, like an editing sub-agent) in `accept_edits` mode by
default: edits run, and a call that needs approval (a shell command your
permission rules don't allow) waits for you. `joshu jobs` shows it as
"waiting for you" with the command; `joshu jobs approve <id>` lets it run,
`joshu jobs deny <id>` refuses it (the job carries on without it). Unanswered
for `job_approval_timeout` seconds (default 1800), it's refused.
`--permission-mode bypass` (or `-y`) runs commands without asking. When it finishes, its work is committed on
a branch `joshu/job-<id>` and the worktree is removed; `apply` puts the work
in your working tree when it still applies (else merge the branch), and the
session is saved, so `joshu trace <session>` shows its timeline. Records are
in `~/.joshu/jobs/`.

## Checks after edits

After `replace` or `write_file` succeeds, the edited file is checked and any
problems are added to the tool result, so the agent fixes them in the same
request:

| Files | Check |
|---|---|
| `.py` | Syntax, plus ruff's error rules (undefined names, invalid code; no style) when ruff is installed |
| `.json`, `.yaml`, `.yml`, `.toml` | Must parse |
| `.js`, `.mjs`, `.cjs` | `node --check` when node is installed |

Add or replace checks per extension; `{file}` is the edited file and a
non-zero exit means problems:

```yaml
diagnostics:
  .go: go vet {file}
  .ts: npx tsc --noEmit {file}
  .py: ""        # turn the built-in Python check off
```

`diagnostics_enabled: false` turns checking off.

### Language servers

When a language server is installed, Joshu starts it the first time it's
needed and keeps it running for the session. After an edit that passes the
checks above, the server's **errors** for the file (type errors, wrong
arguments, missing imports, ...) go back to the model the same way:

| Language | Servers looked for |
|---|---|
| Python | `basedpyright-langserver`, `pyright-langserver`, `pylsp` |
| JavaScript / TypeScript | `typescript-language-server` |
| Go | `gopls` |
| Rust | `rust-analyzer` |

Install one, e.g. `pip install basedpyright` or `npm install -g pyright`;
`/doctor` shows which are found. The `code_nav` tool (loaded on demand) asks the
server for a symbol's **definition**, its **references** or **hover**
information (type and docs); the model can give the symbol's name instead of an
exact position.

```yaml
lsp:
  python: pylsp        # pick the command for a language
  rust: ""             # don't use a server for Rust
# lsp: false           # no language servers at all
```

## Shell sandbox

Shell commands the agent runs (and custom-command shell steps) can run in an
OS-level sandbox: they can write only inside the working directory and temp
files, with no network unless allowed.

```yaml
shell_sandbox:
  mode: auto          # off (default) | auto | bubblewrap | seatbelt | docker
  network: false
  image: python:3.12-slim   # docker only
  auto_allow: true    # sandboxed commands run without asking
```

| Backend | Platform | Notes |
|---|---|---|
| `bubblewrap` | Linux | Needs `bwrap`; on Ubuntu 24.04, unprivileged user namespaces must be allowed |
| `seatbelt` | macOS | Uses the built-in `sandbox-exec` |
| `docker` | Any (incl. Windows) | Commands run in a Linux container with the project at `/workspace` |

`auto` picks the first backend that works. With `auto_allow`, sandboxed
commands skip the approval prompt; commands flagged as unsafe still ask, and
plan mode still denies the shell. If the requested sandbox isn't available,
Joshu says so at startup and commands run unsandboxed, needing approval as
before. With Docker, a command that times out stops waiting but the container
may keep running until it finishes.

## Cost

Each response's cost is added up for the conversation. OpenRouter reports the
cost of every request; for other providers, give prices in USD per million
tokens:

```yaml
model_pricing:
  gpt-4.1-mini: {input: 0.40, output: 1.60}
```

When a request's price is unknown the total is shown as unknown rather than
undercounted. The cost appears in the footer after each request, as
`cost_usd` in `--output-format json`, in `/cost`, and in saved sessions;
sub-agents are included.

## Configuration

| Key | Default | Meaning |
|---|---|---|
| `permission_mode` | `default` | See above |
| `agent_max_turns` | `50` | Model calls per request before stopping |
| `self_review` | `true` | One check of the work against the request before finishing, when files were edited or commands run |
| `context_window` | `128000` | Model context size in tokens |
| `compact_threshold` | `0.8` | Fraction of the window that triggers compaction |
| `tool_output_limit` | `16000` | Max characters of one tool result sent to the model (`read_file` returns up to ~40,000 in whole lines) |
| `clear_tool_results_at` | `60000` | Clear old tool results past this many tokens (0 = never) |
| `max_tokens` | `8192` | Max output tokens per model response (raised automatically, up to 32,768, when a response is cut off) |
| `provider` | `openrouter` | Model provider (see `joshu providers`) |
| `providers` | `{}` | Custom providers and overrides |
| `fallback_providers` | `[]` | Providers or named models tried when the model can't serve a request |
| `request_retries` | `3` | Retries per model request (connection errors, 429, 5xx) |
| `save_sessions` | `true` | Save conversations for `--resume` / `--continue` |
| `hooks` | `{}` | Commands run on agent events (see [Hooks](hooks.md)) |
| `diagnostics_enabled` | `true` | Check files after edits |
| `diagnostics` | `{}` | Per-extension check commands |
| `shell_sandbox` | `{mode: off}` | OS sandbox for shell commands |
| `model_pricing` | `{}` | USD per million tokens, for providers that don't report cost |

## Interactive commands

- `/agent`, `/plan`, `/ask`: switch mode (`ask` answers without tools)
- `/permissions [mode]`: show or set the permission mode
- `/undo`: revert the agent's file edits from its last request
- `/rewind [n]`: drop the last n requests and restore the files they changed
- `/compact [focus]`: summarize the conversation now
- `/init [notes]`: write or update AGENTS.md for this project
- `/memory`, `/memory forget <name>`: the agent's saved memories
- `/skills`, `/<skill> [request]`: list skills, run one
- `/cost`: tokens and cost of the conversation
- `/resume [id]`: list saved sessions, or continue one
- `/commands`, `/agents`: list custom commands and sub-agents
- `/reset`: start a new agent conversation
- Esc or Ctrl+C: interrupt the current task; the conversation stays usable.
  Text typed while the agent works becomes the next prompt.

## Hooks

Commands configured under `hooks:` run on `before_agent`, `after_agent`,
`before_tool` and `after_tool` (see [Hooks](hooks.md)). A `before_tool` hook
can block a call (the model is told why) or rewrite its arguments.
