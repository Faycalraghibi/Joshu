"""Tests for vLLM/LM Studio provider."""

import pytest
import os
import json
from unittest.mock import patch, MagicMock, Mock
import requests

from joshu.models.providers import VLLMProvider
from joshu.models.config import ModelConfig
from joshu.models.base import LLM, ModelProvider


class TestVLLMProvider:
    """Test VLLMProvider functionality."""
    
    def test_vllm_provider_initialization(self):
        """Test VLLMProvider initialization."""
        with patch.dict(os.environ, {
            "VLLM_URL": "http://localhost:1234/v1/chat/completions",
            "VLLM_MODEL_IDENTIFIER": "test-model"
        }):
            provider = VLLMProvider()
            assert provider.name == "vllm"
            assert provider.base_url == "http://localhost:1234/v1/chat/completions"
            assert provider.model_name == "test-model"
    
    def test_vllm_provider_initialization_with_custom_values(self):
        """Test VLLMProvider initialization with custom model name."""
        with patch.dict(os.environ, {
            "VLLM_URL": "http://localhost:1234/v1/chat/completions",
            "VLLM_MODEL_IDENTIFIER": "default-model"
        }):
            provider = VLLMProvider(model_name="custom-model")
            assert provider.model_name == "custom-model"
    
    def test_vllm_provider_initialization_no_config(self):
        """Test VLLMProvider initialization without configuration."""
        with patch.dict(os.environ, {}, clear=True):
            provider = VLLMProvider()
            assert provider.base_url is None
            assert provider.model_name is None
    
    @patch('joshu.models.providers.vllm.requests.post')
    def test_vllm_provider_initialize_success(self, mock_post):
        """Test successful VLLM provider initialization."""
        # Mock successful health check response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "test"}}]
        }
        mock_post.return_value = mock_response
        
        with patch.dict(os.environ, {
            "VLLM_URL": "http://localhost:1234/v1/chat/completions",
            "VLLM_MODEL_IDENTIFIER": "test-model"
        }):
            provider = VLLMProvider()
            result = provider.initialize()
            
            assert result == True
            assert provider._initialized == True
            assert provider._available == True
            mock_post.assert_called_once()
    
    @patch('joshu.models.providers.vllm.requests.post')
    def test_vllm_provider_initialize_failure_no_url(self, mock_post):
        """Test VLLM provider initialization failure when URL is missing."""
        with patch.dict(os.environ, {}, clear=True):
            provider = VLLMProvider()
            result = provider.initialize()
            
            assert result == False
            assert provider._initialized == False
            assert provider._available == False
            mock_post.assert_not_called()
    
    @patch('joshu.models.providers.vllm.requests.post')
    def test_vllm_provider_initialize_failure_no_model(self, mock_post):
        """Test VLLM provider initialization failure when model identifier is missing."""
        with patch.dict(os.environ, {
            "VLLM_URL": "http://localhost:1234/v1/chat/completions"
        }, clear=False):
            # Explicitly remove model identifier env vars
            env_vars_to_remove = ["VLLM_MODEL_IDENTIFIER", "LM_STUDIO_MODEL_IDENTIFIER", "VLLM_MODEL"]
            original_env = {}
            for var in env_vars_to_remove:
                original_env[var] = os.environ.pop(var, None)
            
            try:
                provider = VLLMProvider()
                result = provider.initialize()
                
                assert result == False
                assert provider._initialized == False
                mock_post.assert_not_called()
            finally:
                # Restore original env vars
                for var, value in original_env.items():
                    if value is not None:
                        os.environ[var] = value
                    elif var in os.environ:
                        del os.environ[var]
    
    @patch('joshu.models.providers.vllm.requests.post')
    def test_vllm_provider_initialize_failure_connection_error(self, mock_post):
        """Test VLLM provider initialization failure on connection error."""
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        with patch.dict(os.environ, {
            "VLLM_URL": "http://localhost:1234/v1/chat/completions",
            "VLLM_MODEL_IDENTIFIER": "test-model"
        }):
            provider = VLLMProvider()
            result = provider.initialize()
            
            assert result == False
            assert provider._initialized == False
    
    @patch('joshu.models.providers.vllm.requests.post')
    def test_vllm_provider_initialize_failure_bad_status(self, mock_post):
        """Test VLLM provider initialization failure on bad HTTP status."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response
        
        with patch.dict(os.environ, {
            "VLLM_URL": "http://localhost:1234/v1/chat/completions",
            "VLLM_MODEL_IDENTIFIER": "test-model"
        }):
            provider = VLLMProvider()
            result = provider.initialize()
            
            assert result == False
            assert provider._initialized == False
    
    @patch('joshu.models.providers.vllm.requests.post')
    def test_vllm_provider_is_available(self, mock_post):
        """Test VLLM provider availability check."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "test"}}]
        }
        mock_post.return_value = mock_response
        
        with patch.dict(os.environ, {
            "VLLM_URL": "http://localhost:1234/v1/chat/completions",
            "VLLM_MODEL_IDENTIFIER": "test-model"
        }):
            provider = VLLMProvider()
            provider.initialize()
            
            assert provider.is_available() == True
    
    def test_vllm_provider_is_available_not_initialized(self):
        """Test VLLM provider availability when not initialized."""
        provider = VLLMProvider()
        assert provider.is_available() == False
    
    @patch('joshu.models.providers.vllm.requests.post')
    def test_vllm_provider_generate(self, mock_post):
        """Test VLLM provider generate method."""
        # Mock initialization response
        mock_init_response = Mock()
        mock_init_response.status_code = 200
        mock_init_response.json.return_value = {
            "choices": [{"message": {"content": "test"}}]
        }
        
        # Mock generation response
        mock_gen_response = Mock()
        mock_gen_response.status_code = 200
        mock_gen_response.json.return_value = {
            "choices": [{"message": {"content": "Hello, how can I help you?"}}]
        }
        
        mock_post.side_effect = [mock_init_response, mock_gen_response]
        
        with patch.dict(os.environ, {
            "VLLM_URL": "http://localhost:1234/v1/chat/completions",
            "VLLM_MODEL_IDENTIFIER": "test-model"
        }):
            provider = VLLMProvider()
            result = provider.generate("Hello", temperature=0.7, max_tokens=100)
            
            assert result == "Hello, how can I help you?"
            assert mock_post.call_count == 2
    
    @patch('joshu.models.providers.vllm.requests.post')
    def test_vllm_provider_chat_completion(self, mock_post):
        """Test VLLM provider chat_completion method."""
        # Mock initialization response (health check)
        mock_init_response = Mock()
        mock_init_response.status_code = 200
        mock_init_response.json.return_value = {
            "choices": [{"message": {"content": "test"}}]
        }
        
        # Mock chat completion response
        mock_chat_response = Mock()
        mock_chat_response.status_code = 200
        mock_chat_response.json.return_value = {
            "choices": [{"message": {"content": "Assistant response"}}]
        }
        
        mock_post.side_effect = [mock_init_response, mock_chat_response]
        
        with patch.dict(os.environ, {
            "VLLM_URL": "http://localhost:1234/v1/chat/completions",
            "VLLM_MODEL_IDENTIFIER": "test-model"
        }):
            provider = VLLMProvider()
            provider.initialize()
            
            messages = [
                {"role": "user", "content": "What is Python?"}
            ]
            result = provider.chat_completion(messages, temperature=0.7, max_tokens=100)
            
            assert result == "Assistant response"
            assert mock_post.call_count == 2  # One for init, one for chat completion
            
            # Verify the chat completion request payload (second call)
            call_args = mock_post.call_args_list[1]
            assert call_args[0][0] == "http://localhost:1234/v1/chat/completions"
            assert call_args[1]["headers"]["Content-Type"] == "application/json"
            
            data = json.loads(call_args[1]["data"])
            assert data["model"] == "test-model"
            assert data["temperature"] == 0.7
            assert data["max_tokens"] == 100
            assert len(data["messages"]) == 2  # System message + user message
            assert data["messages"][0]["role"] == "system"
            assert data["messages"][1]["role"] == "user"
            assert data["messages"][1]["content"] == "What is Python?"
    
    @patch('joshu.models.providers.vllm.requests.post')
    def test_vllm_provider_chat_completion_with_system_message(self, mock_post):
        """Test VLLM provider chat_completion with existing system message."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Response"}}]
        }
        mock_post.return_value = mock_response
        
        with patch.dict(os.environ, {
            "VLLM_URL": "http://localhost:1234/v1/chat/completions",
            "VLLM_MODEL_IDENTIFIER": "test-model"
        }):
            provider = VLLMProvider()
            provider.initialize()
            
            messages = [
                {"role": "system", "content": "You are a coding assistant."},
                {"role": "user", "content": "Write a function"}
            ]
            result = provider.chat_completion(messages)
            
            assert result == "Response"
            call_args = mock_post.call_args
            data = json.loads(call_args[1]["data"])
            # Should not add another system message
            assert len(data["messages"]) == 2
            assert data["messages"][0]["role"] == "system"
    
    @patch('joshu.models.providers.vllm.requests.post')
    def test_vllm_provider_chat_completion_max_tokens_negative(self, mock_post):
        """Test VLLM provider with max_tokens=-1 (unlimited)."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Response"}}]
        }
        mock_post.return_value = mock_response
        
        with patch.dict(os.environ, {
            "VLLM_URL": "http://localhost:1234/v1/chat/completions",
            "VLLM_MODEL_IDENTIFIER": "test-model"
        }):
            provider = VLLMProvider()
            provider.initialize()
            
            messages = [{"role": "user", "content": "test"}]
            provider.chat_completion(messages, max_tokens=-1)
            
            call_args = mock_post.call_args
            data = json.loads(call_args[1]["data"])
            assert data["max_tokens"] == -1
    
    @patch('joshu.models.providers.vllm.requests.post')
    def test_vllm_provider_chat_completion_error_response(self, mock_post):
        """Test VLLM provider chat_completion with error response."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response
        
        with patch.dict(os.environ, {
            "VLLM_URL": "http://localhost:1234/v1/chat/completions",
            "VLLM_MODEL_IDENTIFIER": "test-model"
        }):
            provider = VLLMProvider()
            provider.initialize()
            
            messages = [{"role": "user", "content": "test"}]
            result = provider.chat_completion(messages)
            
            assert result is None
    
    @patch('joshu.models.providers.vllm.requests.post')
    def test_vllm_provider_chat_completion_request_exception(self, mock_post):
        """Test VLLM provider chat_completion with request exception."""
        mock_post.side_effect = requests.exceptions.RequestException("Network error")
        
        with patch.dict(os.environ, {
            "VLLM_URL": "http://localhost:1234/v1/chat/completions",
            "VLLM_MODEL_IDENTIFIER": "test-model"
        }):
            provider = VLLMProvider()
            provider.initialize()
            
            messages = [{"role": "user", "content": "test"}]
            result = provider.chat_completion(messages)
            
            assert result is None
    
    @patch('joshu.models.providers.vllm.requests.post')
    def test_vllm_provider_chat_completion_unexpected_format(self, mock_post):
        """Test VLLM provider chat_completion with unexpected response format."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"unexpected": "format"}
        mock_post.return_value = mock_response
        
        with patch.dict(os.environ, {
            "VLLM_URL": "http://localhost:1234/v1/chat/completions",
            "VLLM_MODEL_IDENTIFIER": "test-model"
        }):
            provider = VLLMProvider()
            provider.initialize()
            
            messages = [{"role": "user", "content": "test"}]
            result = provider.chat_completion(messages)
            
            assert result is None
    
    @patch('joshu.models.providers.vllm.requests.post')
    def test_vllm_provider_generate_not_available(self, mock_post):
        """Test VLLM provider generate when not available."""
        with patch.dict(os.environ, {}, clear=True):
            provider = VLLMProvider()
            
            with pytest.raises(RuntimeError, match="vLLM provider is not available"):
                provider.generate("test")
    
    def test_vllm_provider_cleanup(self):
        """Test VLLM provider cleanup."""
        with patch.dict(os.environ, {
            "VLLM_URL": "http://localhost:1234/v1/chat/completions",
            "VLLM_MODEL_IDENTIFIER": "test-model"
        }):
            provider = VLLMProvider()
            provider.initialize()
            provider.cleanup()
            
            assert provider._initialized == False
            assert provider._available == False
    
    def test_vllm_provider_implements_interfaces(self):
        """Test that VLLMProvider implements required interfaces."""
        provider = VLLMProvider()
        assert isinstance(provider, ModelProvider)
        assert hasattr(provider, "initialize")
        assert hasattr(provider, "is_available")
        assert hasattr(provider, "generate")
        assert hasattr(provider, "chat_completion")
        assert hasattr(provider, "cleanup")


class TestVLLMConfig:
    """Test vLLM configuration methods."""
    
    def test_get_vllm_url(self):
        """Test getting vLLM URL from environment."""
        with patch.dict(os.environ, {"VLLM_URL": "http://localhost:1234/v1/chat/completions"}):
            url = ModelConfig.get_vllm_url()
            assert url == "http://localhost:1234/v1/chat/completions"
    
    def test_get_vllm_url_lm_studio_alias(self):
        """Test getting vLLM URL using LM_STUDIO_URL alias."""
        # Clear VLLM_URL first to test LM_STUDIO_URL alias
        with patch.dict(os.environ, {
            "LM_STUDIO_URL": "http://localhost:1234/v1/chat/completions"
        }, clear=False):
            # Remove VLLM_URL if it exists
            original_vllm_url = os.environ.pop("VLLM_URL", None)
            try:
                url = ModelConfig.get_vllm_url()
                assert url == "http://localhost:1234/v1/chat/completions"
            finally:
                if original_vllm_url is not None:
                    os.environ["VLLM_URL"] = original_vllm_url
    
    def test_get_vllm_url_not_set(self):
        """Test getting vLLM URL when not set."""
        with patch.dict(os.environ, {}, clear=True):
            url = ModelConfig.get_vllm_url()
            assert url is None
    
    def test_get_vllm_model_identifier(self):
        """Test getting vLLM model identifier from environment."""
        with patch.dict(os.environ, {"VLLM_MODEL_IDENTIFIER": "my-model"}):
            model = ModelConfig.get_vllm_model_identifier()
            assert model == "my-model"
    
    def test_get_vllm_model_identifier_aliases(self):
        """Test getting vLLM model identifier using aliases."""
        # Save original env vars
        original_vars = {
            "VLLM_MODEL_IDENTIFIER": os.environ.get("VLLM_MODEL_IDENTIFIER"),
            "LM_STUDIO_MODEL_IDENTIFIER": os.environ.get("LM_STUDIO_MODEL_IDENTIFIER"),
            "VLLM_MODEL": os.environ.get("VLLM_MODEL"),
        }
        
        try:
            # Test LM_STUDIO_MODEL_IDENTIFIER
            # Clear other vars first
            for var in ["VLLM_MODEL_IDENTIFIER", "VLLM_MODEL"]:
                if var in os.environ:
                    del os.environ[var]
            
            with patch.dict(os.environ, {"LM_STUDIO_MODEL_IDENTIFIER": "lm-model"}, clear=False):
                model = ModelConfig.get_vllm_model_identifier()
                assert model == "lm-model"
            
            # Test VLLM_MODEL
            # Clear other vars first
            for var in ["VLLM_MODEL_IDENTIFIER", "LM_STUDIO_MODEL_IDENTIFIER"]:
                if var in os.environ:
                    del os.environ[var]
            
            with patch.dict(os.environ, {"VLLM_MODEL": "vllm-model"}, clear=False):
                model = ModelConfig.get_vllm_model_identifier()
                assert model == "vllm-model"
        finally:
            # Restore original env vars
            for var, value in original_vars.items():
                if value is not None:
                    os.environ[var] = value
                elif var in os.environ:
                    del os.environ[var]
    
    def test_get_vllm_model_identifier_not_set(self):
        """Test getting vLLM model identifier when not set."""
        with patch.dict(os.environ, {}, clear=True):
            model = ModelConfig.get_vllm_model_identifier()
            assert model is None


class TestVLLMProviderInPool:
    """Test VLLM provider integration with ModelPool."""
    
    def setup_method(self):
        """Reset pool before each test."""
        from joshu.models.pool import reset_model_pool
        reset_model_pool()
    
    @patch('joshu.models.providers.vllm.requests.post')
    def test_vllm_provider_in_pool(self, mock_post):
        """Test adding VLLM provider to pool."""
        from joshu.models.pool import ModelPool
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "test"}}]
        }
        mock_post.return_value = mock_response
        
        with patch.dict(os.environ, {
            "VLLM_URL": "http://localhost:1234/v1/chat/completions",
            "VLLM_MODEL_IDENTIFIER": "test-model"
        }):
            pool = ModelPool(providers=[])
            provider = VLLMProvider()
            provider.initialize()
            pool.add_provider(provider)
            
            assert len(pool.providers) == 1
            assert provider in pool.providers
    
    @patch('joshu.models.providers.vllm.requests.post')
    def test_vllm_provider_auto_discovery(self, mock_post):
        """Test VLLM provider auto-discovery in pool."""
        from joshu.models.pool import ModelPool, reset_model_pool
        from joshu.models.config import ModelConfig
        
        reset_model_pool()
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "test"}}]
        }
        mock_post.return_value = mock_response
        
        with patch.dict(os.environ, {
            "VLLM_URL": "http://localhost:1234/v1/chat/completions",
            "VLLM_MODEL_IDENTIFIER": "test-model"
        }):
            # Create a new pool with auto-discovery
            pool = ModelPool(providers=None)
            
            # Check if vLLM provider was auto-discovered
            vllm_providers = [p for p in pool.providers if p.name == "vllm"]
            assert len(vllm_providers) > 0
            assert vllm_providers[0].is_available() == True
    
    @patch('joshu.models.providers.vllm.requests.post')
    def test_vllm_provider_generate_through_pool(self, mock_post):
        """Test generating response through pool using VLLM provider."""
        from joshu.models.pool import ModelPool
        
        # Mock initialization and generation responses
        mock_init_response = Mock()
        mock_init_response.status_code = 200
        mock_init_response.json.return_value = {
            "choices": [{"message": {"content": "test"}}]
        }
        
        mock_gen_response = Mock()
        mock_gen_response.status_code = 200
        mock_gen_response.json.return_value = {
            "choices": [{"message": {"content": "Pool response"}}]
        }
        
        mock_post.side_effect = [mock_init_response, mock_gen_response]
        
        with patch.dict(os.environ, {
            "VLLM_URL": "http://localhost:1234/v1/chat/completions",
            "VLLM_MODEL_IDENTIFIER": "test-model"
        }):
            pool = ModelPool(providers=[])
            provider = VLLMProvider()
            provider.initialize()
            pool.add_provider(provider)
            
            result = pool.generate("Hello", model_name="vllm")
            
            assert result == "Pool response"