"""Tests for Local Model Provider."""

import pytest
from unittest.mock import patch, MagicMock
import os

from joshu.models.providers import LocalModelProvider
from joshu.models.config import ModelConfig
from .test_model_base import ModelTestBase


class TestLocalModelProvider(ModelTestBase):
    """Test LocalModelProvider functionality."""
    
    def test_local_model_provider_initialization(self):
        """Test LocalModelProvider initialization."""
        with patch.dict(os.environ, {
            "LOCAL_MODEL_URL": "http://localhost:1234",
            "LOCAL_MODEL_IDENTIFIER": "test-model"
        }):
            provider = LocalModelProvider()
            self.assert_provider_initialization(provider, "local", "test-model")
            assert provider.base_url == "http://localhost:1234/v1/chat/completions"
    
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
        mock_response = self.mock_http_response()
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
    def test_local_model_provider_initialize_failure_connection_error(self, mock_post):
        """Test local model provider initialization failure on connection error."""
        import requests
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
        mock_response = self.mock_http_response(status_code=500)
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
        mock_response = self.mock_http_response()
        mock_post.return_value = mock_response
        
        with patch.dict(os.environ, {
            "LOCAL_MODEL_URL": "http://localhost:1234",
            "LOCAL_MODEL_IDENTIFIER": "test-model"
        }):
            provider = LocalModelProvider()
            provider.initialize()
            
            self.assert_provider_availability(provider, True)
    
    def test_local_model_provider_is_available_not_initialized(self):
        """Test local model provider availability when not initialized."""
        provider = LocalModelProvider()
        self.assert_provider_availability(provider, False)
    
    @patch('joshu.models.providers.local.requests.post')
    def test_local_model_provider_generate(self, mock_post):
        """Test local model provider generate method."""
        mock_init_response = self.mock_http_response()
        mock_gen_response = self.mock_http_response(
            response_data={"choices": [{"message": {"content": "Generated response"}}]}
        )
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
        mock_init_response = self.mock_http_response()
        mock_gen_response = self.mock_http_response(
            response_data={"choices": [{"message": {"content": "Chat response"}}]}
        )
        mock_post.side_effect = [mock_init_response, mock_gen_response]
        
        with patch.dict(os.environ, {
            "LOCAL_MODEL_URL": "http://localhost:1234",
            "LOCAL_MODEL_IDENTIFIER": "test-model"
        }):
            provider = LocalModelProvider()
            provider.initialize()
            
            messages = [{"role": "user", "content": "test"}]
            result = provider.chat_completion(messages)
            
            assert result == "Chat response"