"""Tests for OpenRouter integration."""

import os
import pytest
from unittest.mock import patch, MagicMock

from joshu.models.openrouter import chat_completion, translate_command_with_openrouter


class TestOpenRouterIntegration:
    """Test OpenRouter integration functionality."""
    
    @patch('joshu.models.openrouter.get_openrouter_client')
    def test_chat_completion_success(self, mock_client_factory):
        """Test successful chat completion with OpenRouter."""
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "test response"
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_client_factory.return_value = mock_client
        
        messages = [{"role": "user", "content": "test"}]
        result = chat_completion(messages)
        
        assert result == "test response"
        mock_client.chat.completions.create.assert_called_once()
    
    @patch('joshu.models.openrouter.get_openrouter_client')
    def test_chat_completion_no_client(self, mock_client_factory):
        """Test chat completion when no OpenRouter client is available."""
        mock_client_factory.return_value = None
        messages = [{"role": "user", "content": "test"}]
        result = chat_completion(messages)
        
        assert result is None
    
    @patch('joshu.models.openrouter.get_openrouter_client')
    def test_chat_completion_exception(self, mock_client_factory):
        """Test chat completion when an exception occurs."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API error")
        mock_client_factory.return_value = mock_client
        
        messages = [{"role": "user", "content": "test"}]
        result = chat_completion(messages)
        
        assert result is None
    
    @patch('joshu.models.openrouter.chat_completion')
    def test_translate_command_with_openrouter_success(self, mock_chat):
        """Test successful command translation with OpenRouter."""
        mock_response = '{"command": "ls -la", "explanation": "List all files"}'
        mock_chat.return_value = mock_response
        
        result = translate_command_with_openrouter("list all files")
        
        assert result is not None
        assert result["command"] == "ls -la"
        assert result["explanation"] == "List all files"
    
    @patch('joshu.models.openrouter.chat_completion')
    def test_translate_command_with_openrouter_no_response(self, mock_chat):
        """Test command translation when no response is received."""
        mock_chat.return_value = None
        result = translate_command_with_openrouter("list all files")
        
        assert result is None
    
    @patch('joshu.models.openrouter.chat_completion')
    def test_translate_command_with_openrouter_invalid_json(self, mock_chat):
        """Test command translation when invalid JSON is received."""
        mock_chat.return_value = "invalid json"
        result = translate_command_with_openrouter("list all files")
        
        assert result is None