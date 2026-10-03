# Changelog

All notable changes to the Joshu project will be documented in this file.

## [Unreleased]

### Added
- Provider layer (`joshu.core.providers`): any OpenAI-compatible provider via `provider` / `model` config; built-in presets (OpenRouter, OpenAI, Anthropic, Gemini, Groq, Mistral, DeepSeek, xAI, Together, Fireworks, Cerebras, Ollama, LM Studio, vLLM), custom providers under `providers:`, `fallback_providers`, `--provider` flag and `joshu providers` command.
- Agent loop (`joshu.core.agent`): the model calls tools, sees results, and continues until done; Ctrl+C keeps history valid.
- Native tool calling and streaming for OpenAI-compatible endpoints, with fallback across unreachable endpoints (`joshu.core.llm_client`).
- Permission gate with `default`, `accept_edits`, `plan` and `bypass` modes; diff previews and session "always allow" (`joshu.core.permissions`).
- Context compaction, environment-aware system prompt, read-only `task` sub-agent tool.
- `joshu run` flags: `--permission-mode`, `-p/--print`, `--output-format json`, `--legacy`; interactive `/permissions` and `/reset`.
- Agent settings: `agent_max_turns`, `permission_mode`, `context_window`, `compact_threshold`, `tool_output_limit`.
- Docs: `docs/agent.md`; plan: `docs/plans/2026-10-02-agent-core.md`.

### Changed
- `joshu run`, `joshu "<prompt>"` and interactive agent/plan modes use the agent; the single-command translator remains as `--legacy` and as fallback when no endpoint is configured.
- Removed the open-loop interactive agent mode, which ran generated commands without confirmation.
- MCP tools require approval.
- Config values are type-checked; invalid values fall back to defaults.

### Fixed
- `max_tokens: 0.8` in `config/config.yaml`; tests no longer write the real config file.
- Shell blocklist matched substrings (blocked `ruff format`, `git log --format`, `rm -rf /tmp/x`).
- `edit_file` truncated large files (fixed 2048-token limit) and could use the echo test model.
- Translation cache could return another directory's or OS's command, or one for a merely similar request.
- LLM errors are reported instead of being swallowed.
- CLI crashed on Windows when output was piped (cp1252 console encoding).


### Dependencies

### Technical Details

## Contributing

When adding new features, please update this changelog following the format above.
