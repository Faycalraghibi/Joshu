"""Model provider implementations."""

from .echo import EchoProvider
from .llama_cpp import LlamaCppProvider, LlamaCppWrapper, maybe_load_llama_from_env
from .openrouter import OpenRouterProvider
from .local import LocalModelProvider

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
]

