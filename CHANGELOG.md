# Changelog

All notable changes to the Joshu project will be documented in this file.

## [Unreleased]

### Added
- Provider layer (`joshu.core.providers`): any OpenAI-compatible provider via `provider` / `model` config; built-in presets (OpenRouter, OpenAI, Anthropic, Gemini, Groq, Mistral, DeepSeek, xAI, Together, Fireworks, Cerebras, Ollama, LM Studio, vLLM), custom providers under `providers:`, `fallback_providers`, `--provider` flag and `joshu providers` command.
- Agent loop (`joshu.core.agent`): the model calls tools, sees results, and continues until done; Ctrl+C keeps history valid.
- Native tool calling and streaming for OpenAI-compatible endpoints, with fallback across unreachable endpoints (`joshu.core.llm_client`).
- Permission gate with `default`, `accept_edits`, `plan` and `bypass` modes; diff previews and session "always allow" (`joshu.core.permissions`).
- Context compaction, environment-aware system prompt, read-only `task` sub-agent tool.
- `joshu run` flags: `--permission-mode`, `-p/--print`, `--output-format json`; interactive `/permissions` and `/reset`.
- Agent settings: `agent_max_turns`, `permission_mode`, `context_window`, `compact_threshold`, `tool_output_limit`.
- Docs: `docs/agent.md`; plan: `docs/plans/2026-10-02-agent-core.md`.

### Changed
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

### Fixed
- `max_tokens: 0.8` in `config/config.yaml`; tests no longer write the real config file.
- Shell blocklist matched substrings (blocked `ruff format`, `git log --format`, `rm -rf /tmp/x`).
- LLM errors are reported instead of being swallowed.
- CLI crashed on Windows when output was piped (cp1252 console encoding).
- `SKIP_LLM_TESTS` guarded the removed providers only, and `SKIP_LLM_TESTS=0` still skipped; it now guards every real model request and honors `0`/`false`.


### Dependencies

### Technical Details

## Contributing

When adding new features, please update this changelog following the format above.
