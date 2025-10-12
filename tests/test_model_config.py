"""
Test to verify model configuration fixtures from conftest.py are working properly
"""
import pytest
import os


def test_llama_cpp_models(llama_cpp_model_llama3_8b, llama_cpp_model_mistral_7b):
    """Test that Llama CPP model fixtures are correctly configured."""
    # Test that fixtures return the expected values from .env
    assert llama_cpp_model_llama3_8b == "/path/to/llama-3-8b.gguf"
    assert llama_cpp_model_mistral_7b == "/path/to/mistral-7b.gguf"


def test_deepseek_config(deepseek_model, deepseek_api_key):
    """Test that DeepSeek configuration fixtures are correctly configured."""
    expected_model = "deepseek/deepseek-chat-v3.1:free"
    expected_key = "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"
    
    assert deepseek_model == expected_model
    assert deepseek_api_key == expected_key


def test_tongyi_config(tongyi_model, tongyi_api_key):
    """Test that Tongyi configuration fixtures are correctly configured."""
    expected_model = "alibaba/tongyi-deepresearch-30b-a3b:free"
    expected_key = "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"
    
    assert tongyi_model == expected_model
    assert tongyi_api_key == expected_key


def test_qwen_config(qwen_model, qwen_api_key):
    """Test that Qwen configuration fixtures are correctly configured."""
    expected_model = "qwen/qwen3-coder:free"
    expected_key = "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"
    
    assert qwen_model == expected_model
    assert qwen_api_key == expected_key


def test_kimi_dev_config(kimi_dev_model, kimi_dev_api_key):
    """Test that Kimi Dev configuration fixtures are correctly configured."""
    expected_model = "moonshotai/kimi-dev-72b:free"
    expected_key = "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"
    
    assert kimi_dev_model == expected_model
    assert kimi_dev_api_key == expected_key


def test_agenticat_config(agenticat_model, agenticat_api_key):
    """Test that Agenticat configuration fixtures are correctly configured."""
    expected_model = "agentica-org/deepcoder-14b-preview:free"
    expected_key = "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"
    
    assert agenticat_model == expected_model
    assert agenticat_api_key == expected_key


def test_environment_variables_set():
    """Test that environment variables from .env are properly loaded."""
    # These should be set by pytest_sessionstart loading the .env file
    assert "LLAMA_CPP_MODEL_LLAMA3_8B" in os.environ
    assert "LLAMA_CPP_MODEL_MISTRAL_7B" in os.environ
    assert "DEEPSEEK_URL" in os.environ
    assert "DEEPSEEK_API_KEY" in os.environ
    assert "TONGYI_URL" in os.environ
    assert "TONGYI_API_KEY" in os.environ
    assert "QWEN_URL" in os.environ
    assert "QWEN_API_KEY" in os.environ
    assert "KIMI_DEV_URL" in os.environ
    assert "KIMI_DEV_API_KEY" in os.environ
    assert "AGENTICAT_URL" in os.environ
    assert "AGENTICAT_API_KEY" in os.environ
    
    # Verify specific values
    assert os.environ["LLAMA_CPP_MODEL_LLAMA3_8B"] == "/path/to/llama-3-8b.gguf"
    assert os.environ["LLAMA_CPP_MODEL_MISTRAL_7B"] == "/path/to/mistral-7b.gguf"
    assert os.environ["DEEPSEEK_URL"] == "deepseek/deepseek-chat-v3.1:free"
    assert os.environ["DEEPSEEK_API_KEY"] == "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"