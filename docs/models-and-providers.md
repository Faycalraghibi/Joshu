# Models & Providers

## Overview

Joshu supports multiple LLM providers through a flexible model pool system. You can use cloud-based APIs (like OpenRouter), local models, or vLLM servers. The system automatically manages provider initialization, fallbacks, and switching.

## Supported Providers

### Cloud Providers (via OpenRouter)

- **DeepSeek** - `deepseek/deepseek-chat-v3.1:free`
- **Tongyi** - `alibaba/tongyi-deepresearch-30b-a3b:free`
- **Qwen** - `qwen/qwen3-coder:free`
- **Kimi Dev** - `moonshotai/kimi-dev-72b:free`
- **Agenticat** - `agentica-org/deepcoder-14b-preview:free`
- **Gemma** - `google/gemma-3-27b-it:free`
- **GLM** - `z-ai/glm-4.5-air:free` (default)
- **OpenAI** - `openai/gpt-4o`, `openai/gpt-4o-mini`

### Local Providers

- **Local Model API** - HTTP API for local models
- **vLLM Server** - High-performance local inference
- **Llama.cpp** - CPU-optimized local models (deprecated)
- **Echo Provider** - Test provider (fallback)

## Configuration

### Basic Setup

1. **Set OpenRouter API Key** (required for cloud models):

```bash
export OPENROUTER_API_KEY="sk-or-v1-..."
# Or add to .env file
echo "OPENROUTER_API_KEY=sk-or-v1-..." >> .env
```

2. **Choose a Model** (optional, defaults to GLM):

```bash
export OPENROUTER_MODEL="deepseek/deepseek-chat-v3.1:free"
# Or configure in ~/.joshu/config.yaml
echo "model: deepseek/deepseek-chat-v3.1:free" > ~/.joshu/config.yaml
```

### Provider-Specific API Keys

Some providers support model-specific API keys:

```bash
# DeepSeek
export DEEPSEEK_API_KEY="sk-..."

# Tongyi
export TONGYI_API_KEY="sk-..."

# Qwen
export QWEN_API_KEY="sk-..."
```

When using a model like `deepseek/model-name`, Joshu will first try `DEEPSEEK_API_KEY`, then fall back to `OPENROUTER_API_KEY`.

### Local Model Configuration

For local models via HTTP API:

```bash
export LOCAL_MODEL_URL="http://localhost:8000/v1"
export LOCAL_MODEL_IDENTIFIER="my-local-model"
```

For vLLM server:

```bash
export VLLM_API_BASE="http://localhost:8000"
export VLLM_MODEL="meta-llama/Llama-3-8B"
```

## Model Pool

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
