"""Tests for Local Model Provider."""

import pytest
import os
import json
from unittest.mock import patch, MagicMock, Mock
import requests

from joshu.models.providers import LocalModelProvider
from joshu.models.config import ModelConfig
from joshu.models.base import LLM, ModelProvider


class TestLocalModelProvider:
    """Test LocalModelProvider functionality."""
    
    def test_local_model_provider_initialization(self):
        """Test LocalModelProvider initialization."""
        with patch.dict(os.environ, {
            "LOCAL_MODEL_URL": "http://localhost:1234",
            "LOCAL_MODEL_IDENTIFIER": "test-model"
        }):
            provider = LocalModelProvider()
            assert provider.name == "local"
            assert provider.base_url == "http://localhost:1234/v1/chat/completions"
            assert provider.model_name == "test-model"
    
    def test_local_model_provider_initialization_with_custom_values(self):
        """Test LocalModelProvider initialization with custom model name."""
        with patch.dict(os.environ, {
            "LOCAL_MODEL_URL": "http://localhost:1234",
            "LOCAL_MODEL_IDENTIFIER": "default-model"
        }):
            provider = LocalModelProvider(model_name="custom-model")
            assert provider.model_name == "custom-model"
    
    def test_local_model_provider_initialization_no_config(self):
        """Test LocalModelProvider initialization without configuration."""
        with patch.dict(os.environ, {}, clear=True):
            provider = LocalModelProvider()
            assert provider.base_url is None
    
    @patch('joshu.models.providers.local.requests.post')
    def test_local_model_provider_initialize_success(self, mock_post):
        """Test successful local model provider initialization."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "test"}}]
        }
        mock_post.return_value = mock_response
        
        with patch.dict(os.environ, {
            "LOCAL_MODEL_URL": "http://localhost:1234",
            "LOCAL_MODEL_IDENTIFIER": "test-model"
        }):
            provider = LocalModelProvider()
            result = provider.initialize()
            
            assert result == True
            assert provider._initialized == True
            assert provider._available == True
            mock_post.assert_called_once()
    
    @patch('joshu.models.providers.local.requests.post')
    def test_local_model_provider_initialize_failure_no_url(self, mock_post):
        """Test local model provider initialization failure when URL is missing."""
        with patch.dict(os.environ, {}, clear=True):
            provider = LocalModelProvider()
            result = provider.initialize()
            
            assert result == False
            assert provider._initialized == False
            mock_post.assert_not_called()
    
    @patch('joshu.models.providers.local.requests.post')
    def test_local_model_provider_initialize_failure_no_model(self, mock_post):
        """Test local model provider initialization failure when model identifier is missing."""
        with patch.dict(os.environ, {
            "LOCAL_MODEL_URL": "http://localhost:1234"
        }):
            # Explicitly remove model identifier env vars
            env_vars_to_remove = ["LOCAL_MODEL_IDENTIFIER"]
            original_env = {}
            for var in env_vars_to_remove:
                original_env[var] = os.environ.pop(var, None)
            
            try:
                provider = LocalModelProvider()
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
    
    @patch('joshu.models.providers.local.requests.post')
    def test_local_model_provider_initialize_failure_connection_error(self, mock_post):
        """Test local model provider initialization failure on connection error."""
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        with patch.dict(os.environ, {
            "LOCAL_MODEL_URL": "http://localhost:1234",
            "LOCAL_MODEL_IDENTIFIER": "test-model"
        }):
            provider = LocalModelProvider()
            result = provider.initialize()
            
            assert result == False
            assert provider._initialized == False
    
    @patch('joshu.models.providers.local.requests.post')
    def test_local_model_provider_initialize_failure_bad_status(self, mock_post):
        """Test local model provider initialization failure on bad HTTP status."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response
        
        with patch.dict(os.environ, {
            "LOCAL_MODEL_URL": "http://localhost:1234",
            "LOCAL_MODEL_IDENTIFIER": "test-model"
        }):
            provider = LocalModelProvider()
            result = provider.initialize()
            
            assert result == False
            assert provider._initialized == False
    
    @patch('joshu.models.providers.local.requests.post')
    def test_local_model_provider_is_available(self, mock_post):
        """Test local model provider availability check."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "test"}}]
        }
        mock_post.return_value = mock_response
        
        with patch.dict(os.environ, {
            "LOCAL_MODEL_URL": "http://localhost:1234",
            "LOCAL_MODEL_IDENTIFIER": "test-model"
        }):
            provider = LocalModelProvider()
            provider.initialize()
            
            assert provider.is_available() == True
    
    def test_local_model_provider_is_available_not_initialized(self):
        """Test local model provider availability when not initialized."""
        provider = LocalModelProvider()
        assert provider.is_available() == False
    
    @patch('joshu.models.providers.local.requests.post')
    def test_local_model_provider_generate(self, mock_post):
        """Test local model provider generate method."""
        mock_init_response = Mock()
        mock_init_response.status_code = 200
        mock_init_response.json.return_value = {
            "choices": [{"message": {"content": "test"}}]
        }
        
        mock_gen_response = Mock()
        mock_gen_response.status_code = 200
        mock_gen_response.json.return_value = {
            "choices": [{"message": {"content": "Generated response"}}]
        }
        
        mock_post.side_effect = [mock_init_response, mock_gen_response]
        
        with patch.dict(os.environ, {
            "LOCAL_MODEL_URL": "http://localhost:1234",
            "LOCAL_MODEL_IDENTIFIER": "test-model"
        }):
            provider = LocalModelProvider()
            result = provider.generate("test prompt")
            
            assert result == "Generated response"
            assert mock_post.call_count == 2
    
    @patch('joshu.models.providers.local.requests.post')
    def test_local_model_provider_chat_completion(self, mock_post):
        """Test local model provider chat_completion method."""
        mock_init_response = Mock()
        mock_init_response.status_code = 200
        mock_init_response.json.return_value = {
            "choices": [{"message": {"content": "test"}}]
        }
        
        mock_gen_response = Mock()
        mock_gen_response.status_code = 200
        mock_gen_response.json.return_value = {
            "choices": [{"message": {"content": "Chat response"}}]
        }
        
        mock_post.side_effect = [mock_init_response, mock_gen_response]
        
        with patch.dict(os.environ, {
            "LOCAL_MODEL_URL": "http://localhost:1234",
            "LOCAL_MODEL_IDENTIFIER": "test-model"
        }):
            provider = LocalModelProvider()
            messages = [{"role": "user", "content": "Hello"}]
            result = provider.chat_completion(messages)
            
            assert result == "Chat response"
            assert mock_post.call_count == 2
    
    @patch('joshu.models.providers.local.requests.post')
    def test_local_model_provider_chat_completion_with_system_message(self, mock_post):
        """Test local model provider chat_completion with existing system message."""
        mock_init_response = Mock()
        mock_init_response.status_code = 200
        mock_init_response.json.return_value = {
            "choices": [{"message": {"content": "test"}}]
        }
        
        mock_gen_response = Mock()
        mock_gen_response.status_code = 200
        mock_gen_response.json.return_value = {
            "choices": [{"message": {"content": "Response"}}]
        }
        
        mock_post.side_effect = [mock_init_response, mock_gen_response]
        
        with patch.dict(os.environ, {
            "LOCAL_MODEL_URL": "http://localhost:1234",
            "LOCAL_MODEL_IDENTIFIER": "test-model"
        }):
            provider = LocalModelProvider()
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello"}
            ]
            result = provider.chat_completion(messages)
            
            assert result == "Response"
            # Verify system message was not duplicated
            call_args = mock_post.call_args_list[1]
            data = json.loads(call_args[1]['data'])
            assert len(data['messages']) == 2
    
    @patch('joshu.models.providers.local.requests.post')
    def test_local_model_provider_chat_completion_max_tokens_negative(self, mock_post):
        """Test local model provider with max_tokens=-1 (unlimited)."""
        mock_init_response = Mock()
        mock_init_response.status_code = 200
        mock_init_response.json.return_value = {
            "choices": [{"message": {"content": "test"}}]
        }
        
        mock_gen_response = Mock()
        mock_gen_response.status_code = 200
        mock_gen_response.json.return_value = {
            "choices": [{"message": {"content": "Response"}}]
        }
        
        mock_post.side_effect = [mock_init_response, mock_gen_response]
        
        with patch.dict(os.environ, {
            "LOCAL_MODEL_URL": "http://localhost:1234",
            "LOCAL_MODEL_IDENTIFIER": "test-model"
        }):
            provider = LocalModelProvider()
            messages = [{"role": "user", "content": "Hello"}]
            result = provider.chat_completion(messages, max_tokens=-1)
            
            assert result == "Response"
            # Verify max_tokens was set to -1
            call_args = mock_post.call_args_list[1]
            data = json.loads(call_args[1]['data'])
            assert data['max_tokens'] == -1
    
    @patch('joshu.models.providers.local.requests.post')
    def test_local_model_provider_chat_completion_error_response(self, mock_post):
        """Test local model provider chat_completion with error response."""
        mock_init_response = Mock()
        mock_init_response.status_code = 200
        mock_init_response.json.return_value = {
            "choices": [{"message": {"content": "test"}}]
        }
        
        mock_gen_response = Mock()
        mock_gen_response.status_code = 400
        mock_gen_response.text = "Bad request"
        mock_post.side_effect = [mock_init_response, mock_gen_response]
        
        with patch.dict(os.environ, {
            "LOCAL_MODEL_URL": "http://localhost:1234",
            "LOCAL_MODEL_IDENTIFIER": "test-model"
        }):
            provider = LocalModelProvider()
            messages = [{"role": "user", "content": "Hello"}]
            result = provider.chat_completion(messages)
            
            assert result is None
    
    @patch('joshu.models.providers.local.requests.post')
    def test_local_model_provider_chat_completion_request_exception(self, mock_post):
        """Test local model provider chat_completion with request exception."""
        mock_init_response = Mock()
        mock_init_response.status_code = 200
        mock_init_response.json.return_value = {
            "choices": [{"message": {"content": "test"}}]
        }
        
        mock_post.side_effect = [mock_init_response, requests.exceptions.RequestException("Connection failed")]
        
        with patch.dict(os.environ, {
            "LOCAL_MODEL_URL": "http://localhost:1234",
            "LOCAL_MODEL_IDENTIFIER": "test-model"
        }):
            provider = LocalModelProvider()
            messages = [{"role": "user", "content": "Hello"}]
            result = provider.chat_completion(messages)
            
            assert result is None
    
    @patch('joshu.models.providers.local.requests.post')
    def test_local_model_provider_chat_completion_unexpected_format(self, mock_post):
        """Test local model provider chat_completion with unexpected response format."""
        mock_init_response = Mock()
        mock_init_response.status_code = 200
        mock_init_response.json.return_value = {
            "choices": [{"message": {"content": "test"}}]
        }
        
        mock_gen_response = Mock()
        mock_gen_response.status_code = 200
        mock_gen_response.json.return_value = {"error": "Unexpected format"}
        mock_post.side_effect = [mock_init_response, mock_gen_response]
        
        with patch.dict(os.environ, {
            "LOCAL_MODEL_URL": "http://localhost:1234",
            "LOCAL_MODEL_IDENTIFIER": "test-model"
        }):
            provider = LocalModelProvider()
            messages = [{"role": "user", "content": "Hello"}]
            result = provider.chat_completion(messages)
            
            assert result is None
    
    @patch('joshu.models.providers.local.requests.post')
    def test_local_model_provider_generate_not_available(self, mock_post):
        """Test local model provider generate when not available."""
        with patch.dict(os.environ, {}, clear=True):
            provider = LocalModelProvider()
            
            with pytest.raises(RuntimeError, match="Local model provider is not available"):
                provider.generate("test")
    
    def test_local_model_provider_cleanup(self):
        """Test local model provider cleanup."""
        with patch.dict(os.environ, {
            "LOCAL_MODEL_URL": "http://localhost:1234",
            "LOCAL_MODEL_IDENTIFIER": "test-model"
        }):
            provider = LocalModelProvider()
            provider.cleanup()
            
            assert provider.base_url is None
            assert provider.model_name is None
            assert provider._initialized == False
    
    def test_local_model_provider_implements_interfaces(self):
        """Test that LocalModelProvider implements required interfaces."""
        provider = LocalModelProvider()
        
        # Check ModelProvider interface
        assert isinstance(provider, ModelProvider)
        assert hasattr(provider, "initialize")
        assert hasattr(provider, "is_available")
        assert hasattr(provider, "generate")
        assert hasattr(provider, "chat_completion")
        assert hasattr(provider, "cleanup")


class TestLocalModelConfig:
    """Test local model configuration methods."""
    
    def test_get_local_model_api_url(self):
        """Test getting local model API URL from environment."""
        with patch.dict(os.environ, {"LOCAL_MODEL_URL": "http://localhost:1234"}):
            url = ModelConfig.get_local_model_api_url()
            assert url == "http://localhost:1234"
    
    def test_get_local_model_api_url_not_set(self):
        """Test getting local model API URL when not set."""
        with patch.dict(os.environ, {}, clear=True):
            url = ModelConfig.get_local_model_api_url()
            assert url is None
    
    def test_get_local_model_api_identifier(self):
        """Test getting local model identifier from environment."""
        with patch.dict(os.environ, {"LOCAL_MODEL_IDENTIFIER": "my-model"}):
            model = ModelConfig.get_local_model_api_identifier()
            assert model == "my-model"
    
    def test_get_local_model_api_identifier_not_set(self):
        """Test getting local model identifier when not set."""
        with patch.dict(os.environ, {}, clear=True):
            model = ModelConfig.get_local_model_api_identifier()
            assert model is None


class TestLocalModelProviderInPool:
    """Test local model provider integration with ModelPool."""
    
    @patch('joshu.models.providers.local.requests.post')
    def test_local_model_provider_in_pool(self, mock_post):
        """Test adding local model provider to pool."""
        from joshu.models.pool import ModelPool
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "test"}}]
        }
        mock_post.return_value = mock_response
        
        with patch.dict(os.environ, {
            "LOCAL_MODEL_URL": "http://localhost:1234",
            "LOCAL_MODEL_IDENTIFIER": "test-model"
        }):
            pool = ModelPool(providers=[])
            provider = LocalModelProvider()
            provider.initialize()
            pool.add_provider(provider)
            
            assert provider in pool.providers
            assert provider.is_available() == True
    
    @patch('joshu.models.providers.local.requests.post')
    def test_local_model_provider_auto_discovery(self, mock_post):
        """Test local model provider auto-discovery in pool."""
        from joshu.models.pool import ModelPool
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "test"}}]
        }
        mock_post.return_value = mock_response
        
        with patch.dict(os.environ, {
            "LOCAL_MODEL_URL": "http://localhost:1234",
            "LOCAL_MODEL_IDENTIFIER": "test-model"
        }):
            # Create a new pool with auto-discovery
            pool = ModelPool(providers=None)
            
            # Check if local model provider was auto-discovered
            local_providers = [p for p in pool.providers if p.name == "local"]
            assert len(local_providers) > 0
            assert local_providers[0].is_available() == True
    
    @patch('joshu.models.providers.local.requests.post')
    def test_local_model_provider_generate_through_pool(self, mock_post):
        """Test generating response through pool using local model provider."""
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
            "LOCAL_MODEL_URL": "http://localhost:1234",
            "LOCAL_MODEL_IDENTIFIER": "test-model"
        }):
            pool = ModelPool(providers=[])
            provider = LocalModelProvider()
            provider.initialize()
            pool.add_provider(provider)
            
            result = pool.generate("Hello", model_name="local")
            
            assert result == "Pool response"

