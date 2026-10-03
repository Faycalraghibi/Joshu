# Agent Core Plan

Date: 2026-10-02

## Goal

Turn Joshu from a "natural language → one shell command" translator into a
tool-using coding agent: the model calls tools in a loop, sees their results,
and keeps going until the task is done, behind a permission gate.

## Audit summary (what separates Joshu from modern coding agents)

What modern coding agents share:

1. **Agent loop** — assemble context → call model → model requests tool →
   permission gate → execute → feed result back → repeat until done.
2. **Permission system** between loop and tools; modes (default / accept-edits /
   plan (read-only) / bypass); per-session "always allow".
3. **Precise edit tools** (exact string replace) with a diff shown before apply.
4. **Context management** — token tracking, automatic compaction.
5. **Rich system prompt** — environment (cwd, OS, git), project instructions
   file.
6. **Hooks** around tool use; **sub-agents** for delegated work; **MCP** tools
   reaching the model.
7. **Streaming** output, interruptible turns, headless mode (`-p`, JSON output).
8. Extras: LSP diagnostics, checkpoints / undo, OS-level sandbox,
   client/server split, prompt caching.

Where Joshu falls (verified in code):

| # | Finding | Location |
|---|---------|----------|
| 1 | Tool loop `chat_with_tools` never called | `core/tool_calling_helper.py` |
| 2 | Provider `chat_completion` takes no `tools`, returns text only | `models/openrouter.py`, `models/providers/*` |
| 3 | Tool modules never imported → registry empty at runtime | `tools/*_tools.py` |
| 4 | `requires_approval` never enforced; tool docs promise a diff that is never shown | `core/tool_executor.py` |
| 5 | "Agent mode" is open-loop (JSON list of commands), auto-runs any non-blocklisted command, model never sees output, `cd` doesn't persist | `ui/interactive/modes.py` |
| 6 | `Agent.run` placeholder; A2A executor has no LLM | `core/agent.py`, `a2a/executor.py` |
| 7 | Hooks never dispatched; delegate tool only validates, never runs a sub-agent | `hooks/`, `agents/delegate_tool.py` |
| 8 | MCP tools registered with `requires_approval=False` | `mcp/discovery.py` |
| 9 | `edit_file` regenerates whole file with `max_tokens=2048` → truncation/data loss, no diff | `core/code_editor.py` |
| 10 | Echo test model can serve production requests (`available_providers[0]`) | `models/pool.py`, `core/code_editor.py` |
| 11 | Semantic translation cache keyed on prompt only → wrong cached command for similar prompt | `core/translation_cache.py` |
| 12 | Shell blocklist substring match blocks `ruff format`, `git log --format` | `tools/shell_tool.py` |
| 13 | LLM errors swallowed at debug level → "No translation found" with no reason | `models/openrouter.py` |
| 14 | No streaming in UI, no token accounting, no compaction, no headless JSON mode | `ui/` |
| 15 | Duplicate modules (shell ×2, web_fetch ×2, filesystem ×2, code_editor ×2, hooks ×2, openrouter ×2) | `tools/`, `core/`, `models/` |

## Phase 1 — Agent core (implemented in this pass)

1. **`core/llm_client.py`** — OpenAI-compatible chat client with native tool
   calling and streaming (text + tool-call deltas), usage capture, errors raised
   as `LLMError` with an actionable message. Endpoint resolution:
   `VLLM_SERVER_URL` → `JOSHU_LOCAL_MODEL_API_URL` / local API → OpenRouter.
2. **`core/permissions.py`** — `PermissionMode` (default, accept_edits, plan,
   bypass), `PermissionManager.check()`, session "always allow", approval
   preview (unified diff for `replace` / `write_file`, command for shell).
   Unsafe shell commands (existing `assess_command_safety`) always need explicit
   approval, even in bypass; with no approver they are denied.
3. **`core/system_prompt.py`** — identity + working rules, environment block
   (cwd, OS, shell, date, git branch), project `JOSHU.md` + user memory, plan-mode
   addendum.
4. **`core/compaction.py`** — token estimate; when over
   `compact_threshold × context_window`, summarize older turns with the model
   and keep recent turns intact (never split an assistant tool call from its
   results).
5. **`core/agent.py`** — real `Agent`: loop until no tool calls or
   `agent_max_turns`; hooks `before_tool` / `after_tool` dispatched; tool output
   truncated; Ctrl+C mid-turn leaves history valid; `task` tool runs a read-only
   sub-agent.
6. **Tool loading** — `load_builtin_tools()` imports all tool modules; MCP tools
   require approval.
7. **UI** — `ui/agent_ui.py`: streamed text, tool-call lines, approval prompt
   (yes / always / no) with diff preview.
   - Interactive: `agent` mode and `plan` mode run the new `Agent` (plan =
     read-only permissions); `ask` mode unchanged. Falls back to the legacy
     translator with a clear message when no LLM endpoint is configured.
   - `joshu run "..."` uses the agent; `--permission-mode`, `--print/-p`
     (headless), `--output-format text|json`, `--legacy` for the old translator;
     `-y` maps to bypass.
8. **Config** — `agent_max_turns`, `permission_mode`, `context_window`,
   `compact_threshold`, `tool_output_limit`.
9. **Safety fixes** — shell blocklist matches command words, not substrings;
   `edit_file` scales `max_tokens` to file size, lowers temperature, refuses
   truncated output, never uses the echo provider; translation cache keyed by
   OS + cwd and semantic matching disabled for command reuse.
10. **Tests** — scripted fake `ChatClient` driving the loop end to end:
    tool call → permission → execution → result fed back; plan-mode denial;
    approval "always"; compaction boundary; interrupt; blocklist; cache key.

## Phase 2 — done

- [x] Undo: edits by `replace` / `write_file` are snapshotted per request;
      `/undo` restores them (`core/checkpoints.py`). Shell edits are not tracked.
- [x] Sessions saved after every request; `--resume`, `--continue`, `/resume`,
      `joshu sessions` (`core/sessions.py`).
- [x] Sub-agents defined in `.joshu/agents/` (Markdown or `joshu.agents`
      YAML/JSON) available to the `task` tool, with their own prompt, tools,
      model and turn limit (`core/subagents.py`).
- [x] Custom slash commands from `.joshu/commands/*.md|toml`; shell steps go
      through the permission gate (`core/custom_commands.py`).
- [x] Hooks configured under `hooks:` in `config.yaml`; command hooks, `.py`
      scripts on Windows, block reasons from stderr, `after_agent` fired.
- [x] Regex translator removed; unused `core.hooks`, `core.credentials`,
      `tools.filesystem` removed.

## Phase 3 — in progress

- [x] Checks after edits: syntax / ruff / parse / `node --check` per file type,
      plus per-extension commands; problems go back to the model
      (`core/diagnostics.py`). A full LSP client remains possible later.
- [x] OS-level shell sandbox: bubblewrap, sandbox-exec or Docker; sandboxed
      commands can skip approval (`core/sandbox.py`).
- [x] Cost tracking: provider-reported cost (OpenRouter) or `model_pricing`;
      footer, JSON, `/cost`, sessions (`core/costs.py`).
- [ ] Prompt caching, image input.
- [ ] A2A executor driven by `Agent` instead of pre-scheduled tool calls.
