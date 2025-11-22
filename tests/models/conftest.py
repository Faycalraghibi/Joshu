"""Shared fixtures and configuration for model tests."""

import pytest
import os
from unittest.mock import MagicMock


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Provide a clean environment for testing."""
    # Store original environment
    original_env = dict(os.environ)
    
    # Clear model-related environment variables
    model_vars = [
        "LOCAL_MODEL_URL", "LOCAL_MODEL_IDENTIFIER", "OPENROUTER_API_KEY",
        "VLLM_MODEL", "VLLM_SERVER_URL", "DEEPSEEK_API_KEY", "TONGYI_API_KEY",
        "QWEN_API_KEY", "KIMI_DEV_API_KEY", "AGENTICAT_API_KEY"
    ]
    
    for var in model_vars:
        monkeypatch.delenv(var, raising=False)
    
    yield
    
    # Restore original environment
    for key, value in original_env.items():
        os.environ[key] = value


@pytest.fixture
def mock_openai_client():
    """Create a mock OpenAI client."""
    mock_client = MagicMock()
    mock_completion = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "test response"
    mock_completion.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_completion
    return mock_client


@pytest.fixture
def mock_model_config():
    """Create a mock model configuration."""
    return {
        "LOCAL_MODEL_URL": "http://localhost:1234",
        "LOCAL_MODEL_IDENTIFIER": "test-model",
        "OPENROUTER_API_KEY": "test-key",
        "VLLM_MODEL": "meta-llama/Meta-Llama-3-8B",
        "VLLM_SERVER_URL": "http://localhost:8000"
    }