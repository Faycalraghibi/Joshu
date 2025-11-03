"""Local model provider - re-exported from llama_cpp for convenience."""

from .llama_cpp import LlamaCppProvider

# Re-export for backward compatibility
LocalModelProvider = LlamaCppProvider

__all__ = ["LocalModelProvider"]
