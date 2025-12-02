# vLLM Inference Server Integration

## Overview

vLLM is a high-throughput inference server that provides 10-20× higher throughput than vanilla HuggingFace models through PagedAttention and continuous batching. This integration allows Joshu to use vLLM as a high-performance backend.

## Features

- **High Throughput**: 10-20× faster than standard inference
- **OpenAI-Compatible API**: Works with existing OpenAI client code
- **Two Modes**: Direct programmatic API or HTTP server endpoint
- **Automatic Discovery**: Auto-detected by ModelPool when configured
- **Priority Routing**: Highest priority in provider fallback chain

## Installation

### Option 1: Direct API (Programmatic)

```bash
pip install vllm  # Automatically pulls CUDA kernels
```

### Option 2: Server Mode (Recommended for Production)

```bash
# Install vLLM
pip install vllm

# Start vLLM server
python -m vllm.entrypoints.openai.api_server \
    --model meta-llama/Meta-Llama-3-8B \
    --port 8000
```

## Configuration

### Environment Variables

```bash
# Option 1: Direct API (uses vLLM library directly)
export VLLM_MODEL="meta-llama/Meta-Llama-3-8B"

# Option 2: Server Mode (connects to running server)
export VLLM_SERVER_URL="http://localhost:8000"
export VLLM_MODEL="meta-llama/Meta-Llama-3-8B"  # Model name for server
```

### Configuration Priority

1. **Server URL** (`VLLM_SERVER_URL`) - If set, uses HTTP endpoint
2. **Direct API** (`VLLM_MODEL` only) - If vLLM installed, uses direct API
3. **Auto-discovery** - ModelPool automatically discovers if configured

## Usage

### Automatic (Recommended)

The vLLM provider is automatically discovered and used when configured:

```python
from joshu.models.pool import get_model_pool

pool = get_model_pool()
# vLLM will be used automatically if configured (highest priority)
response = pool.generate("Hello, world!")
```

### Manual

```python
from joshu.models.providers import VLLMServerProvider

# Server mode
provider = VLLMServerProvider(
    model_name="meta-llama/Meta-Llama-3-8B",
    server_url="http://localhost:8000"
)

# Direct API mode
provider = VLLMServerProvider(
    model_name="meta-llama/Meta-Llama-3-8B"
)

provider.initialize()
response = provider.generate("Hello, world!")
```

## Provider Priority

The ModelPool uses the following priority order:

1. **vLLM Server** (Priority 0) - Highest throughput
2. OpenRouter (Priority 1) - Cloud models
3. Local Model API (Priority 2) - Other local servers
4. Llama.cpp (Priority 3) - Deprecated
5. Echo (Priority 4) - Fallback

## Architecture

### Direct API Mode

```python
from vllm import LLM, SamplingParams

llm = LLM("meta-llama/Meta-Llama-3-8B")
out = llm.generate("Hello", SamplingParams(max_tokens=20))
```

### Server Mode

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000", api_key="not-needed")
response = client.chat.completions.create(
    model="meta-llama/Meta-Llama-3-8B",
    messages=[{"role": "user", "content": "Hello"}]
)
```

## Benefits

- **10-20× Higher Throughput**: PagedAttention + continuous batching
- **Memory Efficient**: Better memory management than vanilla HF
- **Production Ready**: Stable, battle-tested inference server
- **OpenAI Compatible**: Drop-in replacement for OpenAI API
- **GPU Optimized**: Automatic CUDA kernel compilation

## Requirements

- **GPU**: CUDA-compatible GPU recommended (CPU mode possible but slower)
- **Python**: 3.8+
- **Memory**: Varies by model size (7B models need ~16GB VRAM)

## Troubleshooting

### vLLM Not Available

If vLLM is not installed, the provider gracefully degrades:
- Provider won't be auto-discovered
- Other providers will be used instead
- No errors, just falls back to next available provider

### Server Connection Issues

- Check server is running: `curl http://localhost:8000/health`
- Verify `VLLM_SERVER_URL` is correct
- Check firewall/network settings

### Direct API Issues

- Ensure vLLM is installed: `pip install vllm`
- Check GPU availability: `nvidia-smi`
- Verify model name is correct HuggingFace identifier

## Example: Starting vLLM Server

```bash
# Basic server
python -m vllm.entrypoints.openai.api_server \
    --model meta-llama/Meta-Llama-3-8B

# With custom port
python -m vllm.entrypoints.openai.api_server \
    --model meta-llama/Meta-Llama-3-8B \
    --port 8000

# With GPU layers
python -m vllm.entrypoints.openai.api_server \
    --model meta-llama/Meta-Llama-3-8B \
    --gpu-memory-utilization 0.9
```

## Integration with Joshu

The vLLM provider integrates seamlessly:

1. **Auto-discovery**: Automatically found if `VLLM_MODEL` or `VLLM_SERVER_URL` is set
2. **High Priority**: Used first in provider fallback chain
3. **Transparent**: Works with existing `get_model()` and `ModelPool` APIs
4. **Backward Compatible**: Doesn't break existing code

## Performance Comparison

- **Vanilla HuggingFace**: ~10 tokens/sec
- **vLLM**: ~100-200 tokens/sec (10-20× improvement)
- **Throughput**: Handles multiple concurrent requests efficiently

## Notes

- vLLM is an optional dependency - code works without it
- Server mode is recommended for production deployments
- Direct API mode is useful for development/testing
- Both modes support streaming responses
