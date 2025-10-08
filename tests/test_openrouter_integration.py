import os
import pytest
from unittest.mock import patch, MagicMock
from opencli.models.openrouter import chat_completion, translate_command_with_openrouter


def test_chat_completion_success():
    """Test successful chat completion with OpenRouter."""
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "test response"
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    
    with patch('opencli.models.openrouter.get_openrouter_client') as mock_client_factory:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_client_factory.return_value = mock_client
        
        messages = [{"role": "user", "content": "test"}]
        result = chat_completion(messages)
        
        assert result == "test response"
        mock_client.chat.completions.create.assert_called_once()


def test_chat_completion_no_client():
    """Test chat completion when no OpenRouter client is available."""
    with patch('opencli.models.openrouter.get_openrouter_client', return_value=None):
        messages = [{"role": "user", "content": "test"}]
        result = chat_completion(messages)
        
        assert result is None


def test_chat_completion_exception():
    """Test chat completion when an exception occurs."""
    with patch('opencli.models.openrouter.get_openrouter_client') as mock_client_factory:
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API error")
        mock_client_factory.return_value = mock_client
        
        messages = [{"role": "user", "content": "test"}]
        result = chat_completion(messages)
        
        assert result is None


def test_translate_command_with_openrouter_success():
    """Test successful command translation with OpenRouter."""
    mock_response = '{"command": "ls -la", "explanation": "List all files"}'
    
    with patch('opencli.models.openrouter.chat_completion', return_value=mock_response):
        result = translate_command_with_openrouter("list all files")
        
        assert result is not None
        assert result["command"] == "ls -la"
        assert result["explanation"] == "List all files"


def test_translate_command_with_openrouter_no_response():
    """Test command translation when no response is received."""
    with patch('opencli.models.openrouter.chat_completion', return_value=None):
        result = translate_command_with_openrouter("list all files")
        
        assert result is None


def test_translate_command_with_openrouter_invalid_json():
    """Test command translation when invalid JSON is received."""
    with patch('opencli.models.openrouter.chat_completion', return_value="invalid json"):
        result = translate_command_with_openrouter("list all files")
        
        assert result is None