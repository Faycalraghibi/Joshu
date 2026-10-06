# Code audit: what the agent rebuild left behind (2026-10-05)

Joshu was rebuilt around the tool-calling agent in 0.2.0. This audit lists
the code that no longer serves a working path, so it can be removed, finished
or kept on purpose.

## Method

- **Reachability:** a static import graph over `src/joshu` (including imports
  inside functions and module names imported dynamically, such as the
  built-in tool modules), walked from every entry point: `joshu.ui.cli`
  (CLI and interactive mode), `joshu.sdk`, `joshu.a2a.server` and
  `joshu.__main__`.
- **Use from outside a package:** a module that is reachable only because its
  own package's `__init__` imports it is not used.
- **Settings:** each default setting checked for a reader outside
  `core/config.py`.
- **Dependencies, scripts, tests and docs:** checked for a user in the code,
  CI or pre-commit, and for which tests exercise only unused code.

143 modules: 133 reachable, 10 unreachable (2,182 lines).

## Findings

| Area | State | Code | Tests | Recommendation |
|---|---|---|---|---|
| `joshu.ide` + `commands/ide.py` + VS Code companion (`packages/`) | **Unreachable.** No CLI command starts the server; the agent does not send diff proposals; the companion and `docs/ide-integration.md` refer to `joshu ide` commands that don't exist | 1,002 + 253 + 366 lines | 957 lines (67 tests) | **Decide:** connect it (a `joshu ide` command that keeps the server running, and edits sent as diff proposals) or remove it. Removing loses a working diff-proposal server and the extension skeleton |
| `joshu.agents`: `registry`, `delegate_tool`, `tool_wrapper`, `schema_converter` | Reachable only through the package `__init__`; the `task` tool replaced them. Only `loader` and `definitions` are used (YAML/JSON sub-agent definitions) | 1,112 lines | 1,344 lines (83 tests) | **Remove**, keep `loader`, `definitions`, `exceptions` |
| `joshu.extensions`: `loader`, `manifest`, `registry`, `settings` + `commands/extensions.py` | Only `commands/extensions.py` (unreachable) uses them. `extensions/commands.py` (TOML command parsing) **is** used by custom commands | 1,581 lines | 191 lines | **Remove**, keep `extensions/commands.py` (or move it to `core/custom_commands.py`) |
| `commands/mcp.py` | Unreachable; the CLI uses `ui/cli_handlers/mcp_handler.py` | 346 lines | 197 lines | **Remove** |
| A2A `extensions` command | Reachable through `/executeCommand`, but only reads an `extensions` config key that nothing writes | small | -- | **Remove** with the extension framework (keep `init` and `restore`) |
| `ui/interactive/utils.py` | Unreachable since `@@` and the old vim keys were removed | 82 lines | -- | **Remove** |
| `core.context_provider` + `core.storage` (semantic memory, attention) | Used by ask mode, `/memory status|search|clear` and `!` history, not by the agent | ~1,000 lines | ~90 tests | **Keep for now**; consider giving ask mode the agent's own context and dropping the vector store, which is the heaviest optional dependency |
| `core.chat_session`, `core.tool_scheduler` | Used by the A2A executor for task bookkeeping | -- | 17 tests | **Keep** |
| Dependencies `tqdm`, `requests` | In `[project] dependencies`, imported nowhere in `src/`, tests or benchmarks | -- | -- | **Remove** from the dependencies (smaller install) |
| `scripts/` | CI uses `lint.py` and `check_build_status.py`; the other 24 scripts (build, package, sandbox image, VS Code build, release helpers, telemetry collectors, ...) come from the project template and nothing runs them | 6,740 lines | -- | **Remove** the unused ones, or move the few worth keeping (secret scanner, settings docs generator) into the documented workflow |
| Docs: `agent-system.md`, `extensions.md`, `command-processing.md`, `ide-integration.md` | Describe the unused systems above (1,376 lines); `chat-and-scheduling.md` and `context-system.md` describe internals still in use | -- | -- | **Remove or rewrite** together with the code; fix `docs/README.md` links |

Already fixed in this round (PR #49): the `@file` / `@@file` injection path
and six settings nothing read.

## Not problems

- `tools/web_fetch.py` and `tools/implementations/web_fetch_tool.py` look
  duplicated but are a helper library and the tool that wraps it. The
  "already registered" warning only appears when the tool registry is
  reloaded.
- `tools/shell.py` (`run_command`, used by `!` commands) and
  `tools/shell_tool.py` (the agent's tool) overlap in purpose; merging them is
  a cleanup, not a fix.

## Impact of the recommended removals

About 4,300 lines of source, 1,800 lines of tests (~210 tests that exercise
only unused code), 6,700 lines of template scripts and 1,400 lines of docs,
plus two runtime dependencies. The IDE decision adds 1,600 lines of source and
950 of tests either way.

## Order

1. Remove the clearly unused code (agents registry and friends, extension
   framework, `commands/mcp.py`, `ui/interactive/utils.py`, `tqdm`,
   `requests`) with its tests and docs. One PR; behavior does not change.
2. Remove the unused template scripts and update
   `docs/development-automation.md`.
3. Decide on the IDE integration: connect or remove.
4. Revisit semantic memory for ask mode.
