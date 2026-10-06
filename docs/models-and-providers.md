# Models & Providers

## Overview

Joshu works with any model provider that offers an OpenAI-compatible chat API,
which covers nearly every hosted provider and every common local server. A
provider is a base URL, where its API key lives, and optional headers. Common
providers are built in, and any other can be added in `config.yaml`; no code
changes are needed.

The agent needs a model that supports **tool calling**.

## Choosing a provider

```bash
joshu providers                       # list providers, their key status and default model
joshu models --provider nvidia        # list the models a provider serves
joshu use claude-sonnet-5-5 --provider anthropic   # make it the default
```

Or for one run, without changing the config:

```bash
joshu run --provider ollama --model qwen3-coder "explain src/main.py"
joshu interactive --provider groq --model <model-id>
```

With `--provider` and no `--model`, the provider's default model is used (when
it has one).

## Choosing a model

The default is NVIDIA's **Nemotron 3.5 Lightning** (`nvidia/nemotron-3.5-lightning-30b-a3b`):
free with a key from build.nvidia.com, supports tool calling, and is fast.

Joshu's benchmark has an **easy tier** (8 small tasks: fix a bug, add a flag,
rename across files, ...) and a **hard tier** (6 tasks: a feature across
several modules, interacting bugs, a data structure from a spec, an API
migration across many call sites, a parser with many edge cases, a rounding
bug found from its symptom). Hidden tests grade every run. Results on NVIDIA's
free models (October 2026, one run per task, `--permission-mode bypass`):

| Model | Easy | Hard | Notes |
|---|---|---|---|
| Nemotron 3.5 Lightning 30B (default) | 8/8 | 3/5 | ~110k tokens per hard task; 1 hard task not measured (endpoint timeouts) |
| Nemotron 3 Super 120B | 7/8 | 3/6 | ~410k tokens per hard task |
| Nemotron 3 Ultra 550B | 8/8 | 1/1 | 5 hard tasks not measured: NVIDIA returned HTTP 500 |

The easy tier is solved reliably by all three. On the hard tier, all models
failed the half-up rounding task (floating-point halves such as 1.005) and the
INI parser's edge cases; the larger models were not better on what could be
measured, and Super used about four times the tokens. One run per task is a
small sample, so treat differences of one task as noise. For harder work a
frontier model from another provider is the safer choice. Compare models on
your own tasks with
`python benchmarks/run.py --provider <p> --model <m> --tier hard --repeat 3`.

## Built-in providers

| Name | Base URL | API key variable | Default model |
|---|---|---|---|
| `openrouter` | `https://openrouter.ai/api/v1` | `OPENROUTER_API_KEY` | `poolside/laguna-s-2.1:free` |
| `openai` | `https://api.openai.com/v1` | `OPENAI_API_KEY` | - |
| `anthropic` | `https://api.anthropic.com/v1/` | `ANTHROPIC_API_KEY` | `claude-sonnet-5-5` |
| `gemini` | `https://generativelanguage.googleapis.com/v1beta/openai/` | `GEMINI_API_KEY` | - |
| `groq` | `https://api.groq.com/openai/v1` | `GROQ_API_KEY` | - |
| `mistral` | `https://api.mistral.ai/v1` | `MISTRAL_API_KEY` | `mistral-large-latest` |
| `deepseek` | `https://api.deepseek.com/v1` | `DEEPSEEK_API_KEY` | `deepseek-chat` |
| `xai` | `https://api.x.ai/v1` | `XAI_API_KEY` | - |
| `together` | `https://api.together.xyz/v1` | `TOGETHER_API_KEY` | - |
| `fireworks` | `https://api.fireworks.ai/inference/v1` | `FIREWORKS_API_KEY` | - |
| `cerebras` | `https://api.cerebras.ai/v1` | `CEREBRAS_API_KEY` | - |
| `nvidia` | `https://integrate.api.nvidia.com/v1` | `NVIDIA_API_KEY` | `nvidia/nemotron-3.5-lightning-30b-a3b` |
| `ollama` | `http://localhost:11434/v1` | not needed | - |
| `lmstudio` | `http://localhost:1234/v1` | not needed | - |
| `vllm` | `http://localhost:8000/v1` | not needed | - |

Anthropic and Gemini are reached through their OpenAI compatibility endpoints.

Put keys in the environment or in `.env` at the project root.

NVIDIA's hosted open models (Nemotron, Llama, Qwen, DeepSeek, ...) take a free
`nvapi-...` key from [build.nvidia.com](https://build.nvidia.com).

## Finding models

Model lists come live from the provider's `/models` endpoint, so new models
show up without a Joshu update:

```bash
joshu models                                   # the configured provider
joshu models -p openrouter --tools --free      # free models with tool calling
joshu models -p nvidia --search nemotron
```

OpenRouter reports tool support, price and context size; for other providers
those columns show `?`. `joshu use` and `joshu models add` check the id against
the list and warn about typos or models without tool calling.

A listed model isn't always usable: some providers list models an account
can't call, or that are overloaded. `joshu models check <model>` sends one small
request with a tool and reports whether the model answers and calls it;
`--check` on `joshu use` and `joshu models add` does the same before saving.

In interactive mode, `/models [search]` lists models and `/model <id>` switches
the running conversation to another model (`joshu use` changes the default).

## Named models

Give a model a short name, its provider and settings:

```bash
joshu models add fast nvidia/nemotron-3.5-lightning-30b-a3b -p nvidia --context-window 128000
joshu use fast             # or --model fast, or /model fast
joshu models remove fast
```

This writes the `models` setting in the user config:

```yaml
models:
  fast:
    provider: nvidia
    model: nvidia/nemotron-3.5-lightning-30b-a3b
    context_window: 128000
```

A named model's `context_window` overrides the global `context_window` for
compaction.

## Custom providers

```bash
joshu providers add homelab --base-url http://10.0.0.5:8080/v1 --api-key-env HOMELAB_KEY
joshu providers remove homelab
```

Or add any OpenAI-compatible endpoint under `providers:`:

```yaml
provider: mycloud
model: my-model-id
providers:
  mycloud:
    base_url: https://api.mycloud.example/v1
    api_key_env: MYCLOUD_API_KEY      # or api_key: ... (avoid committing keys)
    headers:                          # optional extra HTTP headers
      X-Team: research
    default_model: my-model-id        # optional
  homelab:                            # no key settings: treated as a local server
    base_url: http://10.0.0.5:8080/v1
```

The same block overrides a built-in provider's settings, e.g. Ollama on another
machine:

```yaml
providers:
  ollama:
    base_url: http://gpu-box:11434/v1
```

Settings: `base_url` (required for custom providers), `api_key_env`, `api_key`,
`headers`, `default_model`, `requires_key`, `description`, `request_options`
(extra request fields), `cache_control_models` (see Prompt caching).

## Prompt caching

The agent's requests grow by appending to the conversation, so providers that
cache repeated prompt prefixes make long conversations cheaper and faster:

| Provider | Caching |
|---|---|
| OpenAI, DeepSeek | Automatic |
| OpenRouter, Anthropic models (`anthropic/...`) | Joshu adds cache breakpoints (system prompt and latest message) |
| Anthropic direct (`anthropic` preset) | Not available through Anthropic's OpenAI-compatible endpoint |

Other models on OpenRouter use whatever caching their provider does
automatically. A custom provider can ask for breakpoints with
`cache_control_models: ["*"]` (or a list of model id prefixes). Input tokens
served from the cache appear in `/cost`.

## Fallback

```yaml
provider: ollama
model: qwen3-coder
fallback_providers: [openrouter]
```

Entries are provider names (which use their default model) or named models.
When the main model can't serve a request, the fallbacks are tried in order:
connection errors, timeouts, unknown models (404), rate limits (429) and server
errors (5xx). A bad key or an invalid request is reported, not skipped. The
first model that answers is used for the rest of the session.

Free tiers are often busy, so a fallback model is worth setting:

```yaml
provider: nvidia
model: nvidia/nemotron-3-ultra-550b-a55b
models:
  lightning:
    provider: nvidia
    model: nvidia/nemotron-3.5-lightning-30b-a3b
fallback_providers: [lightning, openrouter]
```

## Retries and timeouts

Each request is retried on connection errors, timeouts, 408/409/429 and 5xx,
with exponential backoff that honors `Retry-After`, before a fallback is tried:

```yaml
request_retries: 3     # default
request_timeout: 120   # seconds to wait for a response
```

## Request size

Each request carries the system prompt and the definition of every tool the
model may call, so a task of 15 steps sends them 15 times. Joshu keeps that
fixed part small:

- **MCP tools are loaded on demand.** When MCP tool definitions would cost
  more than ~1,500 tokens per request, only their names go into the system
  prompt; the model loads the ones it needs with `load_tools`, and they stay
  available for the rest of the session. `defer_mcp_tools`: `auto` (default),
  `always` or `never`.
- **Tool results are compact JSON**, and tool definitions are trimmed before
  sending: short descriptions, and rarely used optional parameters left out
  (the tools still accept them).
- **Rarely used built-ins load on demand too**: `web_fetch`, `web_search`,
  `bash_output` and `kill_bash` (the last two load by themselves when a
  background command starts).
- **The system prompt is short**, and the memory guide is one line while no
  memories exist. A plain "hi" costs about 2k tokens (1.9k with Gemini, 2.4k
  with NVIDIA lightning, whose tokenizer counts more).
- **Repeated denials stop early**: when a tool keeps being denied in one request
  the model is told to stop calling it, and after 6 denials the request ends.
- **Old tool results are cleared in long sessions**: past `clear_tool_results_at`
  tokens (default 60,000, at most half the context window) the outputs of all
  but the 6 most recent tool calls become one-line notes (the model can run the
  tool again), in one batch so the prompt cache is rebuilt only once.
  Summarizing (`compact_threshold`) stays the last resort. In measured
  5-question sessions this kept peak context about 30% lower.
- **Large files are read in whole lines**: `read_file` returns up to ~40,000
  characters of complete lines and says how to read the rest.

What dominates a session's total is how many steps the model takes: every step
re-sends the conversation. Small models take many small steps (the same
session took 9 requests in one run and 21 in the next), so a stronger model is
often the biggest saving; in the benchmark, OmniRoute's `auto/coding:free`
used about a quarter of the tokens of a 30B model for the same tasks.

Measured on a small bug-fix task with two MCP servers (34 tools) configured:

| | First request | Requests for the task | Prompt tokens for the task |
|---|---|---|---|
| Before | 10,661 | 32 | 424,762 |
| After | 3,782 | 14 | 72,498 |

The footer under each reply shows that request's tokens (`↑ 3.8k in (2.2k
cached) · ↓ 43 out`); `/context` shows what the context is made of, and
`/cost` the session totals. Providers with prompt caching (NVIDIA, OpenAI,
DeepSeek, Anthropic, ...) serve the repeated prefix from cache, which is
cheaper or faster.

To trim further, keep only the MCP tools you need with `include_tools` /
`exclude_tools` per server (see [MCP servers](mcp-servers.md)), or turn MCP off
with `joshu config --set mcp_enabled=false`.
