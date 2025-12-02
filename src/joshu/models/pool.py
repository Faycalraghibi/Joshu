"""Model pool with automatic fallback and provider management."""

from __future__ import annotations

import logging
from threading import Lock
from typing import Any, Dict, Generator, List, Optional

from .base import LLM, ModelProvider
from .config import ModelConfig
from .providers import (
    EchoProvider,
    LlamaCppProvider,
    LocalModelProvider,
    OpenRouterProvider,
)

# Try to import vLLM server provider (optional)
try:
    from .providers import VLLM_SERVER_AVAILABLE, VLLMServerProvider
except ImportError:
    VLLMServerProvider = None  # type: ignore
    VLLM_SERVER_AVAILABLE = False


logger = logging.getLogger(__name__)

# Global pool instance
_pool_instance: Optional[ModelPool] = None
_pool_lock = Lock()


class ModelPoolAdapter(LLM):
    """Adapter to make ModelPool compatible with LLM interface."""

    def __init__(self, pool: ModelPool) -> None:
        """Initialize adapter with a model pool."""
        self.pool = pool

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate response using the pool."""
        return self.pool.generate(prompt, **kwargs)


class ModelPool:
    """
    Central orchestrator for model providers with automatic fallback.

    The pool manages multiple providers and automatically falls back to
    available providers when others fail or are unavailable.
    """

    def __init__(self, providers: Optional[List[ModelProvider]] = None) -> None:
        """
        Initialize model pool.

        Args:
            providers: Optional list of pre-configured providers.
                      If None, providers will be auto-discovered.
        """
        self.providers: List[ModelProvider] = providers or []
        self._provider_cache: Dict[str, ModelProvider] = {}
        self._lock = Lock()
        self._initialized = False

        if providers is None:
            self._auto_discover_providers()

    def _auto_discover_providers(self) -> None:
        """Auto-discover and add available providers."""
        # Try OpenRouter first if cloud should be used
        if ModelConfig.should_use_cloud():
            try:
                openrouter = OpenRouterProvider()
                if openrouter.initialize():
                    self.add_provider(openrouter)
                    logger.debug("Auto-discovered OpenRouter provider")
            except Exception as e:
                logger.debug(f"Failed to auto-discover OpenRouter: {e}")

        # Try vLLM server if configured (high priority - high throughput)
        if VLLM_SERVER_AVAILABLE and VLLMServerProvider:
            try:
                vllm_model = ModelConfig.get_vllm_model()
                vllm_url = ModelConfig.get_vllm_server_url()
                if vllm_model or vllm_url:
                    vllm_provider = VLLMServerProvider(model_name=vllm_model, server_url=vllm_url)
                    if vllm_provider.initialize():
                        self.add_provider(vllm_provider)
                        logger.debug("Auto-discovered vLLM server provider")
            except Exception as e:
                logger.debug(f"Failed to auto-discover vLLM server provider: {e}")

        # Try local model API if configured
        try:
            local_url = ModelConfig.get_local_model_api_url()
            local_model = ModelConfig.get_local_model_api_identifier()
            if local_url and local_model:
                local_provider = LocalModelProvider()
                if local_provider.initialize():
                    self.add_provider(local_provider)
                    logger.debug("Auto-discovered local model provider")
        except Exception as e:
            logger.debug(f"Failed to auto-discover local model provider: {e}")

        # Try to discover direct llama.cpp models (DEPRECATED: Use local model API instead)
        # Kept for backward compatibility
        import warnings

        for model_name in ModelConfig.SUPPORTED_LOCAL_MODELS.keys():
            try:
                llama_provider = LlamaCppProvider(model_name)
                if llama_provider.initialize():
                    warnings.warn(
                        f"Llama.cpp provider '{model_name}' is deprecated. "
                        "Please use local model API instead. Set LOCAL_MODEL_URL and LOCAL_MODEL_IDENTIFIER environment variables.",
                        DeprecationWarning,
                        stacklevel=2,
                    )
                    self.add_provider(llama_provider)
                    logger.debug(
                        f"Auto-discovered llama.cpp model provider: {model_name} (deprecated)"
                    )
            except Exception as e:
                logger.debug(f"Failed to auto-discover llama.cpp model {model_name}: {e}")

        # Try generic llama model from env (DEPRECATED)
        try:
            model_path = ModelConfig.get_local_model_path("default")
            if model_path:
                # Use the model name from path or a default name
                llama_provider = LlamaCppProvider("default")
                if llama_provider.initialize():
                    warnings.warn(
                        "Llama.cpp provider is deprecated. "
                        "Please use local model API instead. Set LOCAL_MODEL_URL and LOCAL_MODEL_IDENTIFIER environment variables.",
                        DeprecationWarning,
                        stacklevel=2,
                    )
                    self.add_provider(llama_provider)
                    logger.debug("Auto-discovered default llama.cpp model provider (deprecated)")
        except Exception as e:
            logger.debug(f"Failed to auto-discover default llama.cpp model: {e}")

        # Always add echo provider as fallback
        echo_provider = EchoProvider()
        echo_provider.initialize()
        self.add_provider(echo_provider)
        logger.debug("Added echo provider as fallback")

    def add_provider(self, provider: ModelProvider) -> None:
        """
        Add a provider to the pool.

        Args:
            provider: Provider instance to add
        """
        with self._lock:
            # Don't add duplicate providers (by name)
            if any(p.name == provider.name for p in self.providers):
                logger.debug(f"Provider {provider.name} already in pool, skipping")
                return

            self.providers.append(provider)
            self._provider_cache.clear()  # Invalidate cache
            logger.debug(f"Added provider {provider.name} to pool")

    def remove_provider(self, name: str) -> None:
        """
        Remove a provider from the pool.

        Args:
            name: Name of provider to remove
        """
        with self._lock:
            self.providers = [p for p in self.providers if p.name != name]
            if name in self._provider_cache:
                del self._provider_cache[name]
            logger.debug(f"Removed provider {name} from pool")

    def get_provider(
        self, name: Optional[str] = None, model_name: Optional[str] = None
    ) -> Optional[ModelProvider]:
        """
        Get a specific provider by name or model name.

        Args:
            name: Provider name (e.g., "openrouter", "local-llama-3-8b")
            model_name: Model name to find provider for

        Returns:
            Provider instance or None if not found
        """
        with self._lock:
            # Try cache first
            cache_key = name or model_name or "default"
            if cache_key in self._provider_cache:
                cached = self._provider_cache[cache_key]
                if cached.is_available():
                    return cached

            # Search providers - prefer local model API over llama.cpp
            for provider in self.providers:
                if name and provider.name == name:
                    if provider.is_available():
                        self._provider_cache[cache_key] = provider
                        return provider
                elif model_name:
                    # Check if provider can handle this model
                    if isinstance(provider, OpenRouterProvider) and ModelConfig.is_cloud_model(
                        model_name
                    ):
                        if provider.is_available():
                            provider.model_name = ModelConfig.get_openrouter_model(model_name)
                            self._provider_cache[cache_key] = provider
                            return provider
                    elif isinstance(provider, LocalModelProvider) and (
                        not model_name
                        or model_name == "default"
                        or provider.model_name == model_name
                    ):
                        if provider.is_available():
                            self._provider_cache[cache_key] = provider
                            return provider
                    elif (
                        isinstance(provider, LlamaCppProvider) and provider.model_name == model_name
                    ):
                        if provider.is_available():
                            self._provider_cache[cache_key] = provider
                            return provider

            return None

    def get_available_providers(self) -> List[ModelProvider]:
        """
        Get list of currently available providers.

        Returns:
            List of available provider instances
        """
        with self._lock:
            available = [p for p in self.providers if p.is_available()]

            # Sort by priority: vLLM server (high throughput), OpenRouter, local model API, llama.cpp (deprecated), echo
            def priority(p: ModelProvider) -> int:
                if VLLMServerProvider and isinstance(p, VLLMServerProvider):
                    return 0  # Highest priority - high throughput
                elif isinstance(p, OpenRouterProvider):
                    return 1
                elif isinstance(p, LocalModelProvider):
                    return 2
                elif isinstance(p, LlamaCppProvider):
                    return 3  # Deprecated - kept for backward compatibility
                elif isinstance(p, EchoProvider):
                    return 4
                return 5

            available.sort(key=priority)
            return available

    def generate(
        self,
        prompt: str,
        *,
        provider_name: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 512,
        **kwargs: Any,
    ) -> str:
        """
        Generate response with automatic fallback.

        Args:
            prompt: Input prompt
            provider_name: Optional specific provider to use
            model_name: Optional specific model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Returns:
            Generated text response

        Raises:
            RuntimeError: If no providers are available
        """
        # Try specific provider first if requested
        if provider_name:
            provider = self.get_provider(name=provider_name)
            if provider:
                try:
                    return provider.generate(
                        prompt, temperature=temperature, max_tokens=max_tokens, **kwargs
                    )
                except Exception as e:
                    logger.debug(f"Provider {provider_name} failed: {e}, trying fallback")

        # Try specific model if requested
        if model_name:
            provider = self.get_provider(model_name=model_name)
            if provider:
                try:
                    return provider.generate(
                        prompt, temperature=temperature, max_tokens=max_tokens, **kwargs
                    )
                except Exception as e:
                    logger.debug(f"Model {model_name} failed: {e}, trying fallback")

        # Try all available providers in priority order
        available = self.get_available_providers()
        if not available:
            raise RuntimeError("No model providers are available")

        last_exception: Optional[Exception] = None
        for provider in available:
            try:
                return provider.generate(
                    prompt, temperature=temperature, max_tokens=max_tokens, **kwargs
                )
            except Exception as e:
                logger.debug(f"Provider {provider.name} failed: {e}, trying next")
                last_exception = e

        # All providers failed
        if last_exception:
            raise RuntimeError(
                f"All model providers failed. Last error: {last_exception}"
            ) from last_exception
        raise RuntimeError("All model providers failed with no error details")

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        *,
        provider_name: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 512,
        **kwargs: Any,
    ) -> Optional[str]:
        """
        Generate chat completion with automatic fallback.

        Args:
            messages: List of message dicts with 'role' and 'content'
            provider_name: Optional specific provider to use
            model_name: Optional specific model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Returns:
            Generated text response or None if all providers failed
        """
        # Try specific provider first if requested
        if provider_name:
            provider = self.get_provider(name=provider_name)
            if provider:
                try:
                    return provider.chat_completion(
                        messages, temperature=temperature, max_tokens=max_tokens, **kwargs
                    )
                except Exception as e:
                    logger.debug(f"Provider {provider_name} failed: {e}, trying fallback")

        # Try specific model if requested
        if model_name:
            provider = self.get_provider(model_name=model_name)
            if provider:
                try:
                    return provider.chat_completion(
                        messages, temperature=temperature, max_tokens=max_tokens, **kwargs
                    )
                except Exception as e:
                    logger.debug(f"Model {model_name} failed: {e}, trying fallback")

        # Try all available providers in priority order
        available = self.get_available_providers()
        if not available:
            logger.warning("No model providers are available for chat completion")
            return None

        for provider in available:
            try:
                result = provider.chat_completion(
                    messages, temperature=temperature, max_tokens=max_tokens, **kwargs
                )
                if result:
                    return result
            except Exception as e:
                logger.debug(f"Provider {provider.name} failed: {e}, trying next")

        return None

    def generate_stream(
        self,
        prompt: str,
        *,
        provider_name: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 512,
        **kwargs: Any,
    ) -> Generator[str, None, None]:
        """
        Generate streaming response with automatic fallback.

        Args:
            prompt: Input prompt
            provider_name: Optional specific provider to use
            model_name: Optional specific model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Yields:
            Chunks of generated text
        """
        # Try specific provider first if requested
        if provider_name:
            provider = self.get_provider(name=provider_name)
            if provider:
                try:
                    yield from provider.generate_stream(
                        prompt, temperature=temperature, max_tokens=max_tokens, **kwargs
                    )
                    return
                except Exception as e:
                    logger.debug(f"Provider {provider_name} failed: {e}, trying fallback")

        # Try specific model if requested
        if model_name:
            provider = self.get_provider(model_name=model_name)
            if provider:
                try:
                    yield from provider.generate_stream(
                        prompt, temperature=temperature, max_tokens=max_tokens, **kwargs
                    )
                    return
                except Exception as e:
                    logger.debug(f"Model {model_name} failed: {e}, trying fallback")

        # Try all available providers in priority order
        available = self.get_available_providers()
        if not available:
            raise RuntimeError("No model providers are available for streaming")

        for provider in available:
            try:
                yield from provider.generate_stream(
                    prompt, temperature=temperature, max_tokens=max_tokens, **kwargs
                )
                return
            except Exception as e:
                logger.debug(f"Provider {provider.name} failed: {e}, trying next")

        raise RuntimeError("All model providers failed for streaming")

    def has_local_model_available(self) -> bool:
        """
        Check if a local model provider is available (excludes Echo provider).

        Returns:
            True if a real local model provider is available, False otherwise
        """
        with self._lock:
            for provider in self.providers:
                # Check for LocalModelProvider or deprecated LlamaCppProvider
                if isinstance(provider, (LocalModelProvider, LlamaCppProvider)):
                    if provider.is_available():
                        return True
            return False

    def get_provider_metadata(self) -> Dict[str, bool]:
        """
        Get metadata about which provider types are available.

        Returns:
            Dictionary mapping provider type names to availability status
        """
        with self._lock:
            metadata = {
                "openrouter": any(
                    isinstance(p, OpenRouterProvider) and p.is_available() for p in self.providers
                ),
                "local": any(
                    isinstance(p, (LocalModelProvider, LlamaCppProvider)) and p.is_available()
                    for p in self.providers
                ),
                "echo": any(
                    isinstance(p, EchoProvider) and p.is_available() for p in self.providers
                ),
            }

            # Add vLLM only if the provider is available
            if VLLMServerProvider:
                metadata["vllm"] = any(
                    isinstance(p, VLLMServerProvider) and p.is_available() for p in self.providers
                )
            else:
                metadata["vllm"] = False

            return metadata

    def cleanup(self) -> None:
        """Cleanup all providers in the pool."""
        with self._lock:
            for provider in self.providers:
                try:
                    provider.cleanup()
                except Exception as e:
                    logger.debug(f"Error cleaning up provider {provider.name}: {e}")
            self._provider_cache.clear()

    def to_llm(self) -> LLM:
        """
        Convert pool to LLM interface for backward compatibility.

        Returns:
            LLM adapter instance
        """
        return ModelPoolAdapter(self)


def get_model_pool() -> ModelPool:
    """
    Get or create the global model pool instance.

    Returns:
        Global ModelPool instance
    """
    global _pool_instance

    with _pool_lock:
        if _pool_instance is None:
            _pool_instance = ModelPool()
        return _pool_instance


def reset_model_pool() -> None:
    """Reset the global model pool instance (useful for testing)."""
    global _pool_instance

    with _pool_lock:
        if _pool_instance:
            _pool_instance.cleanup()
        _pool_instance = None
