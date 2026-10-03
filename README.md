# Joshu

A coding agent for your terminal. Describe a task in plain language and Joshu
reads and searches your code, edits files and runs commands until it's done,
asking before anything risky. It works with any OpenAI-compatible model
provider, including local models.

```bash
joshu "add a --verbose flag to the CLI and update the tests"
```

## Features

- **Agent loop**: the model uses tools (read, search, edit, shell, web,
  sub-agents, MCP servers), sees the results and keeps going until the task is
  done
- **Permissions**: edits show a diff and commands ask first; `accept_edits`,
  read-only `plan` and `bypass` modes; commands flagged as unsafe always ask
- **Any provider**: OpenRouter, OpenAI, Anthropic, Gemini, Groq, Mistral,
  DeepSeek, Ollama, LM Studio, vLLM or any custom OpenAI-compatible endpoint
- **Checks after edits**: syntax errors and undefined names are sent back to the
  model to fix
- **Undo and sessions**: `/undo` reverts the agent's edits; conversations are
  saved and resumable with `--continue` / `--resume`
- **Customizable**: custom slash commands, user-defined sub-agents, hooks
- **Shell sandbox**: optional bubblewrap, macOS sandbox or Docker isolation
- **Images, cost tracking, prompt caching, headless JSON output**, and an
  authenticated HTTP server (`joshu serve`) for other tools and agents

## Install

Python 3.10 or newer.

**Windows (PowerShell):**
```powershell
git clone https://github.com/Faycalraghibi/Joshu.git joshu
cd joshu
.\clean_install.ps1
```

**Linux/macOS:**
```bash
git clone https://github.com/Faycalraghibi/Joshu.git joshu
cd joshu
chmod +x clean_install.sh
./clean_install.sh
```

Or with pip: `pip install -e .` (add `[use]` for semantic memory, `[a2a]` for
the HTTP server).

## Set up a model

The default is a free model on OpenRouter. Put your key in `.env`:

```bash
OPENROUTER_API_KEY=your_key
```

Or choose another provider:

```bash
joshu providers                              # list providers and key status
joshu config --set provider=ollama           # local models, no key needed
joshu config --set model=qwen3-coder
```

## Use

```bash
joshu interactive                            # conversation (/help for commands)
joshu "why does test_login fail?"            # one task
joshu run --permission-mode plan "how is auth implemented?"   # read-only
joshu run -p --output-format json "list the TODOs"            # for scripts
joshu run --continue "now add tests for it"  # continue the last conversation
```

## Documentation

- [Quick start](docs/quick-start.md)
- [Agent: permissions, tools, sessions, sandbox](docs/agent.md)
- [Models & providers](docs/models-and-providers.md)
- [Configuration](docs/configuration.md)
- [CLI reference](docs/cli-reference.md)
- [All documentation](docs/README.md)

## License

MIT
