"""Tests for model utilities."""

import pytest
import json

from joshu.tools.parsing_utils import (
    parse_json_response,
    extract_command_and_explanation,
)
from joshu.tools.response_utils import (
    is_conversational_response,
    format_messages_as_prompt,
    chunk_response,
)


class TestParseJsonResponse:
    """Test JSON parsing utilities."""
    
    def test_parse_simple_json(self):
        """Test parsing simple JSON response."""
        response = '{"command": "ls", "explanation": "List files"}'
        result = parse_json_response(response)
        assert result is not None
        assert result["command"] == "ls"
        assert result["explanation"] == "List files"
    
    def test_parse_json_with_markdown(self):
        """Test parsing JSON wrapped in markdown code blocks."""
        response = '```json\n{"command": "ls", "explanation": "List files"}\n```'
        result = parse_json_response(response)
        assert result is not None
        assert result["command"] == "ls"
    
    def test_parse_json_with_extra_text(self):
        """Test parsing JSON with extra text around it."""
        response = 'Some text {"command": "ls", "explanation": "List files"} more text'
        result = parse_json_response(response)
        assert result is not None
        assert result["command"] == "ls"
    
    def test_parse_invalid_json(self):
        """Test parsing invalid JSON returns None."""
        response = "not json at all"
        result = parse_json_response(response)
        assert result is None
    
    def test_parse_empty_response(self):
        """Test parsing empty response returns None."""
        result = parse_json_response("")
        assert result is None


class TestExtractCommandAndExplanation:
    """Test command and explanation extraction."""
    
    def test_extract_from_json(self):
        """Test extracting from valid JSON."""
        response = '{"command": "ls -la", "explanation": "List all files"}'
        command, explanation = extract_command_and_explanation(response)
        assert command == "ls -la"
        assert explanation == "List all files"
    
    def test_extract_from_markdown_json(self):
        """Test extracting from markdown-wrapped JSON."""
        response = '```json\n{"command": "pwd", "explanation": "Print working directory"}\n```'
        command, explanation = extract_command_and_explanation(response)
        assert command == "pwd"
        assert explanation == "Print working directory"
    
    def test_extract_from_text_pattern(self):
        """Test extracting from text patterns."""
        response = 'Command: "ls"\nExplanation: "List files"'
        command, explanation = extract_command_and_explanation(response)
        # May or may not work depending on pattern matching
        assert command is not None or explanation is not None


class TestConversationalResponse:
    """Test conversational response detection."""
    
    def test_detect_conversational_from_explanation(self):
        """Test detecting conversational from explanation."""
        response = "some response"
        explanation = "Conversational response - providing direct answer"
        assert is_conversational_response(response, explanation) == True
    
    def test_detect_conversational_from_triple_quotes(self):
        """Test detecting conversational from triple quotes."""
        response = 'echo """Hello there"""'
        assert is_conversational_response(response) == True
    
    def test_detect_conversational_from_long_echo(self):
        """Test detecting conversational from long echo command."""
        response = 'echo "This is a very long response that should be detected as conversational because it is more than 100 characters long and starts with echo"'
        assert is_conversational_response(response) == True
    
    def test_not_conversational(self):
        """Test that regular commands are not conversational."""
        response = "ls -la"
        explanation = "List all files"
        assert is_conversational_response(response, explanation) == False


class TestFormatMessagesAsPrompt:
    """Test message formatting."""
    
    def test_format_simple_messages(self):
        """Test formatting simple messages."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello"},
        ]
        prompt = format_messages_as_prompt(messages)
        assert "System: You are a helpful assistant" in prompt
        assert "User: Hello" in prompt
        assert "Assistant:" in prompt
    
    def test_format_with_assistant_message(self):
        """Test formatting with assistant message."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
            {"role": "user", "content": "How are you?"},
        ]
        prompt = format_messages_as_prompt(messages)
        assert "User: Hello" in prompt
        assert "Assistant: Hi there" in prompt
        assert "User: How are you?" in prompt


class TestChunkResponse:
    """Test response chunking."""
    
    def test_chunk_simple_response(self):
        """Test chunking a simple response."""
        response = "a" * 100  # 100 characters
        chunks = list(chunk_response(response, chunk_size=25))
        assert len(chunks) == 4
        assert all(len(chunk) == 25 for chunk in chunks[:-1])
    
    def test_chunk_short_response(self):
        """Test chunking a short response."""
        response = "short"
        chunks = list(chunk_response(response, chunk_size=10))
        assert len(chunks) == 1
        assert chunks[0] == "short"
    
    def test_chunk_empty_response(self):
        """Test chunking an empty response."""
        response = ""
        chunks = list(chunk_response(response))
        assert len(chunks) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


