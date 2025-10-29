import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_code_generation_detection():
    """Test that code generation requests are detected and handled properly."""
    from joshu.core.translate import translate_to_command
    
    # Test case 1: "give the binary search in python"
    with patch('joshu.core.translate.ContextProvider') as mock_context_provider:
        mock_context_provider.return_value = None
        translation = translate_to_command("give the binary search in python")
        
        # Should return a translation suggesting to use the code command
        assert translation is not None
        assert "code command" in translation.explanation.lower() or "code' command" in translation.explanation.lower()
        assert "joshu code" in translation.command.lower()
        
    # Test case 2: "show me the code for binary search in python"
    with patch('joshu.core.translate.ContextProvider') as mock_context_provider:
        mock_context_provider.return_value = None
        translation = translate_to_command("show me the code for binary search in python")
        
        # Should return a translation suggesting to use the code command
        assert translation is not None
        assert "code command" in translation.explanation.lower() or "code' command" in translation.explanation.lower()
        assert "joshu code" in translation.command.lower()
        
    # Test case 3: "generate binary search code in python"
    with patch('joshu.core.translate.ContextProvider') as mock_context_provider:
        mock_context_provider.return_value = None
        translation = translate_to_command("generate binary search code in python")
        
        # Should return a translation suggesting to use the code command
        assert translation is not None
        assert "code command" in translation.explanation.lower() or "code' command" in translation.explanation.lower()
        assert "joshu code" in translation.command.lower()


def test_non_code_requests_still_work():
    """Test that non-code requests still work properly."""
    from joshu.core.translate import translate_to_command
    
    # Test case: "show disk usage" should still work
    with patch('joshu.core.translate.ContextProvider') as mock_context_provider:
        mock_context_provider.return_value = None
        translation = translate_to_command("show disk usage")
        
        # Should return a translation (might be None if no pattern matches, but shouldn't suggest code command)
        if translation is not None:
            assert "code command" not in translation.explanation.lower()
            assert "joshu code" not in translation.command.lower()