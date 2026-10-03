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
joshu config --set provider=anthropic
joshu config --set model=claude-sonnet-5-5
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
| `ollama` | `http://localhost:11434/v1` | not needed | - |
| `lmstudio` | `http://localhost:1234/v1` | not needed | - |
| `vllm` | `http://localhost:8000/v1` | not needed | - |

Anthropic and Gemini are reached through their OpenAI compatibility endpoints.
For `openrouter`, keys stored per model family (`GLM_API_KEY`, `QWEN_API_KEY`,
...) are also accepted when `OPENROUTER_API_KEY` is not set.

Put keys in the environment or in `.env` at the project root.

## Custom providers

Add any OpenAI-compatible endpoint under `providers:`:

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
`headers`, `default_model`, `requires_key`, `description`.

## Fallback

```yaml
provider: ollama
model: qwen3-coder
fallback_providers: [openrouter]
```

When the main provider can't be reached (connection error or timeout), the
fallback providers are tried in order with their default models. Request errors
such as a bad key, an unknown model or a rate limit are reported, not skipped.

## Auto-detection (`provider: auto`)

The default `provider: auto` keeps the older environment-based setup: it uses
`VLLM_SERVER_URL` + `VLLM_MODEL`, `LOCAL_MODEL_URL` + `LOCAL_MODEL_IDENTIFIER`,
and OpenRouter keys, trying the endpoint that serves the requested model first.
Setting an explicit provider is clearer and is recommended.

## Model Pool (legacy translator)

The single-command translator (`joshu run --legacy`, ask mode) still uses the
model pool below. The agent uses the provider layer above.


The model pool manages multiple providers and handles fallbacks automatically.

### How It Works

1. **Auto-Discovery**: Pool automatically discovers and initializes available providers
2. **Provider Ranking**: Providers are ranked by preference and availability
3. **Fallback**: If preferred provider fails, pool tries next available provider
4. **Singleton**: Model pool is shared across the application

### Using the Model Pool

```python
from joshu.models.pool import get_model_pool

# Get singleton pool instance
pool = get_model_pool()

# Generate with default provider
response = pool.generate("List files in current directory")

# Generate with specific provider
response = pool.generate("List files", provider_name="deepseek")

# Chat completion
messages = [{"role": "user", "content": "Hello"}]
response = pool.chat_completion(messages)

# Check available providers
providers = pool.get_available_providers()
for provider in providers:
    print(f"{provider.name}: {provider.is_available()}")
```

### Provider Priority

Providers are tried in this order:

1. Specified provider (if `provider_name` given)
2. Cloud providers (if API key available)
3. Local model API (if configured)
4. vLLM server (if configured)
5. Echo provider (fallback)

## Model Switching

### Using setup_config.ps1 (Windows)

Interactive menu to switch models:

```powershell
.\setup_config.ps1
```

This updates both `.env` and `~/.joshu/config.yaml`.

### Manual Configuration

Edit `~/.joshu/config.yaml`:

```yaml
model: deepseek/deepseek-chat-v3.1:free
```

Or use environment variable:

```bash
export OPENROUTER_MODEL="qwen/qwen3-coder:free"
```

### Programmatic Switching

```python
from joshu.models.config import ModelConfig

# Check if cloud model should be used
if ModelConfig.should_use_cloud():
    model = ModelConfig.get_openrouter_model()
else:
    # Use local model
    pass

# Get model-specific API key
api_key = ModelConfig.get_openrouter_api_key("deepseek/model-name")
```

## Provider Types

### OpenRouter Provider

Routes requests through OpenRouter API:

```python
from joshu.models.providers.openrouter import OpenRouterProvider

provider = OpenRouterProvider(
    model="deepseek/deepseek-chat-v3.1:free",
    api_key="sk-or-v1-..."
)

response = provider.generate("Hello")
```

### Local Model Provider

Connects to local model API:

```python
from joshu.models.providers.local import LocalModelProvider

provider = LocalModelProvider(
    base_url="http://localhost:8000/v1",
    model_identifier="my-model"
)

if provider.is_available():
    response = provider.generate("Hello")
```

### vLLM Provider

High-performance local inference:

```python
from joshu.models.providers.vllm import VLLMProvider

provider = VLLMProvider(
    api_base="http://localhost:8000",
    model="meta-llama/Llama-3-8B"
)

if provider.is_available():
    response = provider.generate("Hello")
```

## Troubleshooting

### "No providers available"

1. Check API key is set:
   ```bash
   echo $OPENROUTER_API_KEY
   ```

2. Verify model configuration:
   ```bash
   cat ~/.joshu/config.yaml
   ```

3. Test provider manually:
   ```python
   from joshu.models.pool import get_model_pool
   pool = get_model_pool()
   print(pool.get_available_providers())
   ```

### API Connection Errors

- **OpenRouter**: Verify API key is valid
- **Local Model**: Check server is running at configured URL
- **vLLM**: Ensure vLLM server is accessible

### Model Not Found

Some models may not be available on OpenRouter's free tier. Check [OpenRouter models](https://openrouter.ai/models) for availability.

## Best Practices

1. **Use Free Models for Development**: Start with free models like GLM or DeepSeek
2. **Configure Fallbacks**: Set up both cloud and local providers for reliability
3. **Monitor Usage**: Some providers have rate limits
4. **Cache Responses**: Use translation cache to reduce API calls

## Related Documentation

- [Configuration](configuration.md) - Full configuration options
- [vLLM Server Integration](VLLM_SERVER_INTEGRATION.md) - Local model setup
- [Testing Guide](testing-guide.md) - Testing with providers
