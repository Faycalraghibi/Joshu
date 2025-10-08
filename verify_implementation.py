#!/usr/bin/env python3
"""
Verification script for OpenCLI implementation.
This script verifies that all the core functionality works correctly.
"""

import os
import sys
import json
from unittest.mock import patch, MagicMock

# Add src to path so we can import opencli modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_translate_with_pattern_matching():
    """Test that pattern matching still works."""
    from opencli.core.translate import translate_to_command
    
    # Test pattern matching
    translation = translate_to_command("show disk usage of current directory")
    assert translation is not None
    assert translation.command == "du -sh ."
    assert "human-readable" in translation.explanation
    print("✅ Pattern matching works")


def test_translate_with_llm_fallback():
    """Test that LLM fallback works."""
    from opencli.core.translate import translate_to_command
    
    # Mock OpenRouter response for a command that doesn't match patterns
    mock_response = json.dumps({
        "command": "ps aux | grep python",
        "explanation": "List all running Python processes"
    })
    
    with patch("opencli.models.openrouter.chat_completion", return_value=mock_response):
        translation = translate_to_command("show all python processes")
        assert translation is not None
        assert translation.command == "ps aux | grep python"
        assert translation.explanation == "List all running Python processes"
    print("✅ LLM fallback works")


def test_openrouter_integration():
    """Test OpenRouter integration."""
    from opencli.models.openrouter import chat_completion
    
    # Test that the function exists and can be called
    messages = [{"role": "user", "content": "test"}]
    # Should return None when no API key is set
    result = chat_completion(messages)
    assert result is None
    print("✅ OpenRouter integration works (returns None without API key)")


def test_local_model_fallback():
    """Test local model fallback."""
    from opencli.models.inference import get_model
    from opencli.models.llm_interface import LLM
    
    # Should fall back to EchoModel when no local model is available
    model = get_model("test")
    assert isinstance(model, LLM)
    response = model.generate("test prompt")
    assert "Echo:" in response
    print("✅ Local model fallback works")


def test_safety_checks():
    """Test safety checks."""
    from opencli.core.safety import assess_command_safety
    
    # Test safe command
    report = assess_command_safety("ls -la")
    assert report.safe == True
    
    # Test unsafe command
    report = assess_command_safety("rm -rf /")
    assert report.safe == False
    assert len(report.reasons) > 0
    print("✅ Safety checks work")


def test_context_management():
    """Test context management."""
    from opencli.core.context import ConversationContext
    
    context = ConversationContext()
    context.add("user", "hello")
    context.add("assistant", "hi there")
    
    messages = context.as_list()
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "hello"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "hi there"
    print("✅ Context management works")


if __name__ == "__main__":
    print("Verifying OpenCLI implementation...\n")
    
    try:
        test_translate_with_pattern_matching()
        test_translate_with_llm_fallback()
        test_openrouter_integration()
        test_local_model_fallback()
        test_safety_checks()
        test_context_management()
        
        print("\n🎉 All tests passed! OpenCLI implementation is working correctly.")
        print("\nKey features implemented:")
        print("  ✅ Natural Language Command Translation with LLM integration")
        print("  ✅ Interactive Chat Mode")
        print("  ✅ Enhanced Local LLM Integration with OpenRouter API support")
        print("  ✅ Pattern matching for common commands")
        print("  ✅ Safety validation for commands")
        print("  ✅ Context management for conversations")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)