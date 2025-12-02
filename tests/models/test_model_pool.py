"""Tests for Model Pool functionality."""

import os
from unittest.mock import patch

from joshu.models.base import LLM
from joshu.models.config import ModelConfig
from joshu.models.pool import ModelPool, get_model_pool, reset_model_pool
from joshu.models.providers import EchoProvider


class TestModelPool:
    """Test ModelPool functionality."""

    def setup_method(self):
        """Reset pool before each test."""
        reset_model_pool()

    def test_model_pool_initialization(self):
        """Test that ModelPool initializes correctly."""
        # Initialize with empty list to avoid auto-discovery
        pool = ModelPool(providers=[])
        assert pool is not None
        assert isinstance(pool.providers, list)

    def test_model_pool_singleton(self):
        """Test that get_model_pool returns the same instance."""
        pool1 = get_model_pool()
        pool2 = get_model_pool()
        assert pool1 is pool2

    def test_add_provider(self):
        """Test adding providers to the pool."""
        # Initialize with empty list to avoid auto-discovery
        pool = ModelPool(providers=[])
        provider = EchoProvider()
        pool.add_provider(provider)

        assert len(pool.providers) == 1
        assert provider in pool.providers

    def test_add_duplicate_provider(self):
        """Test that duplicate providers are not added."""
        # Initialize with empty list to avoid auto-discovery
        pool = ModelPool(providers=[])
        provider1 = EchoProvider()
        provider2 = EchoProvider()

        pool.add_provider(provider1)
        pool.add_provider(provider2)  # Same name

        # Should only have one
        assert len(pool.providers) == 1

    def test_remove_provider(self):
        """Test removing providers from the pool."""
        # Initialize with empty list to avoid auto-discovery
        pool = ModelPool(providers=[])
        provider = EchoProvider()
        pool.add_provider(provider)

        assert len(pool.providers) == 1
        pool.remove_provider("echo")
        assert len(pool.providers) == 0

    def test_get_provider_by_name(self):
        """Test getting a provider by name."""
        # Initialize with empty list to avoid auto-discovery
        pool = ModelPool(providers=[])
        provider = EchoProvider()
        provider.initialize()
        pool.add_provider(provider)

        found = pool.get_provider(name="echo")
        assert found is not None
        assert found.name == "echo"

    def test_get_available_providers(self):
        """Test getting list of available providers."""
        # Initialize with empty list to avoid auto-discovery
        pool = ModelPool(providers=[])
        provider1 = EchoProvider()
        provider1.initialize()
        pool.add_provider(provider1)

        available = pool.get_available_providers()
        assert len(available) == 1
        assert provider1 in available

    def test_generate_with_echo_provider(self):
        """Test generating response using echo provider."""
        # Initialize with empty list to avoid auto-discovery
        pool = ModelPool(providers=[])
        provider = EchoProvider()
        provider.initialize()
        pool.add_provider(provider)

        response = pool.generate("test prompt")
        assert response is not None
        assert isinstance(response, str)

    def test_generate_with_fallback(self):
        """Test that pool falls back to available providers."""
        # Initialize with empty list to avoid auto-discovery
        pool = ModelPool(providers=[])

        # Add echo provider as fallback
        echo_provider = EchoProvider()
        echo_provider.initialize()
        pool.add_provider(echo_provider)

        # Try to generate with non-existent provider
        response = pool.generate("test", provider_name="nonexistent")

        # Should fallback to echo provider
        assert response is not None

    def test_generate_with_specific_provider(self):
        """Test generating with a specific provider."""
        # Initialize with empty list to avoid auto-discovery
        pool = ModelPool(providers=[])
        provider = EchoProvider()
        provider.initialize()
        pool.add_provider(provider)

        response = pool.generate("ls", provider_name="echo")
        assert response is not None
        assert isinstance(response, str)

    def test_chat_completion(self):
        """Test chat completion through pool."""
        # Initialize with empty list to avoid auto-discovery
        pool = ModelPool(providers=[])
        provider = EchoProvider()
        provider.initialize()
        pool.add_provider(provider)

        messages = [{"role": "user", "content": "hello"}]
        response = pool.chat_completion(messages)

        # Echo provider should return something
        assert response is not None or response == ""  # May return empty for echo

    def test_to_llm_adapter(self):
        """Test converting pool to LLM interface."""
        # Initialize with empty list to avoid auto-discovery
        pool = ModelPool(providers=[])
        provider = EchoProvider()
        provider.initialize()
        pool.add_provider(provider)

        llm = pool.to_llm()
        assert isinstance(llm, LLM)
        assert hasattr(llm, "generate")

        response = llm.generate("test")
        assert response is not None

    def test_cleanup(self):
        """Test pool cleanup."""
        # Initialize with empty list to avoid auto-discovery
        pool = ModelPool(providers=[])
        provider = EchoProvider()
        provider.initialize()
        pool.add_provider(provider)

        # Verify it's initialized before cleanup
        assert provider._initialized is True

        pool.cleanup()
        # Providers should be cleaned up
        assert provider._initialized is False


class TestModelConfig:
    """Test ModelConfig functionality."""

    def test_get_openrouter_api_key(self):
        """Test getting OpenRouter API key."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            key = ModelConfig.get_openrouter_api_key()
            assert key == "test-key"

    def test_get_openrouter_api_key_model_specific(self):
        """Test getting model-specific API key."""
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "deepseek-key"}):
            key = ModelConfig.get_openrouter_api_key("deepseek/test-model")
            assert key == "deepseek-key"

    def test_has_any_api_key(self):
        """Test checking if any API key is available."""
        with patch.dict(os.environ, {}, clear=True):
            assert ModelConfig.has_any_api_key() is False
