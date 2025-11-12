"""Tests for vLLM server provider."""

import os
import pytest
from unittest.mock import patch, MagicMock
from dotenv import load_dotenv

from joshu.models.providers.vllm_server import VLLMServerProvider, VLLM_AVAILABLE
from joshu.models.config import ModelConfig


load_dotenv()


class TestVLLMServerProvider:
    """Test vLLM server provider."""
    
    def setup_method(self):
        """Store originals so tests can modify env safely and restore in teardown."""
        self._orig_vllm_model = os.environ.get("VLLM_MODEL")
        self._orig_vllm_server = os.environ.get("VLLM_SERVER_URL")
    
    def test_provider_initialization_with_server_url(self):
        """Test provider initialization with server URL from environment."""
        model = os.getenv("VLLM_MODEL")
        url = os.getenv("VLLM_SERVER_URL")

        provider = VLLMServerProvider(model_name=model, server_url=url)
        assert provider.model_name == model
        assert provider.server_url == url
        assert provider.name == "vllm-server"
    
    def test_provider_initialization_with_model_name(self):
        """Test provider initialization with model name only (from env)."""
        model = os.getenv("VLLM_MODEL")
        provider = VLLMServerProvider(model_name=model)
        assert provider.model_name == model
        # If VLLM_SERVER_URL is set in the environment, provider picks it up.
        assert provider.server_url == os.getenv("VLLM_SERVER_URL")
    
    def test_provider_initialization_from_env(self):
        """Test provider initialization from environment variables (loaded via dotenv)."""
        # ModelConfig and provider read the raw env values (dotenv already loaded).
        model = os.getenv("VLLM_MODEL")
        url = os.getenv("VLLM_SERVER_URL")

        provider = VLLMServerProvider()
        assert provider.model_name == model
        assert provider.server_url == url
    
    @patch('openai.OpenAI')
    def test_initialize_with_server_url(self, mock_openai):
        """Test initialization with server URL."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        provider = VLLMServerProvider(
            model_name=os.getenv("VLLM_MODEL"),
            server_url=os.getenv("VLLM_SERVER_URL"),
        )
        
        result = provider.initialize()
        
        assert result is True
        assert provider.is_available() is True
        mock_openai.assert_called_once_with(
            base_url=os.getenv("VLLM_SERVER_URL"),
            api_key="not-needed"
        )
    
    @patch('joshu.models.providers.vllm_server.LLM')
    @patch('joshu.models.providers.vllm_server.VLLM_AVAILABLE', True)
    def test_initialize_with_direct_api(self, mock_llm_class):
        """Test initialization with direct vLLM API."""
        # Ensure no server URL env forces server mode
        os.environ.pop("VLLM_SERVER_URL", None)

        mock_llm_instance = MagicMock()
        mock_llm_class.return_value = mock_llm_instance
        
        provider = VLLMServerProvider(model_name="meta-llama/Meta-Llama-3-8B")
        
        result = provider.initialize()
        assert result is True
        assert provider.is_available() is True
        mock_llm_class.assert_called_once_with("meta-llama/Meta-Llama-3-8B")
    
    @patch('openai.OpenAI')
    def test_generate_via_server(self, mock_openai):
        """Test generation via server endpoint."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = "Hello, world!"
        mock_client.chat.completions.create.return_value = mock_completion
        
        provider = VLLMServerProvider(
            model_name=os.getenv("VLLM_MODEL"),
            server_url=os.getenv("VLLM_SERVER_URL"),
        )
        provider.initialize()

        result = provider.generate("Hello")

        assert result == "Hello, world!"
        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == os.getenv("VLLM_MODEL")
        assert call_kwargs["temperature"] == 0.1
        assert call_kwargs["max_tokens"] == 512
    
    @patch('joshu.models.providers.vllm_server.LLM')
    @patch('joshu.models.providers.vllm_server.SamplingParams')
    @patch('joshu.models.providers.vllm_server.VLLM_AVAILABLE', True)
    def test_generate_via_direct_api(self, mock_sampling_params, mock_llm_class):
        """Test generation via direct vLLM API."""
        # Ensure server URL env does not force provider into server mode
        os.environ.pop("VLLM_SERVER_URL", None)
        
        mock_llm_instance = MagicMock()
        mock_llm_class.return_value = mock_llm_instance
        
        mock_output = MagicMock()
        mock_output.outputs = [MagicMock()]
        mock_output.outputs[0].text = "Hello, world!"
        mock_llm_instance.generate.return_value = [mock_output]
        
        provider = VLLMServerProvider(model_name="qwen/qwen3-8b")
        provider.initialize()
        
        result = provider.generate("Hello")
        
        assert result == "Hello, world!"
        mock_llm_instance.generate.assert_called_once()
    
    @patch('openai.OpenAI')
    def test_generate_stream_via_server(self, mock_openai):
        """Test streaming generation via server endpoint."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        # Mock streaming response
        mock_chunk1 = MagicMock()
        mock_chunk1.choices = [MagicMock()]
        mock_chunk1.choices[0].delta.content = "Hello"
        
        mock_chunk2 = MagicMock()
        mock_chunk2.choices = [MagicMock()]
        mock_chunk2.choices[0].delta.content = ", world!"
        
        mock_client.chat.completions.create.return_value = [mock_chunk1, mock_chunk2]
        
        provider = VLLMServerProvider(
            model_name=os.getenv("VLLM_MODEL"),
            server_url=os.getenv("VLLM_SERVER_URL"),
        )
        provider.initialize()
        
        chunks = list(provider.generate_stream("Hello"))
        
        assert len(chunks) == 2
        assert chunks[0] == "Hello"
        assert chunks[1] == ", world!"
    
    def test_is_available_before_initialization(self):
        """Test is_available returns False before initialization."""
        provider = VLLMServerProvider(
            model_name=os.getenv("VLLM_MODEL")
        )
        assert provider.is_available() is False
    
    def test_cleanup(self):
        """Test cleanup releases resources."""
        provider = VLLMServerProvider(
            model_name=os.getenv("VLLM_MODEL"),
            server_url=os.getenv("VLLM_SERVER_URL"),
        )
        provider.cleanup()
        
        assert provider._llm is None
        assert not hasattr(provider, '_client') or provider._client is None
        assert provider.is_available() is False

    def teardown_method(self):
        """Restore original environment after each test."""
        if self._orig_vllm_model is None:
            os.environ.pop("VLLM_MODEL", None)
        else:
            os.environ["VLLM_MODEL"] = self._orig_vllm_model

        if self._orig_vllm_server is None:
            os.environ.pop("VLLM_SERVER_URL", None)
        else:
            os.environ["VLLM_SERVER_URL"] = self._orig_vllm_server


class TestVLLMConfig:
    """Test vLLM configuration."""

    def test_get_vllm_model_from_env(self):
        """Test getting vLLM model from environment (dotenv loaded)."""
        model = ModelConfig.get_vllm_model()
        # ModelConfig reads raw env value; compare to the raw variable loaded by dotenv
        assert model == os.getenv("VLLM_MODEL")

    def test_get_vllm_server_url_from_env(self):
        """Test getting vLLM server URL from environment (dotenv loaded)."""
        url = ModelConfig.get_vllm_server_url()
        assert url == os.getenv("VLLM_SERVER_URL")



