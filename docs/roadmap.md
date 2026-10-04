# Roadmap

What remains to make Joshu a complete coding agent, in the order it is being
built. Each item ships as its own pull request with tests and, where it applies,
a live check against a real model.

## Phase 1: Safety and speed

### A. Secret protection (done)
- Protected paths (`.env*`, private keys, `~/.ssh`, cloud credentials, ...):
  reading or editing one needs explicit approval in every mode; search results
  skip them; shell commands that name one or print the environment ask first.
  `protected_paths` / `allow_paths` adjust the list.
- API keys, tokens and private keys in tool output are masked before the model
  or a saved session sees them (`mask_secrets`).

### B. Parallel read-only tools (done)
- Several read-only calls in one turn (read, search, glob, list, web, `task`)
  run concurrently (up to 4); results keep their order. Edits and shell
  commands stay sequential. Several `task` calls run sub-agents in parallel.

### C. A default model chosen from data
- `benchmarks/run.py --repeat 3` over the candidate models; pass rate, tokens
  and time per model; a recommended default and a "Choosing a model" guide.

## Phase 2: Extensibility

### D. More hook events (done)
- `user_prompt_submit`, `session_start`, `pre_compact`, `stop`,
  `subagent_stop`, `notification`. Hook output can block, add context to the
  conversation, or (for `stop`) send the agent back to work with a reason.

### E. Editing tools (done)
- `multi_edit`: several replacements in one file, applied atomically.
- `notebook_edit`: edit `.ipynb` cells by id.
- Paste clipboard images into the input (Ctrl+V), with Pillow as an optional
  dependency.

### F. MCP extras (done: prompts and resources)
- MCP prompts as slash commands (`/server:prompt`), MCP resources as
  `@server:uri` attachments, OAuth (PKCE) for remote HTTP servers.

## Phase 3: Code intelligence

### G. Language-server client (done)
- Detect installed servers (pyright / basedpyright, typescript-language-server,
  gopls, rust-analyzer; configurable with `lsp:`). After edits, real type and
  compile errors go back to the model. A `code_nav` tool (loaded on demand) for
  definition, references and hover. Status in `/doctor`.

## Phase 4: Programmatic use and distribution

### H. SDK and streaming (done)
- A stable Python API (`from joshu import Agent`) and
  `joshu run --input-format stream-json --output-format stream-json`.

### I. GitHub Action (done)
- `@joshu ...` in a pull request or issue comment runs Joshu in a workflow and
  pushes a branch or replies.

### J. Release
- Tag a release, publish to PyPI through a trusted-publishing workflow,
  `pipx install joshu`, and an update check.

## Later
- VS Code extension (building on `ide/` and `scripts/build_vscode_companion.py`).
- Plugins: `joshu plugin install <git-url>` for bundles of commands, skills,
  hooks and MCP servers.
- A managed settings layer for teams.
- A real-terminal QA checklist for the interactive UI.

## Open decisions
- Which models the benchmark (C) compares.
- Pillow as an optional dependency for clipboard images (E).
- Whether OAuth MCP servers (F) are needed now.
- The next release version (J).
