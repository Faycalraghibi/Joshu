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

When the main provider can't be reached (connection error or timeout), the
fallback providers are tried in order with their default models. Request errors
such as a bad key, an unknown model or a rate limit are reported, not skipped.
