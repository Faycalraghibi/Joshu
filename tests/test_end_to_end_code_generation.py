import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_end_to_end_code_generation_detection():
    """Test that code generation requests are properly detected in the translation system."""
    
    from opencli.core.translate import translate_to_command
    
    # Test that "give the binary search in python" is detected as a code generation request
    translation = translate_to_command("give the binary search in python")
    
    # Should return a translation suggesting to use the code command
    assert translation is not None
    assert "code command" in translation.explanation.lower() or "code' command" in translation.explanation.lower()
    assert "opencli code" in translation.command.lower()
    
    # Test that "show me the code for binary search in python" is detected as a code generation request
    translation = translate_to_command("show me the code for binary search in python")
    
    # Should return a translation suggesting to use the code command
    assert translation is not None
    assert "code command" in translation.explanation.lower() or "code' command" in translation.explanation.lower()
    assert "opencli code" in translation.command.lower()
    
    # Test that "generate binary search code in python" is detected as a code generation request
    translation = translate_to_command("generate binary search code in python")
    
    # Should return a translation suggesting to use the code command
    assert translation is not None
    assert "code command" in translation.explanation.lower() or "code' command" in translation.explanation.lower()
    assert "opencli code" in translation.command.lower()


def test_end_to_end_non_code_requests():
    """Test that non-code requests still work properly."""
    
    from opencli.core.translate import translate_to_command
    
    # Test that "show disk usage" still works
    translation = translate_to_command("show disk usage")
    
    # Should return a translation for disk usage (might match a pattern)
    # If it matches a pattern, it should not suggest using the code command
    if translation is not None:
        assert "code command" not in translation.explanation.lower()
        assert "opencli code" not in translation.command.lower()
    
    # Test that "list all python files" still works
    translation = translate_to_command("list all python files")
    
    # Should return a translation for finding python files (might match a pattern)
    # If it matches a pattern, it should not suggest using the code command
    if translation is not None:
        assert "code command" not in translation.explanation.lower()
        assert "opencli code" not in translation.command.lower()