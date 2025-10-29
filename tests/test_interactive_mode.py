import pytest
from unittest.mock import patch, MagicMock
from joshu.ui.cli import start_interactive_mode


def test_start_interactive_mode_exit():
    """Test that interactive mode exits correctly when user types 'exit'."""
    with patch('rich.console.Console.input', side_effect=['exit']), \
         patch('rich.console.Console.print') as mock_print, \
         patch('joshu.core.config.get_config_manager') as mock_config_manager:
        # Mock config manager to disable enhanced interactive mode
        config_manager = MagicMock()
        config_manager.get.side_effect = lambda key, default=None: False if key == "enhanced_interactive" else default
        mock_config_manager.return_value = config_manager
        
        start_interactive_mode("test-model")
        # Should print goodbye message
        mock_print.assert_called_with("[dim]Goodbye![/dim]")


def test_start_interactive_mode_quit():
    """Test that interactive mode exits correctly when user types 'quit'."""
    with patch('rich.console.Console.input', side_effect=['quit']), \
         patch('rich.console.Console.print') as mock_print, \
         patch('joshu.core.config.get_config_manager') as mock_config_manager:
        # Mock config manager to disable enhanced interactive mode
        config_manager = MagicMock()
        config_manager.get.side_effect = lambda key, default=None: False if key == "enhanced_interactive" else default
        mock_config_manager.return_value = config_manager
        
        start_interactive_mode("test-model")
        # Should print goodbye message
        mock_print.assert_called_with("[dim]Goodbye![/dim]")


def test_start_interactive_mode_empty_input():
    """Test that interactive mode handles empty input correctly."""
    with patch('rich.console.Console.input', side_effect=['', 'exit']), \
         patch('rich.console.Console.print') as mock_print, \
         patch('joshu.core.config.get_config_manager') as mock_config_manager:
        # Mock config manager to disable enhanced interactive mode
        config_manager = MagicMock()
        config_manager.get.side_effect = lambda key, default=None: False if key == "enhanced_interactive" else default
        mock_config_manager.return_value = config_manager
        
        start_interactive_mode("test-model")


def test_start_interactive_mode_keyboard_interrupt():
    """Test that interactive mode handles keyboard interrupt correctly."""
    with patch('rich.console.Console.input', side_effect=KeyboardInterrupt), \
         patch('rich.console.Console.print') as mock_print, \
         patch('joshu.core.config.get_config_manager') as mock_config_manager:
        # Mock config manager to disable enhanced interactive mode
        config_manager = MagicMock()
        config_manager.get.side_effect = lambda key, default=None: False if key == "enhanced_interactive" else default
        mock_config_manager.return_value = config_manager
        
        start_interactive_mode("test-model")
        # Should print goodbye message
        mock_print.assert_called_with("\n[dim]Goodbye![/dim]")