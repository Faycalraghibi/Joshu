# Changelog

All notable changes to the Joshu project will be documented in this file.

## [Unreleased]

### Added
- Plan approval: in plan mode the agent shows its finished plan (`exit_plan_mode`) and asks whether to carry it out. Approving switches to accept-edits or default mode and the agent implements the plan in the same request; otherwise it keeps planning with your feedback. Before, you had to switch modes yourself and ask again.
- The input box shown while a task runs can be edited: ←/→, Home/End (Ctrl+A/Ctrl+E), Delete and Ctrl+U (clear the line), with the cursor drawn where it is. The bar under the prompt redraws every second, so running shells and background agents update without a key press.
- Flags for scripted runs (`joshu run`, `-p`), with Claude Code's `claude -p` spellings: `--allowed-tools` / `--disallowed-tools` (permission rules; `Bash(git log:*)`, `Edit` and other Claude Code names work), `--system-prompt`, `--append-system-prompt`, `--max-turns`, `--add-dir`, `--mcp-config` (a `.mcp.json`-style file), `--settings` (JSON or a file, this run only), `--session-id` and `--fork-session`. A tool denied by a rule without a pattern is no longer offered to the model.
- Background sub-agents: `task` with `background: true` starts a read-only sub-agent and the agent goes on meanwhile. Its answer comes back by itself (between turns, or with your next message), or with the new `task_output` tool (`wait: true` to wait for it). An agent about to finish while some still run is told once. The bar under the input shows `N agents working`.
- Sub-agents can start sub-agents of their own (read-only), down to the `subagent_depth` setting: `2` (default) lets a sub-agent delegate once more, `1` keeps the old behaviour.
- `delete_file` tool: deletes one file in the project (not a folder), with the same approval as edits (asked in default mode, automatic in accept-edits and bypass, refused in plan mode; `.env` and keys always ask) and undoable with `/rewind`. Before, an agent asked to remove a file had only `rm` / `del`, which the safety check blocks; in a run with no one to approve (`joshu run`, `-p`) the file could never be deleted. A blocked shell delete now points to the tool.
- The input box stays at the bottom while a task runs, as in Claude Code: under the working line, with what you type, the messages queued for when the task ends listed above it, and what Enter will do (queue it, or ask a `/btw` question now) and the mode below it.
- Messages sent with Enter while a task runs are queued and go by themselves when it ends; Ctrl+B moves a running shell command to the background; the bar under the input shows the context use from 50% (`context 72%`, suggesting `/compact` from 80%).
- Slash commands from Claude Code that Joshu lacked: `/copy` (last reply to the clipboard), `/rename <title>`, `/fork` (continue in a copy of the conversation), `/login` / `/logout` (a provider's API key, saved in `~/.joshu/.env`), `/install-github-action` (writes the workflow) and `/feedback` / `/bug` (a pre-filled GitHub issue).
- `/btw <question>`: a side question answered from the conversation, without tools and without being added to it; it also works while a task runs (type it and press Enter). What you type during a task now shows under the working line.
- `/subagent <name> <task>` runs a sub-agent yourself (`research`, `editor`, or yours), its answer added to the conversation; `/agents` lists the built-in ones too, and `/agents new <name> <what it does>` creates one.
- Background jobs ask instead of refusing: a call that needs approval waits for `joshu jobs approve <id>` or `deny <id>` (also `/jobs`), shown as "waiting for you" in `joshu jobs`, and is refused after `job_approval_timeout` (1800 s).
- Prompt hooks: a hook entry with `prompt` (or a Claude Code hook of type `prompt`) asks a model (`hook_model`, or the configured one) to decide, with the event as JSON in `$ARGUMENTS`; `{"ok": false, "reason": ...}` blocks the event, or sends the agent back to work for `stop` (`joshu.hooks.prompt_hooks`).
- The OS sandbox hides credential locations from sandboxed commands (`shell_sandbox.hide`): by default `~/.ssh`, `~/.aws`, `~/.gnupg`, cloud CLI configs, `~/.kube`, `~/.docker`, `~/.netrc`, `~/.git-credentials`, `~/.npmrc`, `~/.pypirc` and `~/.joshu/config.yaml` (bubblewrap: an empty tmpfs or /dev/null over each; seatbelt: a read denial). Before, they could read the whole disk.
- In a project without tests, an agent that edited code and ran nothing since is asked once to check its change itself (run it or a small script) before finishing, when it can run commands; `verify_command: off` turns this off too.
- Background jobs: `joshu run --background "<request>"` (or `/background` in a session) runs a request detached, in its own worktree, after the terminal closes, in `accept_edits` mode by default. `joshu jobs` / `/jobs` lists them, `show` gives the answer and log, `apply` puts the work into the working tree, `stop` ends one (`joshu.core.jobs`).
- A trace of every conversation: each model call (seconds, tokens, tool calls, thinking on or off) and tool run (seconds, success), saved with the session. `joshu trace [session] [--json]` shows the timeline and totals, and benchmark triage reports seconds per model call (`joshu.core.trace`).
- Tests before finishing: when a request edited code and the agent didn't run the tests afterwards, Joshu runs the project's tests (the `verify_command` setting, or found: pytest, `npm test`, `go test`, `cargo test`) through the permission gate, and sends a failure back to fix, twice at most. A missing test runner turns it off for the session. Benchmark triage now tells `untested` (the project had tests) from `unchecked` (it had none).
- Claude Code plugins and marketplaces: `/plugin marketplace add owner/repo` and `/plugin install <plugin>@<marketplace>` (also `joshu plugin ...`) install them as they are: `.claude-plugin/plugin.json`, skills, commands, `agents/` (tool names translated), `hooks/hooks.json` (events, matchers, `${CLAUDE_PLUGIN_ROOT}`) and `.mcp.json`. Hook scripts written for Claude Code get the input fields they expect and their JSON output is understood. Plugin sources can be `owner/repo`. `/plugin` in a session loads what it installs at once (`joshu.core.claude_compat`).
- Sub-agents that edit: `task` with `edit: true` runs a sub-agent with the full tools in its own git worktree (a checkout of HEAD on a new branch), so several can change code at once. When one finishes, its work is applied to the working tree (uncommitted, undoable with `/rewind`), or kept on its branch when it touches files with local changes. File tools and shell commands follow the sub-agent's worktree (`joshu.core.worktrees`).
- A bigger hard benchmark tier: 10 new tasks (16 in all), with reference solutions checked by `--verify`. `benchmarks/compare.py` compares setups with pooled repeats and 95% intervals, saying whether a difference is shown or could be noise, and a `Benchmark` workflow runs the benchmark on GitHub by hand.
- `thinking` setting for reasoning models: `on` (default), `off`, or `auto`, which skips thinking on the call right after a round of successful reads and searches. Measured on NVIDIA's Nemotron Lightning, a one-sentence answer took 55.6 s with thinking and 2.7 s without. Providers declare their switch in `no_thinking_options` (NVIDIA and vLLM: `chat_template_kwargs.enable_thinking`, OpenRouter: `reasoning.enabled`).
- Managed settings: an administrator's `managed-settings.yaml` (`%ProgramData%\joshu`, `/Library/Application Support/joshu`, `/etc/joshu`, or `JOSHU_MANAGED_SETTINGS`) is the last config layer; its settings win and can't be changed, its `permissions` rules are added to everyone's, and `allow_bypass: false` rules out bypass mode. `joshu config --list` and `/doctor` show it.
- Plugins: `joshu plugin install <git-url | dir>` installs a bundle of skills, commands, output styles, hooks and MCP servers (`joshu-plugin.yaml`) into `~/.joshu/plugins/`, after showing what it adds; `list`, `update`, `enable`, `disable`, `remove`. The loaders search plugin directories after the project's and the user's own, and `${PLUGIN_DIR}` in hooks and MCP settings is the installed directory (`joshu.core.plugins`, [docs](docs/plugins.md)).
- A project map in the system prompt: the files grouped by directory with their top-level definitions (Python through `ast`; JS/TS, Go, Rust and Java by pattern), built once per conversation and capped near 1,500 tokens, so the agent goes to the right file instead of listing directories and reading files to learn the layout. `repo_map`: `auto` (default: only when the project fits), `always` (cut to fit), `never` (`joshu.core.repo_map`).
- Terminal tests with a scripted model (`tests/e2e/scripted_joshu.py`): questions with choices, the approval menu and diff, and the background shells viewer run in a real pseudo-terminal and are checked on the screen as drawn (`pyte`). A manual checklist for terminals is in the testing guide.
- Spending limits: `max_budget_usd` (the session's cost) and `max_request_tokens` (one request's tokens), as settings, `joshu run --max-budget-usd / --max-request-tokens`, SDK `Session` options and GitHub Action inputs. Checked before each model call, so every tool call keeps its result; the request ends with `stopped: "budget"`.
- `benchmarks/triage.py` tells why benchmark runs failed (provider error, no edits, out of time or turns, untested, gave up with failing tests, missed cases), from each run's conversation, which `benchmarks/run.py` now keeps next to the results (`--no-transcripts` to skip).
- Self-review: before finishing a request that edited files or ran commands, the agent is asked once to compare its work with the request (every asked-for change done, edge cases checked, tests run) and fix what is missing. On by default (`self_review: false` turns it off; sub-agents skip it). `benchmarks/run.py --set KEY=VALUE` runs a benchmark with a setting changed, to compare settings.
- Background shells viewer: Down on an empty prompt (or `/bashes`) lists the commands the agent started in the background; Enter shows one's output live, `k` stops it. The bar under the prompt shows `N shells · ↓ to view` while they run, and the working line counts them during a request (`joshu.ui.shell_viewer`).
- The agent asks multiple-choice questions when a decision is the user's (`ask_user` tool): up to four questions with two to six choices each, single choice (arrow menu, number keys) or several (checkboxes), "Other" to type an answer, Esc to skip. Interactive sessions only; the SDK takes an `ask_user` callback (`joshu.core.ask`).
- `@path` in a request attaches the file to it (`@src/app.py:10-40` for lines, `@dir` for a listing), in interactive mode and `joshu run`; the agent sees it without a tool call. Up to 40,000 characters per file and 100,000 per request; protected files are never attached and secrets are masked (`joshu.core.file_refs`).
- `/memory add <text> [--user]` saves a memory for the agent.
- A test runs every slash command (and its main forms) through the real interactive mode with a fake model, so a broken command fails CI.
- Install skills from where they're published: `joshu skills add <owner/repo> --skill <name> [-g]` (also `/skills add`, `joshu skills remove`, `joshu skills list`). Accepts the `npx skills add ...` command skill pages show; fetches with that tool in a temporary directory (or `git clone` without Node.js) and copies the skills into `.agents/skills/` or `~/.joshu/skills/`. A source with several skills offers a menu. When the agent (or `!` in the prompt) runs `npx skills add`, Joshu installs the skill this way, and new skills are usable at once.
- Read-only shell commands (`ls`, `dir`, `cat`, `type`, `head`, `tail`, `rg`, `grep`, `git status/diff/log/show/blame`, ...) run without asking when they aren't chained or redirected and their paths stay inside the project.
- Skills with `disable-model-invocation: true` run only when you type `/name`; the model doesn't see or load them.
- Desktop notifications when a long request finishes or needs approval, in terminals that support them (iTerm2, WezTerm, Ghostty via OSC 9; kitty via OSC 99); other terminals get the bell. `notifications: auto` (default), `desktop`, `bell` or `off`.
- A busy indicator in the taskbar / tab while a request runs, in Windows Terminal, ConEmu, Ghostty and WezTerm (OSC 9;4).
- `Esc Esc` on an empty prompt, or `/rewind` without a number, opens a menu of earlier requests: pick one to go back to before it (files the agent edited since are restored). `/rewind n` still drops the last n directly.
- The bottom bar shows todo progress (`☐ 2/5 Add tests`) and how many background shells are running.
- Models that stream their reasoning (`reasoning_content` or `reasoning`, e.g. NVIDIA Nemotron, DeepSeek, OpenRouter reasoning models) show it live as dim text while they think; it then folds to one line ("Thought for 3s"), and `Ctrl+O` shows it in full. `on_reasoning` is a new `AgentEvents` callback.
- Replies stream into the terminal as they are written: finished paragraphs, lists and code blocks are printed as Markdown right away, and the line below shows elapsed time and output tokens so far.
- `Ctrl+O` shows tool output that was cut short: at the prompt, the last request's output in full; while the agent works, everything from then on.
- The terminal bell rings when a request that ran 20 seconds or more finishes or waits for approval (`notifications`, `notify_after_seconds`).
- The working line names the task in progress from the todo list.
- Terminal tests (`tests/e2e/test_terminal.py`) run the interactive prompt in a real pseudo-terminal (ConPTY on Windows, pexpect elsewhere) and drive it with key bytes.
- `Ctrl+G` writes the prompt in your editor (`$VISUAL`, `$EDITOR`, Notepad on Windows).

### Changed
- On Windows, multi-line commands (`python -c` with several lines, heredocs) run through Git Bash when it's installed (found next to `git`, in the usual install folders, or at `JOSHU_GIT_BASH_PATH`) instead of being refused: cmd.exe runs only their first line. On the hard benchmark 74 commands in 68 runs were refused this way, each costing a turn. Without Git Bash they are still refused with advice.
- Interactive mode shows its prompt about 6x sooner (9.1 s to 1.55 s here, with the repository's two MCP servers): MCP servers and the modules the first request needs (the OpenAI SDK alone takes about 2 s to import) now load on threads started once the prompt is on screen, so the first request's setup drops from about 2.4 s to 1 s; `rich.markdown` and the MCP loop are no longer imported at startup.
- Faster start: the CLI no longer loads interactive mode and the MCP client up front (`joshu --version` 1.15 s → 0.46 s here), and interactive mode starts MCP servers in the background instead of waiting for them before the prompt.
- No more terminal bell by default: `notifications: auto` only sends desktop notifications where the terminal supports them; `bell` turns the beep back on.
- A plugin installed with `/plugin` during a session starts its MCP servers and offers their tools at once; before, they waited for the next start (`load_new_mcp_servers`).
- Sub-agents that edit see the project as it is: their worktree gets the working tree's uncommitted changes and untracked files first, and only their own work is applied back, on top of those changes (before, uncommitted work was invisible to them and blocked applying).
- `replace` and `multi_edit` apply an edit whose `old_string` differs from the file only in trailing spaces or in indentation shifted the same amount on every line, when exactly one block of lines matches; `new_string` is re-indented to fit and the result notes it. Before, the model had to read the file again and retry (about two failed edits per hard benchmark run).
- The system prompt names the Python command that works on the machine (`python`, `python3` or `py`; the Windows Store stub is skipped) and asks for paths relative to the working directory. Benchmark transcripts showed `python3` failing on Windows and a long absolute path copied wrong.
- A saved conversation is written after every tool round, not only when the request ends, so a crash or a killed process keeps the work so far.
- Diffs: added lines are green and removed lines red on a matching background across the row; a diff longer than 24 lines is cut with "ctrl+o to expand", and Ctrl+O shows it whole and colored. A new file from `write_file` shows as added lines, an overwrite as its diff, and the edited path is a link that opens the file (in terminals with OSC 8 links).
- `max_tokens` defaults to 8192 (was 4096): reasoning models spend output tokens on thinking.
- Removed `@@file`, which ran a script directly from the prompt (use `!python script.py`), and the settings that had no effect: `history_size`, `log_level`, `memory_enabled`, `multiline_input`, `persistent_history`, `semantic_memory_enabled` (ignored if still present).
- `docs/ide-integration.md` says the IDE integration is not available yet: the `joshu ide` commands it describes are not registered.
- `/<skill>` puts the skill's instructions straight into the request instead of asking the model to load them (one model call less, and small models can't skip it). The `skill` tool says where the skill's directory is (for its scripts) and labels supporting files it returns.
- Model API errors are short: HTTP status and the provider's message, without the raw error body (which can include account metadata).
- Vim mode uses prompt_toolkit's vi editing (full motions, operators, undo) instead of a handful of custom keys.

### Fixed
- A reply that stops mid-way (an open code block, an unclosed bracket on its last line, or ending in `:` / `,`) is sent back to the model to continue instead of ending the request. On the hard benchmark a stream ended at "... B.end (1.1" with finish_reason "stop", and booking-overlap ended after 3 calls with nothing fixed.
- Read-only sub-agents were offered every tool, including the shell and edit tools that plan mode denies; calling them three times ended the sub-agent with no answer. They are now offered only the tools they may use.
- The agent no longer spends its last turns saving a memory that summarizes the task it just did (the memory guidance says not to). Benchmark triage counts a check script the agent wrote and ran (`python verify.py`) as its own check, so such runs show as "missed cases" instead of "unchecked".
- `joshu run`, `-p` and the SDK waited for a model's whole answer in one request, cut off after `request_timeout` (120 s) and retried from scratch: a reasoning model that thought for two minutes failed, and retries wasted up to 6 minutes per call (4 hard benchmark tasks ran out of time this way, 1 never got past its second call). Requests are now always streamed, so the timeout applies to each chunk.
- Benchmarks: a provider error broken over two lines in the saved output ("request" / "failed: HTTP 429...") counted as a failure of the model instead of "not counted", and didn't stop the run after several in a row; a rate-limited run scored 0/16. `compare.py` and `triage.py` now read such saved results right too.
- An edit that leaves a Python file unparsable now says where the trouble likely starts (a string whose closing quotes are missing, found from the tokens before the error), and when edits keep leaving the same file broken, the note shows the numbered lines and asks for a `replace` of those lines instead of another full rewrite. In the hard benchmark two runs spent all 50 turns rewriting files that kept losing a closing `"""`.
- Empty replies, and replies that only announce a step ("Let me read the files...") before anything was done, go back to the model instead of ending the request (two benchmark runs ended that way).
- Shell commands ran in the process's directory, not the agent's workspace, so an SDK session with another `cwd` ran its commands in the wrong place.
- Prompt injection: tool results had no marking and the rules didn't say they aren't instructions. The system prompt now says tool results are data, not instructions, and `web_fetch`, `web_search` and MCP tool results are labeled as external content.
- With an OS sandbox, a shell command of an editing sub-agent ran in the main working directory (the sandbox fell back to it) and couldn't write in the worktree; the sandbox now follows the sub-agent's worktree.
- A broken final reply ended the request: small models sometimes write a tool call as text (`... </function> </tool_call>`) or stop with a few garbled words right after a failed tool call (2 of 6 hard benchmark runs). Such replies now go back to the model with a note, up to twice per request (`retry_broken_replies`, on by default).
- On Windows a multi-line shell command (a several-line `python -c`, a heredoc) ran only its first line through cmd.exe and still reported success with no output, so the agent believed its checks printed nothing. Such commands are now refused with advice (write a script file, or join with `&&`), and the environment in the system prompt says so.
- A shell command with an unbalanced quote (`echo don't panic`, a cut-off `python -c "...`) crashed the whole request in the safety check; it is now checked word by word instead. Found by the hard benchmark tier.
- A response cut off by the output limit (`finish_reason: length`) was taken as the final answer, so a reasoning model that spent its tokens thinking ended the request with half a thought and no code. The agent now continues it with a doubled limit (up to 32,768 tokens, at most 3 times per request), falling back to the configured limit if the provider refuses the larger one. Found by the hard benchmark tier.
- A request starting with a file reference (`@app.py what does this do?`) was taken by an older file-injection path, answered "File not found" and never reached the agent; every `@` request now goes to the agent.
- `/theme` and `/rewind` crashed when the terminal couldn't show a menu (stdin a terminal but output not, or a Windows pipe); menus now fall back to text.
- `/config <key> <value with spaces>` did nothing, `/config <unknown key>` printed `None` instead of saying the key is unknown, and `/config vim_mode` didn't apply to the running session.
- `/export dir/file.md` failed when the folder didn't exist.
- After `/compact`, the session list showed "[Summary of the earlier conversation]" as the session's title instead of its first request.
- `/memory status` pointed to a `[semantic]` extra that doesn't exist (it's `joshu[use]`).
- `joshu <command>` only recognized a fixed list of commands; the list now comes from the registered commands (new ones like `skills` were run as a task).
- Replies with emoji like ➡️, ⚠️ or ✔️ were garbled (lines duplicated or run together): terminals draw them two cells wide but they were measured as one, so lines overflowed. The emoji variation selector is now dropped before rendering.
- "Don't ask again" for a command whose second word is a path offered the whole path as the key (``dir "C:\...\x"``); it is now the program (`dir`).
- Number keys in approval prompts and pickers only moved the selection, and Esc did nothing; a number now picks its option, Esc declines or cancels, and options are no longer numbered twice ("1. 1. Yes").
- A `SyntaxWarning` about `"\+"` printed on the first start.
- MCP servers are disconnected at the same time on exit, and their pipes closed, so a slow server no longer leaves "Task was destroyed but it is pending" and closed-pipe errors at exit.
- `Ctrl+O` before the first request did nothing; it now says there is no tool output yet.
- `Ctrl+D` exited even with text in the prompt; it now deletes the next character and exits only on an empty prompt.
- `Ctrl+R` opened a second prompt inside the running one; it now uses the built-in history search.
- `Ctrl+L` ran `cls`/`clear` in a subprocess behind the prompt; it now redraws the screen.
- Removed key bindings that did nothing (`Ctrl+B`, `Ctrl+J`, `Ctrl+K`, `Ctrl+T`, the custom vim keys).

### Removed
- Code no command reaches (see docs/plans/2026-10-05-code-audit.md): the agent registry, delegate tool, tool wrapper and schema converter (`joshu.agents` keeps the YAML/JSON definitions and loader used for sub-agents), the extension framework (`joshu.extensions` keeps the TOML command parser used by custom commands), the A2A `extensions` command, `joshu.commands.mcp` and `ui/interactive/utils.py`; with their tests and the docs pages agent-system.md, extensions.md and command-processing.md.
- The `tqdm` and `requests` dependencies (nothing imported them).
- 25 helper scripts from the project template that nothing ran (builds for other languages, packaging, telemetry collectors, release helpers, ...); `scripts/lint.py` stays. `docs/development-automation.md` describes what is actually used.

## [0.3.0] - 2026-10-04

### Added
- Layered configuration: built-in defaults, `config/config.yaml` in a source checkout, the user config `~/.joshu/config.yaml` (written by `joshu config --set`, only the keys you set) and a project `.joshu/config.yaml`; `joshu config --list` shows where settings come from.
- `joshu trust`: a project's config only applies once the project is trusted, since it can run commands (hooks, diagnostics) and choose providers.
- Persistent permission rules (`permissions: {allow, deny}`, e.g. `run_shell_command(git status*)`); deny rules block in every mode; `/permissions allow|deny <rule>` saves one.
- Model management: `joshu models` lists a provider's models live from its `/models` endpoint (tool support, price and context size where reported; `--search`, `--tools`, `--free`); `joshu use <model>` sets the default; named models (`joshu models add`, the `models` setting) bundle a provider, model id and context window; `joshu providers add|remove` (`joshu.core.model_catalog`).
- `nvidia` provider preset (`NVIDIA_API_KEY`, free key from build.nvidia.com).
- `/models [search]` in interactive mode.
- `joshu models check <model>` and `--check` on `joshu use` / `joshu models add`: one small request with a tool, to catch listed models the account can't use or that don't call tools.
- Requests are retried (`request_retries`, default 3) on connection errors, 408/409/429 and 5xx with backoff; `request_timeout` sets how long to wait.
- `fallback_providers` also takes named models, and fallbacks now also cover unknown models (404), rate limits and server errors, not only unreachable endpoints.
- Instruction files: `AGENTS.md` / `JOSHU.md` from the repository root down to the working directory, plus `~/.joshu/AGENTS.md`, are added to the system prompt (`config/JOSHU.md` still works).

- Tool-call recovery for weaker models: arguments that aren't quite JSON (code fences, trailing commas, Python literals, truncated output) are repaired, near-miss tool names (`ReadFile`, `bash`, `functions.read_file`) resolve to the right tool, and errors list the available tools or the tool's parameters (`joshu.core.tool_repair`).
- Loop detection: the same tool call returning the same result 3 times in a row gets a warning; at 5 the request stops (`stopped: loop`).
- `replace` shows the closest matching lines when `old_string` isn't found.
- Smaller requests: large MCP tool sets are loaded on demand (`load_tools`, `defer_mcp_tools` setting), tool results are compact JSON, built-in tool descriptions are shorter, and a tool that keeps being denied is dropped (the request stops after 6 denials). On a measured bug-fix task with 34 MCP tools: first request 10,661 → 3,782 tokens, whole task 424,762 → 72,498 prompt tokens and 32 → 14 requests.
- GitHub Action: mention `@joshu` in an issue or pull request comment and Joshu makes the changes (a new branch and pull request for issues, a commit to the branch for pull requests) and replies with a summary; owners, members and collaborators only (`action.yml`, docs/github-action.md).
- MCP prompts run as `/server:prompt` slash commands (with arguments) and MCP resources attach with `@server:uri`; `/mcp` lists them.
- Python SDK: `from joshu import Session, run`; sessions keep their conversation between `send()` calls, `stream()` yields events as they happen, `can_use_tool` decides approvals, and `Result` carries the answer, usage and cost (`joshu.sdk`, docs/sdk.md).
- `joshu run --output-format stream-json` prints one JSON event per line as things happen, and `--input-format stream-json` reads several requests from stdin into one conversation.
- Language servers: an installed server (basedpyright / pyright / pylsp, typescript-language-server, gopls, rust-analyzer) starts on demand; after an edit its errors for the file go back to the model, and the `code_nav` tool (loaded on demand) gives definitions, references and hover information. `/doctor` lists the servers; `lsp` setting (`joshu.core.lsp`).
- Editing tools: `multi_edit` (several exact-text edits to one file, applied all or nothing) and `notebook_edit` (replace, insert or delete `.ipynb` cells; outputs of changed code cells are cleared), both loaded on demand. Images in the clipboard can be attached with Alt+V or `/paste` (needs Pillow), and `@"path with spaces"` references work.
- More hook events: `session_start`, `stop` (a blocking stop hook sends the agent back to work, at most 3 times per request), `subagent_stop`, `pre_compress` (can block clearing or summarizing), `notification` (when an approval is needed) and `session_end` now fire; `session_start` and `before_agent` hooks can add context to the conversation with plain stdout or `additional_context`.
- Parallel tool calls: several read-only calls from one turn (reads, searches, web, sub-agents) run at the same time, up to 4, with results kept in order; three sub-agents finished in 9.5s instead of 26s (`parallel_tools`).
- Secret protection: reading or editing `.env`, private keys, `~/.ssh`, cloud credentials and similar files needs explicit approval in every mode, shell commands that name them or print the environment ask first, searches skip them, and API keys, tokens and private keys in tool output are masked before the model or a saved session sees them (`protected_paths`, `allow_paths`, `mask_secrets`; `joshu.core.secrets`).
- Roadmap of the remaining work (`docs/roadmap.md`).
- Leaner requests: tool definitions are trimmed before sending (short parameter descriptions, rarely used optional parameters left out; `joshu.core.tool_schema`), `web_fetch`, `web_search`, `bash_output` and `kill_bash` load on demand, the working rules are shorter and the memory guide is one line until memories exist. A plain "hi": 3.0k → 1.9k tokens (Gemini), 3.8k → 2.4k (NVIDIA lightning).
- Long sessions clear old tool results (all but the 6 most recent) once the context passes `clear_tool_results_at` (60,000 tokens or half the context window), in one batch, before falling back to summarizing (`joshu.core.context_editing`). `read_file` returns large files in whole lines (up to ~40,000 characters) with a note on how to read on, instead of being cut in the middle; `tool_output_limit` defaults to 16,000. The system prompt asks for independent reads and searches in one turn.
- The footer under each reply shows that request's input and output tokens and how many the provider served from its cache, instead of a running session total.
- More slash commands: `/security-review`, `/pr-comments [number]`, `/add-dir <path>` (file tools may also use that directory), `/bashes` (list and stop background commands), `/hooks` (list, add, remove), `/output-style` (`concise`, `explanatory`, `learning` or custom styles in `.joshu/output-styles/`), `/statusline <command>`, `/sandbox [mode]`, `/terminal-setup` (Shift+Enter instructions per terminal) and `/release-notes`. Alt+Enter and `\`+Enter insert a new line.
- Background commands write to a log file, so their output can be read while they run; the agent gets `bash_output` and `kill_bash` tools.
- Joshu's own look: a mascot in the welcome box, a ✦ mark, and color themes (`dark`, `light`, `colorblind`, `plain`; `/theme` with a preview, `theme` setting) (`joshu.ui.theme`). The working indicator says what is happening ("Running pytest -q…", "Reading calc.py…").
- Slash commands from one registry: typing `/` opens a menu with descriptions, `/help` is a grouped table, and aliases work everywhere. New: `/status`, `/doctor` (provider, API key, live model check, tools), `/context` (context window use by system prompt, tools and conversation), `/todos`, `/export [file]` (Markdown transcript), `/review [focus]`, `/mcp`, `/theme`, `/vim`, `/exit`. `@` completes project file paths. Plain `joshu` starts interactive mode.
- Redesigned terminal UI: a compact welcome box (version, working directory, model, first-run tips); the input between two rules with a mode and model line below; Shift+Tab cycles default / accept edits / plan; `?` lists shortcuts; a `Working… (12s · esc to interrupt)` indicator; replies rendered as Markdown; tool calls as `● Read(path)` with results under `⎿` (line counts, colored diffs with line numbers, command output, todo checklists); approvals as a panel plus an arrow-key menu whose "No" option takes a note that is passed to the agent.
- Memory across sessions: the agent saves, updates and deletes notes with a `memory` tool (project scope under `~/.joshu/projects/<project>/memory/`, user scope under `~/.joshu/memory/`); short memories are added to the system prompt in full, longer ones by description. Replaces `save_memory` while `auto_memory` is on (default); `/memory` lists and `/memory forget` deletes (`joshu.core.auto_memory`).
- Skills: `SKILL.md` folders in `.joshu/skills/`, `.agents/skills/` or `~/.joshu/skills/`; only names and descriptions go into the system prompt and the `skill` tool loads instructions and supporting files on demand; `/skills` lists them and `/<skill>` runs one (`joshu.core.skills`).
- Esc interrupts the agent in interactive mode, and text typed while it works is kept as the next prompt (`joshu.ui.key_listener`).
- `/rewind [n]` drops the last n requests and restores the files the agent changed for them; `/compact [focus]` summarizes the conversation on demand; `/init` has the agent write or update AGENTS.md.
- Tab completes slash commands (built-in and custom) instead of shell command names.
- Benchmark tasks and runner (`benchmarks/`): pass rate, turns and tokens per model on small real coding tasks, graded by hidden tests.

### Changed
- The default model is NVIDIA's free Nemotron 3.5 Lightning (`provider: nvidia`, key from build.nvidia.com); OpenRouter remains available with `joshu use <model> -p openrouter`.
- Install from PyPI: `pipx install joshu`; tagged releases publish there automatically.
- `/clear` starts a new conversation (as `/reset` did); clearing the input history is now `/history clear`.

### Fixed
- MCP tool calls always failed after discovery ("'NoneType' object has no attribute 'send'"): servers were connected in one event loop and called from another. All MCP communication now runs on one background loop.
- MCP servers on Windows didn't start when a command or argument contained spaces, and a server writing a lot to stderr could hang (its stderr was piped but never read).
- Esc at the prompt switched to vim NORMAL mode even with `vim_mode` off, so letters such as h, j, k, l and d then ran vim commands; vim keys now follow the `vim_mode` setting. Ctrl+C at the prompt clears the input instead of exiting at once.
- `replace` rewrote a whole file's line endings on Windows (LF files became CRLF); line endings are now kept as they are.
- Commands such as `joshu models`, `joshu config` and `joshu providers` printed the welcome banner.
- `/model <id>` only saved the setting; it now switches the running conversation's model.
- The `save_memory` file ignored `JOSHU_HOME` (always `~/.joshu/JOSHU.md`).

## [0.2.0] - 2026-10-03

### Added
- A2A server runs the tool-using agent for each task: streamed thoughts, tool calls and the final answer, approvals as confirmation requests, cancellation; `approval_mode` per task; `joshu serve`; `a2a` extra (FastAPI, uvicorn).
- Prompt caching: cache breakpoints on the system prompt and latest message for models that need them (Anthropic models on OpenRouter; `cache_control_models` for custom providers); cached input tokens shown in `/cost` (`joshu.core.prompt_cache`).
- Images in requests: `@path/to/image.png` in a request or `joshu run --image PATH` sends PNG/JPEG/GIF/WebP images (up to 5 MB) to vision models (`joshu.core.images`).
- Checks after edits: files written by the agent are checked (Python syntax and ruff error rules, JSON/YAML/TOML parsing, `node --check`, or per-extension commands) and problems are sent back to the model (`joshu.core.diagnostics`).
- OS-level shell sandbox (`shell_sandbox`): bubblewrap, sandbox-exec or Docker; sandboxed commands can run without approval (`joshu.core.sandbox`).
- Cost tracking: provider-reported cost or `model_pricing`; shown in the footer, `cost_usd` in JSON output, `/cost`, saved with sessions (`joshu.core.costs`).
- Undo for the agent's file edits: `/undo` restores files changed by `replace` / `write_file` in the last request (`joshu.core.checkpoints`).
- Saved sessions: conversations are written to `~/.joshu/sessions/` after each request; `--resume <id>`, `--continue`, `/resume`, `joshu sessions`; `save_sessions` setting; `JOSHU_HOME` overrides the data directory.
- Custom slash commands from `.joshu/commands/` and `~/.joshu/commands/` (`.md` or `.toml`); `/commands` lists them.
- User-defined sub-agents in `.joshu/agents/` for the `task` tool, with their own prompt, tools, model and turn limit; `/agents` lists them.
- Hooks configured under `hooks:` in `config.yaml`; `after_agent` is fired; command hooks with per-hook timeouts.
- Provider layer (`joshu.core.providers`): any OpenAI-compatible provider via `provider` / `model` config; built-in presets (OpenRouter, OpenAI, Anthropic, Gemini, Groq, Mistral, DeepSeek, xAI, Together, Fireworks, Cerebras, Ollama, LM Studio, vLLM), custom providers under `providers:`, `fallback_providers`, `--provider` flag and `joshu providers` command.
- Agent loop (`joshu.core.agent`): the model calls tools, sees results, and continues until done; Ctrl+C keeps history valid.
- Native tool calling and streaming for OpenAI-compatible endpoints, with fallback across unreachable endpoints (`joshu.core.llm_client`).
- Permission gate with `default`, `accept_edits`, `plan` and `bypass` modes; diff previews and session "always allow" (`joshu.core.permissions`).
- Context compaction, environment-aware system prompt, read-only `task` sub-agent tool.
- `joshu run` flags: `--permission-mode`, `-p/--print`, `--output-format json`; interactive `/permissions` and `/reset`.
- Agent settings: `agent_max_turns`, `permission_mode`, `context_window`, `compact_threshold`, `tool_output_limit`.
- Docs: `docs/agent.md`; plan: `docs/plans/2026-10-02-agent-core.md`.

### Changed
- One session store: `/session` (list, new, switch, delete) now manages the saved agent sessions, the same ones as `joshu sessions`, `--resume` and `/resume`; `joshu history` lists recent requests from them.
- Per-user data (input history, memory, semantic-memory database) moved from `./cache` and `./.joshu_chromadb` in the working directory to `~/.joshu` (`$JOSHU_HOME`).
- CI runs on every pull request and push to `main`, on Linux with Python 3.10-3.14 and on Windows.
- `joshu run`, `joshu "<prompt>"`, `joshu explain` and interactive agent/plan modes use the agent; ask mode uses the configured provider.
- Removed the open-loop interactive agent mode, which ran generated commands without confirmation.
- MCP tools require approval.
- Config values are type-checked; invalid values fall back to defaults.

### Removed
- Legacy model stack: single-command translator (`joshu run --legacy`, `translate.py`), model pool and providers package (`joshu.models`, including the echo test model), translation cache, auto-fix, whole-file `joshu code` generator, `tool_calling_helper`.
- `provider: auto` environment detection (`VLLM_SERVER_URL`, `LOCAL_MODEL_URL`) and per-model-family OpenRouter keys (`GLM_API_KEY`, `QWEN_API_KEY`, ...); use `provider` + the provider's key variable.
- Commands `repeat-last`, `explain-last`, `code`, `cache-stats`, `cache-clear`; basic interactive fallback (prompt_toolkit is required).
- Config keys with no remaining readers: `safety_mode`, `auto_execute`, `cache_*`, `auto_fix_*`, `tool_calling_*`, `web_search_tool_enabled` (ignored if present).
- Local-LLM extras from `[use]` (`transformers`, `torch` pin, `huggingface_hub`, `llama-cpp-python`, `sentencepiece`).
- Unused modules `joshu.core.hooks` (duplicated `joshu.hooks`), `joshu.core.credentials`, `joshu.tools.filesystem`.

### Fixed
- Web search never worked: the code used the `ddgs` package but the dependency was the old `duckduckgo-search`; the dependency is now `ddgs`.
- MCP tools were only loaded in interactive mode; `joshu run`, `joshu "<prompt>"` and A2A tasks now get them too.
- Startup no longer warns about the optional web-search and semantic-memory packages on every run.
- A2A server: CORS allowed every origin with credentials and no authentication was required; it now needs a bearer token and allows no cross-origin access by default.
- A2A server: `GET /tasks/metadata` returned 404 because `/tasks/{task_id}` was declared first.
- `/reset` kept the same session id, so the next request overwrote the previous conversation's saved session.
- The Docker sandbox was used with Docker engines in Windows-container mode, which can't run its Linux image.
- Starting Joshu in a directory without `./cache` printed "Could not save sessions".
- Hook scripts written in Python could not run on Windows; a hook blocking with exit code 2 gave the model no reason.
- `max_tokens: 0.8` in `config/config.yaml`; tests no longer write the real config file.
- Shell blocklist matched substrings (blocked `ruff format`, `git log --format`, `rm -rf /tmp/x`).
- LLM errors are reported instead of being swallowed.
- CLI crashed on Windows when output was piped (cp1252 console encoding).
- `SKIP_LLM_TESTS` guarded the removed providers only, and `SKIP_LLM_TESTS=0` still skipped; it now guards every real model request and honors `0`/`false`.

## Contributing

When adding new features, please update this changelog following the format above.
