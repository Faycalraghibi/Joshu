# Changelog

All notable changes to the Joshu project will be documented in this file.

## [Unreleased]

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
- `/clear` starts a new conversation (as `/reset` did); clearing the input history is now `/history clear`.

### Fixed
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
