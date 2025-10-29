import pytest
from unittest.mock import patch, MagicMock, mock_open
import os
import tempfile
from pathlib import Path

# Skip these tests if prompt_toolkit is not available
pytest.importorskip("prompt_toolkit")


def test_enhanced_interactive_mode_import():
    """Test that the enhanced interactive mode can be imported."""
    from joshu.ui.enhanced_interactive import EnhancedInteractiveMode, PROMPT_TOOLKIT_AVAILABLE
    assert EnhancedInteractiveMode is not None
    assert PROMPT_TOOLKIT_AVAILABLE is True


def test_enhanced_interactive_mode_initialization():
    """Test that the enhanced interactive mode can be initialized."""
    with patch('joshu.ui.enhanced_interactive.get_config_manager') as mock_config_manager, \
         patch('joshu.ui.enhanced_interactive.ContextProvider') as mock_context_provider:
        
        # Mock config manager
        mock_config = MagicMock()
        mock_config.get.return_value = 1000
        mock_config_manager.return_value = mock_config
        
        # Mock context provider
        mock_context_provider.return_value = MagicMock()
        
        from joshu.ui.enhanced_interactive import EnhancedInteractiveMode
        mode = EnhancedInteractiveMode("test-model")
        
        assert mode is not None
        assert mode.model == "test-model"


def test_enhanced_interactive_mode_history():
    """Test that the enhanced interactive mode handles history correctly."""
    with patch('joshu.ui.enhanced_interactive.get_config_manager') as mock_config_manager, \
         patch('joshu.ui.enhanced_interactive.ContextProvider') as mock_context_provider:
        
        # Mock config manager
        mock_config = MagicMock()
        mock_config.get.return_value = 1000
        mock_config_manager.return_value = mock_config
        
        # Mock context provider
        mock_context_provider.return_value = MagicMock()
        
        from joshu.ui.enhanced_interactive import EnhancedInteractiveMode
        mode = EnhancedInteractiveMode("test-model")
        
        # Test adding to history
        mode._add_to_history("test command")
        assert len(mode.command_history) == 1
        assert mode.command_history[0] == "test command"
        
        # Test duplicate prevention
        mode._add_to_history("test command")
        assert len(mode.command_history) == 1  # Should not add duplicate
        
        # Test adding different command
        mode._add_to_history("another command")
        assert len(mode.command_history) == 2


def test_enhanced_interactive_mode_file_injection():
    """Test that the enhanced interactive mode handles file injection."""
    with patch('joshu.ui.enhanced_interactive.get_config_manager') as mock_config_manager, \
         patch('joshu.ui.enhanced_interactive.ContextProvider') as mock_context_provider, \
         patch('joshu.ui.enhanced_interactive.Path.exists') as mock_exists, \
         patch('builtins.open', mock_open(read_data="test content")):
        
        # Mock config manager
        mock_config = MagicMock()
        mock_config.get.return_value = 1000
        mock_config_manager.return_value = mock_config
        
        # Mock context provider
        mock_context_provider.return_value = MagicMock()
        
        # Mock file existence
        mock_exists.return_value = True
        
        from joshu.ui.enhanced_interactive import EnhancedInteractiveMode
        mode = EnhancedInteractiveMode("test-model")
        
        # Test file injection
        mode._handle_file_injection("@test.txt")
        # Should not raise an exception


def test_enhanced_interactive_mode_bash_command():
    """Test that the enhanced interactive mode handles bash commands."""
    with patch('joshu.ui.enhanced_interactive.get_config_manager') as mock_config_manager, \
         patch('joshu.ui.enhanced_interactive.ContextProvider') as mock_context_provider, \
         patch('joshu.ui.enhanced_interactive.run_command') as mock_run_command:
        
        # Mock config manager
        mock_config = MagicMock()
        mock_config.get.return_value = 1000
        mock_config_manager.return_value = mock_config
        
        # Mock context provider
        mock_context_provider.return_value = MagicMock()
        
        # Mock run_command to return success
        mock_run_command.return_value = (0, "output", "")
        
        from joshu.ui.enhanced_interactive import EnhancedInteractiveMode
        mode = EnhancedInteractiveMode("test-model")
        
        # Test bash command execution
        mode._handle_bash_command("!ls")
        mock_run_command.assert_called_with("ls")


def test_enhanced_interactive_mode_slash_commands():
    """Test that the enhanced interactive mode handles slash commands."""
    with patch('joshu.ui.enhanced_interactive.get_config_manager') as mock_config_manager, \
         patch('joshu.ui.enhanced_interactive.ContextProvider') as mock_context_provider, \
         patch('builtins.print') as mock_print:
        
        # Mock config manager
        mock_config = MagicMock()
        mock_config.get.return_value = 1000
        mock_config_manager.return_value = mock_config
        
        # Mock context provider
        mock_context_provider.return_value = MagicMock()
        
        from joshu.ui.enhanced_interactive import EnhancedInteractiveMode
        mode = EnhancedInteractiveMode("test-model")
        
        # Test /help command
        result = mode._handle_slash_command("/help")
        assert result is True
        mock_print.assert_called()  # Should have printed help text
        
        # Test /clear command
        mode.command_history = ["cmd1", "cmd2"]
        result = mode._handle_slash_command("/clear")
        assert result is True
        assert len(mode.command_history) == 0  # Should be cleared
        
        # Test /history command with empty history
        result = mode._handle_slash_command("/history")
        assert result is True
        
        # Test /history command with history
        mode.command_history = ["cmd1", "cmd2"]
        result = mode._handle_slash_command("/history")
        assert result is True


def test_enhanced_interactive_mode_config_commands():
    """Test that the enhanced interactive mode handles config commands."""
    with patch('joshu.ui.enhanced_interactive.get_config_manager') as mock_config_manager, \
         patch('joshu.ui.enhanced_interactive.ContextProvider') as mock_context_provider, \
         patch('builtins.print') as mock_print:
        
        # Mock config manager
        mock_config = MagicMock()
        mock_config.get.return_value = 1000
        mock_config.set.return_value = True
        mock_config.save_config.return_value = True
        mock_config.config.to_dict.return_value = {"model": "test-model"}
        mock_config_manager.return_value = mock_config
        
        # Mock context provider
        mock_context_provider.return_value = MagicMock()
        
        from joshu.ui.enhanced_interactive import EnhancedInteractiveMode
        mode = EnhancedInteractiveMode("test-model")
        
        # Test /config command (show all)
        result = mode._handle_slash_command("/config")
        assert result is True
        mock_print.assert_called()  # Should have printed config
        
        # Test /config command (get specific value)
        mock_config.get.return_value = "test-value"
        result = mode._handle_slash_command("/config model")
        assert result is True
        
        # Test /config command (set value)
        result = mode._handle_slash_command("/config model new-model")
        assert result is True
        mock_config.set.assert_called_with("model", "new-model")
        mock_config.save_config.assert_called()


def test_enhanced_interactive_mode_model_commands():
    """Test that the enhanced interactive mode handles model commands."""
    with patch('joshu.ui.enhanced_interactive.get_config_manager') as mock_config_manager, \
         patch('joshu.ui.enhanced_interactive.ContextProvider') as mock_context_provider, \
         patch('builtins.print') as mock_print:
        
        # Mock config manager
        mock_config = MagicMock()
        mock_config.get.side_effect = lambda key, default=None: {
            "model": "test-model",
            "history_limit": 1000
        }.get(key, default)
        mock_config.set.return_value = True
        mock_config.save_config.return_value = True
        mock_config_manager.return_value = mock_config
        
        # Mock context provider
        mock_context_provider.return_value = MagicMock()
        
        from joshu.ui.enhanced_interactive import EnhancedInteractiveMode
        mode = EnhancedInteractiveMode("test-model")
        
        # Test /model command (show current)
        result = mode._handle_slash_command("/model")
        assert result is True
        mock_print.assert_called()  # Should have printed current model
        
        # Test /model command (switch model)
        result = mode._handle_slash_command("/model new-model")
        assert result is True
        mock_config.set.assert_called_with("model", "new-model")
        mock_config.save_config.assert_called()
