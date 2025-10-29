import pytest
import platform
from unittest.mock import patch, MagicMock

from joshu.core.translate import translate_to_command
from joshu.core.context_provider import ContextProvider


def test_memory_summary_feature():
    """Test the memory summary feature when asking about history/memory."""
    context_provider = ContextProvider()
    from joshu.tools.system_info import get_detailed_system_info
    context_provider.set_system_info(get_detailed_system_info())
    
    # Add some conversation history
    context_provider.add_to_history("user", "Hello, can you help me?")
    context_provider.add_to_history("assistant", "Of course! What do you need help with?")
    context_provider.add_to_history("user", "Show me how to list files")
    context_provider.add_to_history("assistant", "You can use the 'dir' command to list files")
    
    # Add some memory entries
    context_provider.set_memory("user_preference", "likes python")
    context_provider.set_memory("last_command", "dir")
    
    # Mock the LLM calls to avoid hanging
    with patch("joshu.models.openrouter.chat_completion") as mock_chat_completion:
        mock_chat_completion.return_value = "This is a mock summary of the conversation history and memory."
        
        # Test various ways of asking for memory/history
        test_prompts = [
            "show me the history",
            "tell me the conversation history",
            "what is the memory",
            "give me the context",
            "provide memory summary"
        ]
        
        for prompt in test_prompts:
            translation = translate_to_command(prompt, context_provider)
            assert translation is not None
            # The command should be an echo command for displaying the summary
            assert "echo" in translation.command
            assert "summary" in translation.explanation.lower()
            
    # Test with echo model response
    with patch("joshu.models.openrouter.chat_completion") as mock_chat_completion:
        mock_chat_completion.return_value = "Echo: You are a helpful assistant..."
        
        translation = translate_to_command("show me the history", context_provider)
        assert translation is not None
        assert "echo" in translation.command
        assert "summary" in translation.explanation.lower()


def test_memory_summary_without_context_provider():
    """Test memory summary request without context provider."""
    # Should fall back to pattern matching
    translation = translate_to_command("show me the history")
    assert translation is not None
    # Should get the echo command from the pattern
    assert "echo" in translation.command
    assert "memory summary feature" in translation.command


def test_memory_summary_pattern_matching():
    """Test that memory summary patterns are correctly detected."""
    import re
    
    # Test the regex pattern
    pattern = re.compile(r"(show|tell|what|give|provide)(\s+is)?\s+(me\s+)?(the\s+)?(conversation\s+)?(history|memory|context)\b", re.I)
    
    test_cases = [
        "show me the history",
        "tell me the conversation history", 
        "what is the memory",
        "give me the context",
        "provide memory summary",
        "Show HISTORY",
        "TELL ME THE CONVERSATION CONTEXT",
        "what is the conversation history"
    ]
    
    for test_case in test_cases:
        assert pattern.search(test_case) is not None, f"Failed to match: {test_case}"


if __name__ == "__main__":
    pytest.main([__file__])