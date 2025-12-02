"""Model provider implementations."""

from .echo import EchoProvider
from .llama_cpp import LlamaCppProvider, LlamaCppWrapper, maybe_load_llama_from_env
from .local import LocalModelProvider
from .openrouter import OpenRouterProvider

# Try to import vLLM server provider (optional dependency)
try:
    from .vllm_server import VLLMServerProvider

    VLLM_SERVER_AVAILABLE = True
except ImportError:
    VLLMServerProvider = None  # type: ignore
    VLLM_SERVER_AVAILABLE = False

# Backward compatibility: Old LocalModelProvider was LlamaCppProvider
# Now LocalModelProvider is the local model API provider
# Keep the old name for deprecated llama.cpp direct loading
OldLocalModelProvider = LlamaCppProvider

__all__ = [
    "EchoProvider",
    "LlamaCppProvider",
    "LlamaCppWrapper",
    "maybe_load_llama_from_env",
    "LocalModelProvider",  # Local model API provider
    "OldLocalModelProvider",  # Deprecated: LlamaCppProvider
    "OpenRouterProvider",
    # vLLM server provider (optional)
    "VLLMServerProvider",
    "VLLM_SERVER_AVAILABLE",
]
