"""Tests for vLLM Server Provider."""

import os
from unittest.mock import MagicMock, patch

import pytest

from joshu.models.providers.vllm_server import VLLM_AVAILABLE, VLLMServerProvider


class TestVLLMServerProvider:
    """Test vLLM server provider."""

    def test_provider_initialization_with_server_url(self):
        """Test provider initialization with server URL."""
        provider = VLLMServerProvider(model_name="test-model", server_url="http://localhost:8000")
        assert provider.name == "vllm-server"
        assert provider.model_name == "test-model"
        assert provider.server_url == "http://localhost:8000"

    def test_provider_initialization_with_model_name(self):
        """Test provider initialization with model name only."""
        provider = VLLMServerProvider(model_name="meta-llama/Meta-Llama-3-8B")
        assert provider.model_name == "meta-llama/Meta-Llama-3-8B"
        assert provider.server_url is None

    def test_provider_initialization_from_env(self):
        """Test provider initialization from environment variables."""
        os.environ["VLLM_MODEL"] = "meta-llama/Meta-Llama-3-8B"
        os.environ["VLLM_SERVER_URL"] = "http://localhost:8000"

        provider = VLLMServerProvider()
        assert provider.model_name == "meta-llama/Meta-Llama-3-8B"
        assert provider.server_url == "http://localhost:8000"

    @patch("openai.OpenAI")  # Patch OpenAI from the openai module, not vllm_server
    def test_initialize_with_server_url(self, mock_openai_class):
        """Test initialization with server URL."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        provider = VLLMServerProvider(model_name="test-model", server_url="http://localhost:8000")

        result = provider.initialize()

        assert result is True
        assert provider.is_available() is True
        mock_openai_class.assert_called_once_with(
            base_url="http://localhost:8000", api_key="not-needed"
        )

    @patch("joshu.models.providers.vllm_server.LLM")
    @patch("joshu.models.providers.vllm_server.VLLM_AVAILABLE", True)
    def test_initialize_with_direct_api(self, mock_llm_class):
        """Test initialization with direct vLLM API."""
        mock_llm_instance = MagicMock()
        mock_llm_class.return_value = mock_llm_instance

        provider = VLLMServerProvider(model_name="meta-llama/Meta-Llama-3-8B")

        result = provider.initialize()

        # Since we've patched VLLM_AVAILABLE to True, initialization should succeed
        assert result is True
        assert provider.is_available() is True
        mock_llm_class.assert_called_once_with("meta-llama/Meta-Llama-3-8B")

    @patch("openai.OpenAI")  # Patch OpenAI from the openai module
    def test_generate_via_server(self, mock_openai_class):
        """Test generation via server endpoint."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = "Hello, world!"
        mock_client.chat.completions.create.return_value = mock_completion

        provider = VLLMServerProvider(model_name="test-model", server_url="http://localhost:8000")
        provider.initialize()

        result = provider.generate("Hello")

        assert result == "Hello, world!"
        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "test-model"
        assert call_kwargs["temperature"] == 0.1
        assert call_kwargs["max_tokens"] == 512

    @patch("joshu.models.providers.vllm_server.LLM")
    @patch("joshu.models.providers.vllm_server.SamplingParams")
    @patch("joshu.models.providers.vllm_server.VLLM_AVAILABLE", True)
    def test_generate_via_direct_api(self, mock_sampling_params, mock_llm_class):
        """Test generation via direct vLLM API."""
        if not VLLM_AVAILABLE:
            pytest.skip("vLLM not available")

        mock_llm_instance = MagicMock()
        mock_llm_class.return_value = mock_llm_instance

        mock_output = MagicMock()
        mock_output.outputs = [MagicMock()]
        mock_output.outputs[0].text = "Hello, world!"
        mock_llm_instance.generate.return_value = [mock_output]

        provider = VLLMServerProvider(model_name="meta-llama/Meta-Llama-3-8B")
        provider.initialize()

        result = provider.generate("Hello")

        assert result == "Hello, world!"
        mock_llm_instance.generate.assert_called_once()

    @patch("openai.OpenAI")  # Patch OpenAI from the openai module
    def test_generate_stream_via_server(self, mock_openai_class):
        """Test streaming generation via server endpoint."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        # Mock streaming response
        mock_chunk1 = MagicMock()
        mock_chunk1.choices = [MagicMock()]
        mock_chunk1.choices[0].delta.content = "Hello"

        mock_chunk2 = MagicMock()
        mock_chunk2.choices = [MagicMock()]
        mock_chunk2.choices[0].delta.content = ", world!"

        mock_client.chat.completions.create.return_value = [mock_chunk1, mock_chunk2]

        provider = VLLMServerProvider(model_name="test-model", server_url="http://localhost:8000")
        provider.initialize()

        chunks = list(provider.generate_stream("Hello"))

        assert len(chunks) == 2
        assert chunks[0] == "Hello"
        assert chunks[1] == ", world!"

    def test_is_available_before_initialization(self):
        """Test is_available returns False before initialization."""
        provider = VLLMServerProvider()
        assert provider.is_available() is False

    def test_cleanup(self):
        """Test cleanup releases resources."""
        provider = VLLMServerProvider()
        provider._llm = MagicMock()
        # _client is created during initialization, so we need to mock that
        provider._initialized = True
        provider._available = True

        provider.cleanup()

        assert provider._llm is None
        assert provider._initialized is False
        assert provider._available is False
