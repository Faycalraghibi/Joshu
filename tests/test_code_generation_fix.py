import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_code_generation_fix():
    """Test that code generation requests are properly detected and users are guided to use the code command."""
    
    # Mock the console.print function to capture output
    with patch('opencli.ui.cli.console.print') as mock_console_print, \
         patch('opencli.core.config.get_config_manager') as mock_config_manager, \
         patch('opencli.core.context_provider.ContextProvider') as mock_context_provider, \
         patch('opencli.ui.cli.translate_to_command') as mock_translate:
        
        # Mock config manager
        mock_config = MagicMock()
        mock_config.get.side_effect = lambda key, default=None: {
            "model": "llama-3-8b",
            "sandbox_enabled": True,
            "auto_execute": False
        }.get(key, default)
        mock_config_manager.return_value = mock_config
        
        # Mock translation to return a code generation suggestion
        mock_translation = MagicMock()
        mock_translation.command = 'echo "Use the code command: opencli code \\"your request\\""'
        mock_translation.explanation = "This is a code generation request. Use the 'code' command instead."
        mock_translate.return_value = mock_translation
        
        # Import and test the execute_prompt function
        from opencli.ui.cli import execute_prompt
        from click.exceptions import Exit
        
        # This should raise a typer.Exit exception
        with pytest.raises(Exit):
            execute_prompt("give the binary search in python")
        
        # Check that the console print was called with the correct messages
        print_calls = [call[0][0] for call in mock_console_print.call_args_list]
        
        # Should have printed the prompt
        assert any("Prompt:" in str(call) and "give the binary search in python" in str(call) for call in print_calls)
        
        # Should have printed the proposed command
        assert any("Proposed command:" in str(call) for call in print_calls)
        
        # Should have printed the explanation
        assert any("This is a code generation request" in str(call) for call in print_calls)
        
        # Should have printed the tip about using the code command
        assert any("💡 Tip: For code generation requests, use the 'code' command:" in str(call) for call in print_calls)