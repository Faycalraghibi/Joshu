from __future__ import annotations

import logging
from typing import Dict, Generator

from .base import LLM
from .pool import ModelPool, get_model_pool

# Set up logging with reduced verbosity - only show warnings and errors
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

# Model cache for backward compatibility
_model_cache: Dict[str, LLM] = {}

# Global variable to track if connection has been established
_connection_established = False


def establish_model_connection(model_name: str) -> bool:
    """Establish connection to the model service."""
    global _connection_established

    if _connection_established:
        return True

    try:
        # Use ModelPool to establish connection
        pool = get_model_pool()
        # Try to get a provider for this model
        provider = pool.get_provider(model_name=model_name)
        if provider and provider.is_available():
            _connection_established = True
            logger.debug(f"Model connection established via pool for {model_name}")
            return True

        # If no specific provider, check if any providers are available
        available = pool.get_available_providers()
        if available:
            _connection_established = True
            logger.debug("Model connection established via pool")
            return True

    except Exception as e:
        logger.debug(f"Failed to establish model connection: {e}")
        return False

    return False


class StreamingLLM(LLM):
    """Wrapper for LLMs that supports streaming responses."""

    def __init__(self, llm: LLM) -> None:
        self._llm = llm

    def generate(self, prompt: str, **kwargs) -> str:
        """Generate a complete response."""
        return self._llm.generate(prompt, **kwargs)

    def generate_stream(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        """Generate a streaming response."""
        # Check if the underlying LLM supports streaming (pool adapter)
        if hasattr(self._llm, "pool") and hasattr(self._llm.pool, "generate_stream"):
            # Use pool's streaming if available
            yield from self._llm.pool.generate_stream(
                prompt, model_name=kwargs.get("model_name"), **kwargs
            )
        else:
            # For models that don't natively support streaming,
            # we generate the full response and yield it in chunks
            full_response = self._llm.generate(prompt, **kwargs)
            # Yield in chunks for streaming effect
            chunk_size = 50
            for i in range(0, len(full_response), chunk_size):
                yield full_response[i : i + chunk_size]


def get_model(model_name: str) -> LLM:
    """Get a model instance with caching and lazy loading (backward compatible)."""
    global _model_cache, _connection_established

    # Return cached model if available
    if model_name in _model_cache:
        return _model_cache[model_name]

    # Try to establish connection if not already done
    if not _connection_established:
        logger.debug("Attempting to establish model connection...")
        establish_model_connection(model_name)

    # Use ModelPool to get model
    pool = get_model_pool()

    # Create a wrapper that adapts the pool to the LLM interface
    class ModelWrapper(LLM):
        """Wrapper that uses ModelPool but maintains LLM interface."""

        def __init__(self, pool_instance: ModelPool, model: str) -> None:
            self.pool = pool_instance
            self.model_name = model

        def generate(self, prompt: str, **kwargs) -> str:
            """Generate response using pool."""
            return self.pool.generate(prompt, model_name=self.model_name, **kwargs)

    model = ModelWrapper(pool, model_name)

    # Wrap with streaming support
    streaming_model = StreamingLLM(model)
    _model_cache[model_name] = streaming_model

    return streaming_model


def unload_model(model_name: str) -> bool:
    """Unload a model from cache to free memory."""
    global _model_cache
    if model_name in _model_cache:
        del _model_cache[model_name]
        return True
    return False


def list_loaded_models() -> list[str]:
    """List all currently loaded models."""
    global _model_cache
    return list(_model_cache.keys())


def clear_model_cache() -> None:
    """Clear all models from cache."""
    global _model_cache
    _model_cache.clear()
