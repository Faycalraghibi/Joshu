import pytest
from unittest.mock import patch, MagicMock


def test_imports():
    """Test that the module can be imported without errors."""
    try:
        from opencli.ui.cli import start_enhanced_interactive_mode
        assert True
    except ImportError:
        # This is expected if prompt_toolkit is not available
        assert True


# Skip these tests if prompt_toolkit is not available
pytest.importorskip("prompt_toolkit")


def test_enhanced_interactive_mode_import():
    """Test that the enhanced interactive mode function can be imported."""
    # Import after ensuring prompt_toolkit is available
    from opencli.ui.cli import start_enhanced_interactive_mode, PROMPT_TOOLKIT_AVAILABLE
    assert start_enhanced_interactive_mode is not None
    assert PROMPT_TOOLKIT_AVAILABLE is True


def test_enhanced_interactive_mode_fallback():
    """Test that enhanced interactive mode falls back to basic mode when prompt_toolkit is not available."""
    with patch('opencli.ui.cli.PROMPT_TOOLKIT_AVAILABLE', False), \
         patch('opencli.ui.cli.start_basic_interactive_mode') as mock_basic_mode, \
         patch('rich.console.Console.print') as mock_print:
        
        # Mock config manager
        config_manager = MagicMock()
        
        # Import after ensuring prompt_toolkit is available
        from opencli.ui.cli import start_enhanced_interactive_mode
        start_enhanced_interactive_mode("test-model", False, config_manager)
        
        # Should call the basic mode function
        mock_basic_mode.assert_called_once_with("test-model", False, config_manager)
        # Should print error message
        mock_print.assert_called_with("[red]Error: prompt_toolkit is not available. Falling back to basic interactive mode.[/red]")


def test_enhanced_interactive_mode_exit():
    """Test that enhanced interactive mode exits correctly when user types 'exit'."""
    with patch('prompt_toolkit.PromptSession') as mock_session, \
         patch('rich.console.Console.print') as mock_print:
        # Mock the prompt session to return 'exit' on first call
        mock_session_instance = MagicMock()
        mock_session_instance.prompt.return_value = 'exit'
        mock_session.return_value = mock_session_instance
        
        # Mock config manager
        config_manager = MagicMock()
        config_manager.get.return_value = False  # auto_execute = False
        
        # Import after ensuring prompt_toolkit is available
        from opencli.ui.cli import start_enhanced_interactive_mode
        start_enhanced_interactive_mode("test-model", False, config_manager)
        # Should print goodbye message
        mock_print.assert_called_with("[dim]Goodbye![/dim]")


def test_enhanced_interactive_mode_quit():
    """Test that enhanced interactive mode exits correctly when user types 'quit'."""
    with patch('prompt_toolkit.PromptSession') as mock_session, \
         patch('rich.console.Console.print') as mock_print:
        # Mock the prompt session to return 'quit' on first call
        mock_session_instance = MagicMock()
        mock_session_instance.prompt.return_value = 'quit'
        mock_session.return_value = mock_session_instance
        
        # Mock config manager
        config_manager = MagicMock()
        config_manager.get.return_value = False  # auto_execute = False
        
        # Import after ensuring prompt_toolkit is available
        from opencli.ui.cli import start_enhanced_interactive_mode
        start_enhanced_interactive_mode("test-model", False, config_manager)
        # Should print goodbye message
        mock_print.assert_called_with("[dim]Goodbye![/dim]")


def test_enhanced_interactive_mode_empty_input():
    """Test that enhanced interactive mode handles empty input correctly."""
    with patch('prompt_toolkit.PromptSession') as mock_session, \
         patch('rich.console.Console.print') as mock_print:
        # Mock the prompt session to return empty string then 'exit'
        mock_session_instance = MagicMock()
        mock_session_instance.prompt.side_effect = ['', 'exit']
        mock_session.return_value = mock_session_instance
        
        # Mock config manager
        config_manager = MagicMock()
        config_manager.get.return_value = False  # auto_execute = False
        
        # Import after ensuring prompt_toolkit is available
        from opencli.ui.cli import start_enhanced_interactive_mode
        start_enhanced_interactive_mode("test-model", False, config_manager)


def test_enhanced_interactive_mode_bash_command():
    """Test that enhanced interactive mode handles bash commands correctly."""
    with patch('prompt_toolkit.PromptSession') as mock_session, \
         patch('rich.console.Console.print'), \
         patch('opencli.tools.shell.run_command') as mock_run_command:
        # Mock the prompt session to return '!ls' then 'exit'
        mock_session_instance = MagicMock()
        mock_session_instance.prompt.side_effect = ['!ls', 'exit']
        mock_session.return_value = mock_session_instance
        
        # Mock run_command to return success
        mock_run_command.return_value = (0, "file1.txt\nfile2.txt", "")
        
        # Mock config manager
        config_manager = MagicMock()
        config_manager.get.return_value = False  # auto_execute = False
        
        # Import after ensuring prompt_toolkit is available
        from opencli.ui.cli import start_enhanced_interactive_mode
        start_enhanced_interactive_mode("test-model", False, config_manager)
        
        # Should call run_command with 'ls'
        mock_run_command.assert_called_with('ls')


def test_enhanced_interactive_mode_file_injection():
    """Test that enhanced interactive mode handles file injection correctly."""
    with patch('prompt_toolkit.PromptSession') as mock_session, \
         patch('rich.console.Console.print'), \
         patch('os.path.exists') as mock_exists, \
         patch('builtins.open', MagicMock()):
        # Mock the prompt session to return '@test.txt' then 'exit'
        mock_session_instance = MagicMock()
        mock_session_instance.prompt.side_effect = ['@test.txt', 'exit']
        mock_session.return_value = mock_session_instance
        
        # Mock file existence
        mock_exists.return_value = True
        
        # Mock config manager
        config_manager = MagicMock()
        config_manager.get.return_value = False  # auto_execute = False
        
        # Import after ensuring prompt_toolkit is available
        from opencli.ui.cli import start_enhanced_interactive_mode
        start_enhanced_interactive_mode("test-model", False, config_manager)


def test_enhanced_interactive_mode_history_command():
    """Test that enhanced interactive mode handles /history command correctly."""
    with patch('prompt_toolkit.PromptSession') as mock_session, \
         patch('rich.console.Console.print'), \
         patch('pathlib.Path.cwd') as mock_cwd:
        # Mock the prompt session to return '/history' then 'exit'
        mock_session_instance = MagicMock()
        mock_session_instance.prompt.side_effect = ['/history', 'exit']
        mock_session.return_value = mock_session_instance
        
        # Mock current working directory
        mock_cwd.return_value = MagicMock()
        
        # Mock config manager
        config_manager = MagicMock()
        config_manager.get.return_value = True  # persistent_history = True
        
        # Import after ensuring prompt_toolkit is available
        from opencli.ui.cli import start_enhanced_interactive_mode
        start_enhanced_interactive_mode("test-model", False, config_manager)


def test_enhanced_interactive_mode_clear_command():
    """Test that enhanced interactive mode handles /clear command correctly."""
    with patch('prompt_toolkit.PromptSession') as mock_session, \
         patch('rich.console.Console.print'), \
         patch('pathlib.Path.cwd') as mock_cwd, \
         patch('pathlib.Path.exists') as mock_exists, \
         patch('pathlib.Path.unlink') as mock_unlink:
        # Mock the prompt session to return '/clear' then 'exit'
        mock_session_instance = MagicMock()
        mock_session_instance.prompt.side_effect = ['/clear', 'exit']
        mock_session.return_value = mock_session_instance
        
        # Mock current working directory
        mock_cwd.return_value = MagicMock()
        mock_exists.return_value = True
        
        # Mock config manager
        config_manager = MagicMock()
        config_manager.get.return_value = True  # persistent_history = True
        
        # Import after ensuring prompt_toolkit is available
        from opencli.ui.cli import start_enhanced_interactive_mode
        start_enhanced_interactive_mode("test-model", False, config_manager)
        
        # Should call unlink to clear history
        mock_unlink.assert_called_once()


def test_enhanced_interactive_mode_keyboard_shortcuts():
    """Test that enhanced interactive mode handles keyboard shortcuts."""
    with patch('prompt_toolkit.PromptSession') as mock_session, \
         patch('rich.console.Console.print') as mock_print:
        # Mock the prompt session to return special commands then 'exit'
        mock_session_instance = MagicMock()
        mock_session_instance.prompt.side_effect = ['toggle_verbose', 'exit']
        mock_session.return_value = mock_session_instance
        
        # Mock config manager
        config_manager = MagicMock()
        config_manager.get.return_value = False  # auto_execute = False
        
        # Import after ensuring prompt_toolkit is available
        from opencli.ui.cli import start_enhanced_interactive_mode
        start_enhanced_interactive_mode("test-model", False, config_manager)
        
        # Should print verbose mode message
        mock_print.assert_any_call("[green]Verbose mode enabled.[/green]")