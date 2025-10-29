import pytest
import os
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner

from src.joshu.ui.cli import app

runner = CliRunner()


def test_history_command():
    """Test the history command shows command history."""
    with patch('src.joshu.ui.cli.context_provider') as mock_context_provider:
        # Set up mock context provider with history
        mock_context_provider.conversation_context.messages = [
            {"role": "user", "content": "show disk usage"},
            {"role": "assistant", "content": "Executed: dir"},
            {"role": "user", "content": "list python files"},
            {"role": "assistant", "content": "Executed: dir *.py"}
        ]
        
        # Make sure we don't reinitialize the context provider in the callback
        with patch('src.joshu.ui.cli.ContextProvider') as mock_context_constructor:
            mock_context_constructor.return_value = mock_context_provider
            
            result = runner.invoke(app, ["history"])
            assert result.exit_code == 0
            # Check that the command history is in the output (after the banner)
            assert "show disk usage" in result.output
            assert "list python files" in result.output


def test_history_command_with_limit():
    """Test the history command with limit option."""
    with patch('src.joshu.ui.cli.context_provider') as mock_context_provider:
        # Set up mock context provider with history
        mock_context_provider.conversation_context.messages = [
            {"role": "user", "content": "command 1"},
            {"role": "assistant", "content": "response 1"},
            {"role": "user", "content": "command 2"},
            {"role": "assistant", "content": "response 2"},
            {"role": "user", "content": "command 3"},
            {"role": "assistant", "content": "response 3"}
        ]
        
        # Make sure we don't reinitialize the context provider in the callback
        with patch('src.joshu.ui.cli.ContextProvider') as mock_context_constructor:
            mock_context_constructor.return_value = mock_context_provider
            
            result = runner.invoke(app, ["history", "--limit", "2"])
            assert result.exit_code == 0
            assert "command 2" in result.output
            assert "command 3" in result.output
            # command 1 should not be in the output due to limit


def test_history_command_no_history():
    """Test the history command when no history is available."""
    with patch('src.joshu.ui.cli.context_provider') as mock_context_provider:
        mock_context_provider.conversation_context.messages = []
        
        # Make sure we don't reinitialize the context provider in the callback
        with patch('src.joshu.ui.cli.ContextProvider') as mock_context_constructor:
            mock_context_constructor.return_value = mock_context_provider
            
            result = runner.invoke(app, ["history"])
            assert result.exit_code == 0
            assert "No history available" in result.output


def test_repeat_last_command():
    """Test the repeat-last command repeats the last command."""
    with patch('src.joshu.ui.cli.context_provider') as mock_context_provider, \
         patch('joshu.core.translate.translate_to_command') as mock_translate_to_command, \
         patch('src.joshu.ui.cli.run_command') as mock_run_command, \
         patch('joshu.core.safety.assess_command_safety') as mock_assess_command_safety:
        
        # Set up mocks
        mock_context_provider.conversation_context.messages = [
            {"role": "user", "content": "show disk usage"},
            {"role": "assistant", "content": "Executed: dir"}
        ]
        
        # Mock config manager
        with patch('src.joshu.core.config.get_config_manager') as mock_get_config_manager:
            mock_config_manager = MagicMock()
            mock_config_manager.get.side_effect = lambda key, default=None: {
                "model": "llama-3-8b",
                "sandbox_enabled": True,
                "auto_execute": False
            }.get(key, default)
            mock_get_config_manager.return_value = mock_config_manager
            
            mock_translation = MagicMock()
            mock_translation.command = "dir"
            mock_translation.explanation = "Show directory contents"
            mock_translate_to_command.return_value = mock_translation
            
            mock_run_command.return_value = (0, "Directory contents", "")
            
            mock_safety_report = MagicMock()
            mock_safety_report.safe = True
            mock_assess_command_safety.return_value = mock_safety_report
            
            # Make sure we don't reinitialize the context provider in the callback
            with patch('src.joshu.ui.cli.ContextProvider') as mock_context_constructor:
                mock_context_constructor.return_value = mock_context_provider
                
                # Test with user confirmation
                with patch('typer.confirm', return_value=True):
                    result = runner.invoke(app, ["repeat-last"])
                    assert result.exit_code == 0
                    assert "Repeating last command" in result.output
                    assert "show disk usage" in result.output


def test_repeat_last_command_no_history():
    """Test the repeat-last command when no history is available."""
    with patch('src.joshu.ui.cli.context_provider') as mock_context_provider:
        mock_context_provider.conversation_context.messages = []
        
        # Make sure we don't reinitialize the context provider in the callback
        with patch('src.joshu.ui.cli.ContextProvider') as mock_context_constructor:
            mock_context_constructor.return_value = mock_context_provider
            
            result = runner.invoke(app, ["repeat-last"])
            assert result.exit_code == 1
            assert "No history available" in result.output


def test_repeat_last_command_no_user_command():
    """Test the repeat-last command when no user command is found."""
    with patch('src.joshu.ui.cli.context_provider') as mock_context_provider:
        # Only assistant messages, no user commands
        mock_context_provider.conversation_context.messages = [
            {"role": "assistant", "content": "response 1"},
            {"role": "assistant", "content": "response 2"}
        ]
        
        # Make sure we don't reinitialize the context provider in the callback
        with patch('src.joshu.ui.cli.ContextProvider') as mock_context_constructor:
            mock_context_constructor.return_value = mock_context_provider
            
            result = runner.invoke(app, ["repeat-last"])
            assert result.exit_code == 1
            assert "No previous command found" in result.output


def test_explain_last_command():
    """Test the explain-last command shows explanation of last command."""
    with patch('src.joshu.ui.cli.context_provider') as mock_context_provider:
        # Set up mock context provider with history
        mock_context_provider.conversation_context.messages = [
            {"role": "user", "content": "show disk usage"},
            {"role": "assistant", "content": "This command shows the contents of the current directory using the dir command."}
        ]
        
        # Make sure we don't reinitialize the context provider in the callback
        with patch('src.joshu.ui.cli.ContextProvider') as mock_context_constructor:
            mock_context_constructor.return_value = mock_context_provider
            
            result = runner.invoke(app, ["explain-last"])
            assert result.exit_code == 0
            assert "Last Command" in result.output
            assert "show disk usage" in result.output
            assert "This command shows the contents" in result.output


def test_explain_last_command_no_history():
    """Test the explain-last command when no history is available."""
    with patch('src.joshu.ui.cli.context_provider') as mock_context_provider:
        mock_context_provider.conversation_context.messages = []
        
        # Make sure we don't reinitialize the context provider in the callback
        with patch('src.joshu.ui.cli.ContextProvider') as mock_context_constructor:
            mock_context_constructor.return_value = mock_context_provider
            
            result = runner.invoke(app, ["explain-last"])
            assert result.exit_code == 1
            assert "No history available" in result.output


def test_explain_last_command_incomplete_history():
    """Test the explain-last command with incomplete history."""
    with patch('src.joshu.ui.cli.context_provider') as mock_context_provider:
        # Only user command, no assistant response
        mock_context_provider.conversation_context.messages = [
            {"role": "user", "content": "show disk usage"}
        ]
        
        # Make sure we don't reinitialize the context provider in the callback
        with patch('src.joshu.ui.cli.ContextProvider') as mock_context_constructor:
            mock_context_constructor.return_value = mock_context_provider
            
            result = runner.invoke(app, ["explain-last"])
            assert result.exit_code == 1
            assert "No complete command history found" in result.output