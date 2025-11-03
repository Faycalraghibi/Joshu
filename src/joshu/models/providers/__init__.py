"""Model provider implementations."""

from .echo import EchoProvider
from .llama_cpp import LlamaCppProvider, LlamaCppWrapper, maybe_load_llama_from_env
from .openrouter import OpenRouterProvider

# Alias for backward compatibility
LocalModelProvider = LlamaCppProvider

__all__ = [
    "EchoProvider",
    "LlamaCppProvider",
    "LlamaCppWrapper",
    "maybe_load_llama_from_env",
    "LocalModelProvider",  # Backward compatibility
    "OpenRouterProvider",
]

