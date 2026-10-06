# Joshu

A coding agent for your terminal. Describe a task in plain language and Joshu
reads and searches your code, edits files and runs commands until it's done,
asking before anything risky. It works with any OpenAI-compatible model
provider, including free and local models.

```bash
joshu "add a --verbose flag to the CLI and update the tests"
```

## Features

- **Agent loop**: the model uses tools (read, search, edit, shell, web,
  sub-agents, MCP servers), sees the results and keeps going until the task is
  done; independent reads and sub-agents run in parallel
- **Permissions and safety**: edits show a diff and commands ask first;
  `accept_edits`, read-only `plan` and `bypass` modes; `.env` files, keys and
  credentials need explicit approval and secrets are masked in tool output
- **Any provider**: NVIDIA, OpenRouter, OpenAI, Anthropic, Gemini, Groq,
  Mistral, DeepSeek, Ollama, LM Studio, vLLM or any OpenAI-compatible endpoint;
  live model lists, named models, retries and fallback models
- **Code intelligence**: language-server errors after every edit, plus
  go-to-definition, references and hover
- **Interactive mode**: themes, a `/` command menu with ~50 commands, Esc to
  interrupt, `/rewind`, `/compact`, `/init`, skills and memory across sessions
- **Lean on tokens**: on-demand tool loading, compact results and context
  clearing keep a plain "hi" around 2k tokens
- **Extensible**: custom commands, sub-agents, skills, hooks, MCP tools,
  prompts and resources, output styles, and plugins that bundle them
- **Programmable**: a Python SDK, JSON / streaming JSON output, an HTTP server
  (`joshu serve`) and a GitHub Action that works on `@joshu` comments

## Install

Python 3.10 or newer.

```bash
pipx install joshu        # or: pip install joshu
```

From source: `git clone https://github.com/Faycalraghibi/Joshu.git && cd Joshu && pip install -e .`
(add `[use]` for semantic memory, `[a2a]` for the HTTP server).

## Set up a model

The default is NVIDIA's free Nemotron 3.5 Lightning. Get a free key at
[build.nvidia.com](https://build.nvidia.com) and put it in `.env` or your
environment:

```bash
NVIDIA_API_KEY=nvapi-...
```

Check the setup with `joshu` then `/doctor`. To use something else:

```bash
joshu providers                                   # providers and key status
joshu models -p openrouter --tools --free         # browse a provider's models
joshu use qwen3-coder -p ollama                   # local models, no key needed
```

## Use

```bash
joshu                                         # interactive (/help, ? for shortcuts)
joshu "why does test_login fail?"             # one task
joshu run --permission-mode plan "how is auth implemented?"   # read-only
joshu run -p --output-format json "list the TODOs"            # for scripts
joshu run --continue "now add tests for it"   # continue the last conversation
```

From Python:

```python
from joshu import run
print(run("summarize README.md").text)
```

## Documentation

- [Quick start](docs/quick-start.md)
- [Agent: permissions, tools, memory, skills, sandbox](docs/agent.md)
- [Interactive mode and slash commands](docs/interactive-mode.md)
- [Models & providers](docs/models-and-providers.md)
- [Python SDK and streaming](docs/sdk.md)
- [GitHub Action](docs/github-action.md)
- [Hooks](docs/hooks.md) · [MCP servers](docs/mcp-servers.md) · [Plugins](docs/plugins.md) · [Configuration](docs/configuration.md)
- [Roadmap](docs/roadmap.md) · [All documentation](docs/README.md)

## License

MIT
