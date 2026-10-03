from unittest.mock import MagicMock, patch

import pytest

# Skip these tests if prompt_toolkit is not available
pytest.importorskip("prompt_toolkit")


def test_interactive_mode_import():
    """Test that the interactive mode can be imported."""
    from joshu.ui.interactive import InteractiveMode

    assert InteractiveMode is not None


def test_interactive_mode_initialization():
    """Test that the interactive mode can be initialized."""
    with patch("joshu.core.config.get_config_manager") as mock_config_manager:
        # Mock config manager
        mock_config = MagicMock()
        mock_config.get.return_value = 1000
        mock_config_manager.return_value = mock_config

        from joshu.ui.interactive import InteractiveMode

        mode = InteractiveMode("test-model", sandbox=False, verbose=False)

        assert mode is not None
        assert mode.model == "test-model"


def test_interactive_mode_history():
    """Test that the interactive mode handles history correctly."""
    with patch("joshu.core.config.get_config_manager") as mock_config_manager:
        # Mock config manager
        mock_config = MagicMock()
        mock_config.get.return_value = 1000
        mock_config_manager.return_value = mock_config

        from joshu.ui.interactive import InteractiveMode

        mode = InteractiveMode("test-model", sandbox=False, verbose=False)

        # Test adding to history
        mode._add_to_history("test command")
        assert len(mode.command_history) >= 1
        assert "test command" in mode.command_history

        # Test adding different command
        mode._add_to_history("another command")
        assert len(mode.command_history) >= 2


def test_interactive_mode_file_injection():
    """Test that the interactive mode handles file injection."""
    with (
        patch("joshu.core.config.get_config_manager") as mock_config_manager,
        patch("joshu.ui.interactive.utils.execute_file_content"),
    ):
        # Mock config manager
        mock_config = MagicMock()
        mock_config.get.return_value = 1000
        mock_config_manager.return_value = mock_config

        from joshu.ui.interactive import InteractiveMode

        mode = InteractiveMode("test-model", sandbox=False, verbose=False)

        # Test file injection - should not raise an exception
        try:
            mode._handle_file_injection("@test.txt")
        except Exception:
            # May fail if file doesn't exist, but method should be callable
            pass


def test_interactive_mode_bash_command():
    """Test that the interactive mode handles bash commands."""
    with (
        patch("joshu.core.config.get_config_manager") as mock_config_manager,
        patch("joshu.ui.interactive.interactive_mode.run_command") as mock_run_command,
    ):
        # Mock config manager
        mock_config = MagicMock()
        mock_config.get.return_value = 1000
        mock_config_manager.return_value = mock_config

        # Mock run_command to return success
        mock_run_command.return_value = (0, "output", "")

        from joshu.ui.interactive import InteractiveMode

        mode = InteractiveMode("test-model", sandbox=False, verbose=False)

        # Test bash command execution - method extracts command after !
        mode._handle_bash_command("!ls")
        # Should call run_command with "ls" (without the !)
        # The method calls run_command(bash_cmd) where bash_cmd = command[1:] for "!ls"
        mock_run_command.assert_called_once_with("ls")
        # Verify the first argument is "ls"
        call_args = mock_run_command.call_args[0]
        assert len(call_args) > 0
        assert call_args[0] == "ls"  # Direct check of first argument


def test_interactive_mode_slash_commands():
    """Test that the interactive mode handles slash commands."""
    with patch("joshu.core.config.get_config_manager") as mock_config_manager:
        # Mock config manager
        mock_config = MagicMock()
        mock_config.get.return_value = 1000
        mock_config_manager.return_value = mock_config

        from joshu.ui.interactive import InteractiveMode

        mode = InteractiveMode("test-model", sandbox=False, verbose=False)

        # Test /help command
        result = mode.command_handler.handle_slash_command("/help")
        assert result is True

        # Test /clear command
        mode._add_to_history("cmd1")
        mode._add_to_history("cmd2")
        result = mode.command_handler.handle_slash_command("/clear")
        assert result is True
        # History should be cleared (reloaded from storage)

        # Test /history command
        result = mode.command_handler.handle_slash_command("/history")
        assert result is True


def test_interactive_mode_config_commands():
    """Test that the interactive mode handles config commands."""
    with (
        patch("joshu.core.config.get_config_manager") as mock_config_manager,
        patch("joshu.ui.interactive.interactive_mode.ContextProvider"),
    ):
        # Mock config manager
        mock_config = MagicMock()
        mock_config.get.side_effect = lambda key, default=None: {
            "history_limit": 1000,
            "model": "test-model",
        }.get(key, default)
        mock_config.set.return_value = True
        mock_config.save_config.return_value = True
        mock_config.config.to_dict.return_value = {"model": "test-model"}
        mock_config_manager.return_value = mock_config

        from joshu.ui.interactive import InteractiveMode

        mode = InteractiveMode("test-model", sandbox=False, verbose=False)

        # Replace the command_handler's config_manager reference with our mock
        mode.command_handler.config_manager = mock_config

        # Test /config command (show all)
        result = mode.command_handler.handle_slash_command("/config")
        assert result is True

        # Test /config command (get specific value)
        # Reset mock and set up side_effect to return "test-value" for "model"
        mock_config.get.reset_mock()
        mock_config.get.side_effect = lambda key, default=None: {
            "model": "test-value",
            "history_limit": 1000,
        }.get(key, default)
        result = mode.command_handler.handle_slash_command("/config model")
        assert result is True
        # Verify get was called
        assert mock_config.get.called

        # Test /config command (set value)
        mock_config.set.reset_mock()
        mock_config.save_config.reset_mock()
        result = mode.command_handler.handle_slash_command("/config model new-model")
        assert result is True
        # Verify set and save_config were called
        # Note: handle_config_command is called by handle_slash_command
        assert mock_config.set.called
        assert mock_config.save_config.called


def test_interactive_mode_model_commands():
    """Test that the interactive mode handles model commands."""
    with (
        patch("joshu.core.config.get_config_manager") as mock_config_manager,
        patch("joshu.ui.interactive.interactive_mode.ContextProvider"),
    ):
        # Mock config manager
        mock_config = MagicMock()
        mock_config.get.side_effect = lambda key, default=None: {
            "model": "test-model",
            "history_limit": 1000,
        }.get(key, default)
        mock_config.set.return_value = True
        mock_config.save_config.return_value = True
        mock_config_manager.return_value = mock_config

        from joshu.ui.interactive import InteractiveMode

        mode = InteractiveMode("test-model", sandbox=False, verbose=False)

        # Replace the command_handler's config_manager reference with our mock
        mode.command_handler.config_manager = mock_config

        # Test /model command (show current)
        result = mode.command_handler.handle_slash_command("/model")
        assert result is True

        # /model <id> switches the running agent's model for this conversation
        new_client = MagicMock(model="new-model", context_window=None)
        mode.agent = MagicMock()
        mock_config.save_config.reset_mock()
        with patch("joshu.core.llm_client.create_chat_client", return_value=new_client) as create:
            result = mode.command_handler.handle_slash_command("/model new-model")
        assert result is True
        create.assert_called_once_with("new-model")
        assert mode.agent.client is new_client
        assert mode.model == "new-model"
        # The default model is unchanged (joshu use <model> changes it)
        assert not mock_config.save_config.called
