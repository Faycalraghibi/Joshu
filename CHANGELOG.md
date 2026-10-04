# Changelog

All notable changes to the Joshu project will be documented in this file.

## [Unreleased]

### Added
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
- `/<skill>` puts the skill's instructions straight into the request instead of asking the model to load them (one model call less, and small models can't skip it). The `skill` tool says where the skill's directory is (for its scripts) and labels supporting files it returns.
- Model API errors are short: HTTP status and the provider's message, without the raw error body (which can include account metadata).
- Vim mode uses prompt_toolkit's vi editing (full motions, operators, undo) instead of a handful of custom keys.

### Fixed
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
