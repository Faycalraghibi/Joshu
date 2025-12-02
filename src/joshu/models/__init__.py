"""Model providers and pool architecture for Joshu Assistant."""

# Export new pool architecture
from .base import LLM, ModelProvider

# Maintain backward compatibility - export old API
from .inference import StreamingLLM, establish_model_connection, get_model
from .openrouter import (
    chat_completion,
    establish_openrouter_connection,
    get_openrouter_client,
)
from .pool import ModelPool, get_model_pool
from .providers import EchoProvider, LocalModelProvider

# Try to export vLLM server provider (optional)
try:
    from .providers import VLLM_SERVER_AVAILABLE, VLLMServerProvider
except ImportError:
    VLLMServerProvider = None  # type: ignore
    VLLM_SERVER_AVAILABLE = False

# Backward compatibility aliases
EchoModel = EchoProvider

__all__ = [
    # New pool architecture
    "ModelPool",
    "get_model_pool",
    "ModelProvider",
    "LLM",
    # Backward compatibility
    "get_model",
    "establish_model_connection",
    "StreamingLLM",
    "EchoModel",  # Alias for EchoProvider
    "EchoProvider",
    "LocalModelProvider",  # Local model API provider
    "get_openrouter_client",
    "chat_completion",
    "establish_openrouter_connection",
    # vLLM server provider (optional)
    "VLLMServerProvider",
    "VLLM_SERVER_AVAILABLE",
]
