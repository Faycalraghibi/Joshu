"""Tests for model switching functionality."""

import pytest
from unittest.mock import patch, MagicMock

from joshu.core.translate import translate_to_command
from joshu.core.context_provider import ContextProvider
from joshu.models.inference import get_model, unload_model, list_loaded_models, clear_model_cache


class TestModelSwitching:
    """Test model switching functionality."""
    
    def test_model_switching(self):
        """Test that we can switch between different models."""
        # Test that we can get different model instances
        model1 = get_model("llama-3-8b")
        model2 = get_model("mistral-7b")
        
        # They should be different objects
        assert model1 is not model2
        
        # Test that we get the same instance when requesting the same model
        model1_again = get_model("llama-3-8b")
        assert model1 is model1_again
    
    def test_model_caching(self):
        """Test that models are properly cached."""
        # Clear cache first
        clear_model_cache()
        
        # Initially no models should be loaded
        assert len(list_loaded_models()) == 0
        
        # Load a model
        model = get_model("test-model")
        assert len(list_loaded_models()) == 1
        assert "test-model" in list_loaded_models()
        
        # Load the same model again (should return cached version)
        model2 = get_model("test-model")
        assert model is model2
        assert len(list_loaded_models()) == 1
        
        # Load a different model
        model3 = get_model("test-model-2")
        assert model is not model3
        assert len(list_loaded_models()) == 2
        assert "test-model-2" in list_loaded_models()
    
    def test_model_unloading(self):
        """Test that models can be unloaded."""
        # Clear cache first
        clear_model_cache()
        
        # Load a model
        model = get_model("test-model-to-unload")
        assert len(list_loaded_models()) == 1
        
        # Unload the model
        assert unload_model("test-model-to-unload") == True
        assert len(list_loaded_models()) == 0
        
        # Try to unload a non-existent model
        assert unload_model("non-existent-model") == False
    
    @patch("joshu.models.openrouter.chat_completion")
    def test_translate_with_different_models(self, mock_chat):
        """Test that translation works with different models."""
        mock_chat.return_value = '{"command": "echo Hello", "explanation": "Print greeting"}'
        
        context_provider = ContextProvider()
        context_provider.set_system_info("Windows 10")
        
        # Test with default model
        result1 = translate_to_command("say hello", context_provider, "default")
        assert result1 is not None
        # May return echo command or conversational response
        assert ("echo" in result1.command.lower() or 
                "hello" in result1.command.lower() or
                "greeting" in result1.explanation.lower())
        
        # Test with specific model
        result2 = translate_to_command("say hello", context_provider, "llama-3-8b")
        assert result2 is not None
        # May return echo command or conversational response
        assert ("echo" in result2.command.lower() or 
                "hello" in result2.command.lower() or
                "greeting" in result2.explanation.lower())