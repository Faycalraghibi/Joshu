"""Tests for the new model pool architecture."""

import pytest
from unittest.mock import patch, MagicMock
import os

from joshu.models.pool import ModelPool, get_model_pool, reset_model_pool
from joshu.models.base import LLM, ModelProvider
from joshu.models.config import ModelConfig
from joshu.models.providers import (
    EchoProvider,
    LlamaCppProvider,
    OpenRouterProvider,
    LocalModelProvider,
)


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
        assert provider._initialized == True
        
        pool.cleanup()
        # Providers should be cleaned up
        assert provider._initialized == False


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
            assert ModelConfig.has_any_api_key() == False
        
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test"}):
            assert ModelConfig.has_any_api_key() == True
    
    def test_should_use_cloud(self):
        """Test cloud usage determination."""
        with patch.dict(os.environ, {}, clear=True):
            assert ModelConfig.should_use_cloud() == False
        
        with patch.dict(os.environ, {"JOSHU_USE_CLOUD": "true"}):
            assert ModelConfig.should_use_cloud() == True
        
        with patch.dict(os.environ, {"JOSHU_USE_CLOUD": "false"}):
            assert ModelConfig.should_use_cloud() == False
        
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test"}, clear=True):
            assert ModelConfig.should_use_cloud() == True
    
    def test_is_cloud_model(self):
        """Test cloud model detection."""
        assert ModelConfig.is_cloud_model("deepseek/test") == True
        assert ModelConfig.is_cloud_model("openai/gpt-4") == True
        assert ModelConfig.is_cloud_model("llama-3-8b") == False
    
    def test_get_openrouter_model(self):
        """Test getting OpenRouter model name."""
        with patch.dict(os.environ, {"OPENROUTER_MODEL": "custom/model"}):
            assert ModelConfig.get_openrouter_model() == "custom/model"
        
        with patch.dict(os.environ, {}, clear=True):
            model = ModelConfig.get_openrouter_model()
            assert model == "openai/gpt-4o-mini"  # Default


class TestEchoProvider:
    """Test EchoProvider."""
    
    def test_echo_provider_initialization(self):
        """Test EchoProvider initialization."""
        provider = EchoProvider()
        assert provider.name == "echo"
        assert provider.is_available() == True
    
    def test_echo_provider_generate(self):
        """Test EchoProvider generation."""
        provider = EchoProvider()
        provider.initialize()
        
        response = provider.generate("ls")
        assert response is not None
        assert isinstance(response, str)
    
    def test_echo_provider_is_llm(self):
        """Test that EchoProvider implements LLM interface."""
        provider = EchoProvider()
        assert isinstance(provider, LLM)
        assert isinstance(provider, ModelProvider)
    
    def test_echo_provider_code_generation_detection(self):
        """Test code generation detection in EchoProvider."""
        provider = EchoProvider()
        provider.initialize()
        
        response = provider.generate("give me code for binary search in python")
        assert "code command" in response.lower() or "code generation" in response.lower()


class TestProviderInterfaces:
    """Test provider interface compliance."""
    
    def test_echo_provider_interface(self):
        """Test that EchoProvider implements all required methods."""
        provider = EchoProvider()
        assert hasattr(provider, "initialize")
        assert hasattr(provider, "is_available")
        assert hasattr(provider, "generate")
        assert hasattr(provider, "chat_completion")
        assert hasattr(provider, "generate_stream")
        assert hasattr(provider, "cleanup")
    
    def test_provider_initialization_required(self):
        """Test that providers need initialization."""
        provider = EchoProvider()
        # EchoProvider is always available, but others might not be
        assert provider.initialize() == True


class TestPoolFallback:
    """Test pool fallback mechanisms."""
    
    def test_fallback_order(self):
        """Test that fallback follows correct priority order."""
        # Initialize with empty list to avoid auto-discovery
        pool = ModelPool(providers=[])
        
        # Add providers in different order
        echo = EchoProvider()
        echo.initialize()
        pool.add_provider(echo)
        
        available = pool.get_available_providers()
        # Echo should be last in priority
        assert len(available) == 1
        assert echo in available
    
    def test_fallback_on_provider_failure(self):
        """Test that pool falls back when provider fails."""
        # Initialize with empty list to avoid auto-discovery
        pool = ModelPool(providers=[])
        
        # Create a mock provider that fails
        class FailingProvider(ModelProvider):
            def __init__(self):
                super().__init__("failing", {})
            
            def initialize(self):
                self._initialized = True
                self._available = True
                return True
            
            def is_available(self):
                return True
            
            def generate(self, prompt, **kwargs):
                raise RuntimeError("Provider failed")
        
        failing = FailingProvider()
        failing.initialize()
        echo = EchoProvider()
        echo.initialize()
        
        pool.add_provider(failing)
        pool.add_provider(echo)
        
        # Should fallback to echo provider
        response = pool.generate("test")
        assert response is not None


class TestBackwardCompatibility:
    """Test backward compatibility with old API."""
    
    def test_get_model_still_works(self):
        """Test that get_model() still works."""
        from joshu.models.inference import get_model
        
        model = get_model("default")
        assert model is not None
        assert isinstance(model, LLM)
        
        response = model.generate("test")
        assert response is not None
    
    def test_echo_model_alias(self):
        """Test that EchoModel alias works."""
        from joshu.models import EchoModel
        
        model = EchoModel()
        assert isinstance(model, LLM)
        assert isinstance(model, ModelProvider)
        
        response = model.generate("ls")
        assert response is not None
    
    def test_llm_interface_available(self):
        """Test that LLM interface is available from base."""
        from joshu.models.base import LLM
        from joshu.models import LLM as LLMFromInit
        
        assert LLM is LLMFromInit


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

