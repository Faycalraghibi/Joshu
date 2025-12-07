"""Abstract base interface for all model providers."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Generator, List, Optional

logger = logging.getLogger(__name__)

# Import utilities for use in default implementations
try:
    from joshu.tools.response_utils import chunk_response as _chunk_response_func
    from joshu.tools.response_utils import (
        format_messages_as_prompt as _format_messages_func,
    )

    format_messages_as_prompt: Optional[
        Callable[[List[Dict[str, str]]], str]
    ] = _format_messages_func
    chunk_response: Optional[
        Callable[[str, int], Generator[str, None, None]]
    ] = _chunk_response_func
except ImportError:
    # Fallback if tools not available
    format_messages_as_prompt = None
    chunk_response = None


class LLM(ABC):
    """
    Legacy LLM interface for backward compatibility.

    This is a simple interface that's used throughout the codebase.
    ModelProvider is the new provider interface, but LLM remains
    for backward compatibility with existing code.
    """

    @abstractmethod
    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate a response from the model."""
        raise NotImplementedError


class ModelProvider(ABC):
    """
    Abstract base class for all model providers.

    All providers must implement this interface to be used in the ModelPool.
    """

    def __init__(self, name: str, config: Dict[str, Any]) -> None:
        """
        Initialize the model provider.

        Args:
            name: Unique name identifier for this provider
            config: Configuration dictionary for this provider
        """
        self.name = name
        self.config = config
        self._initialized = False
        self._available = False

    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize the provider (e.g., load model, establish connection).

        Returns:
            True if initialization was successful, False otherwise
        """
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the provider is currently available.

        Returns:
            True if the provider can handle requests, False otherwise
        """
        raise NotImplementedError

    @abstractmethod
    def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.1,
        max_tokens: int = 512,
        **kwargs: Any,
    ) -> str:
        """
        Generate a response from the model.

        Args:
            prompt: Input prompt for the model
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Returns:
            Generated text response

        Raises:
            RuntimeError: If provider is not available or initialization failed
        """
        raise NotImplementedError

    def generate_stream(
        self,
        prompt: str,
        *,
        temperature: float = 0.1,
        max_tokens: int = 512,
        **kwargs: Any,
    ) -> Generator[str, None, None]:
        """
        Generate a streaming response from the model.

        Default implementation generates full response and yields in chunks.
        Providers can override for native streaming support.

        Args:
            prompt: Input prompt for the model
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Yields:
            Chunks of generated text

        Raises:
            RuntimeError: If provider is not available or initialization failed
        """
        full_response = self.generate(
            prompt, temperature=temperature, max_tokens=max_tokens, **kwargs
        )
        # Use utility function for chunking if available, otherwise fallback
        if chunk_response:
            yield from chunk_response(full_response)
        else:
            # Fallback implementation
            chunk_size = 50
            for i in range(0, len(full_response), chunk_size):
                yield full_response[i : i + chunk_size]

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float = 0.1,
        max_tokens: int = 512,
        **kwargs: Any,
    ) -> Optional[str]:
        """
        Generate a chat completion from a list of messages.

        Default implementation converts messages to a prompt.
        Providers can override for native chat API support.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Returns:
            Generated text response, or None if generation failed
        """
        # Use utility function for formatting if available, otherwise fallback
        if format_messages_as_prompt:
            prompt = format_messages_as_prompt(messages)
        else:
            # Fallback implementation
            prompt_parts = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "system":
                    prompt_parts.append(f"System: {content}\n")
                elif role == "user":
                    prompt_parts.append(f"User: {content}\n")
                elif role == "assistant":
                    prompt_parts.append(f"Assistant: {content}\n")
            prompt = "".join(prompt_parts) + "\nAssistant:"

        try:
            return self.generate(prompt, temperature=temperature, max_tokens=max_tokens, **kwargs)
        except Exception as e:
            logger.debug(f"Chat completion failed for {self.name}: {e}")
            return None

    def cleanup(self) -> None:
        """
        Cleanup resources (e.g., unload model, close connections).

        Can be overridden by providers that need custom cleanup logic.
        """
        self._initialized = False
        self._available = False

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r}, available={self.is_available()})"
