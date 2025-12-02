"""
Tests for interactive mode /search command.
"""

from unittest.mock import Mock, patch

import pytest


class TestInteractiveSearchCommand:
    """Test the /search slash command in interactive mode."""

    def test_search_slash_command_basic(self):
        """Test basic /search command."""
        from joshu.ui.interactive.commands import CommandHandler

        # Create mock interactive mode
        mock_interactive = Mock()
        mock_interactive.context_provider = Mock()
        mock_interactive.config_manager = Mock()

        handler = CommandHandler(mock_interactive)

        with patch("joshu.ui.cli_handlers.search_handler.handle_search_command") as mock_search:
            result = handler.handle_slash_command("/search Python programming")

            # Should call handle_search_command with the query
            mock_search.assert_called_once_with("Python programming", max_results=None)
            assert result is True

    def test_search_slash_command_without_query(self):
        """Test /search command without query."""
        from joshu.ui.interactive.commands import CommandHandler

        mock_interactive = Mock()
        mock_interactive.context_provider = Mock()
        mock_interactive.config_manager = Mock()

        handler = CommandHandler(mock_interactive)

        with patch("joshu.ui.cli_handlers.search_handler.handle_search_command") as mock_search:
            result = handler.handle_slash_command("/search")

            # Should not call search handler, should show usage message
            mock_search.assert_not_called()

            # Should call _show_message with usage info
            assert mock_interactive._show_message.called
            message_calls = [str(call) for call in mock_interactive._show_message.call_args_list]
            usage_shown = any("usage" in call.lower() for call in message_calls)
            assert usage_shown

            assert result is True

    def test_search_slash_command_multiword_query(self):
        """Test /search with multi-word query."""
        from joshu.ui.interactive.commands import CommandHandler

        mock_interactive = Mock()
        mock_interactive.context_provider = Mock()
        mock_interactive.config_manager = Mock()

        handler = CommandHandler(mock_interactive)

        with patch("joshu.ui.cli_handlers.search_handler.handle_search_command") as mock_search:
            result = handler.handle_slash_command("/search machine learning best practices 2024")

            # Should join all words into single query
            mock_search.assert_called_once_with(
                "machine learning best practices 2024", max_results=None
            )
            assert result is True

    def test_search_in_help_text(self):
        """Test that /search is included in help text."""
        from joshu.ui.interactive.commands import CommandHandler

        mock_interactive = Mock()
        mock_interactive.context_provider = Mock()
        mock_interactive.config_manager = Mock()
        mock_interactive.interaction_mode = "agent"

        handler = CommandHandler(mock_interactive)

        # Call show_help
        handler.show_help()

        # Check that help text was shown and includes /search
        assert mock_interactive._show_message.called
        messages = [str(call) for call in mock_interactive._show_message.call_args_list]

        # Join all messages to check full help text
        full_help = " ".join(messages).lower()
        assert "/search" in full_help or "search <query>" in full_help


class TestInteractiveModeIntegration:
    """Test full interactive mode integration with search."""

    def test_handle_user_input_with_search_command(self):
        """Test that user input starting with / triggers slash command handler."""
        from joshu.ui.interactive.interactive_mode import InteractiveMode

        with patch("joshu.ui.interactive.interactive_mode.get_config_manager") as mock_config:
            mock_config_inst = Mock()
            mock_config_inst.get.return_value = 1000
            mock_config.return_value = mock_config_inst

            with patch("joshu.ui.interactive.interactive_mode.ContextProvider"):
                with patch("joshu.ui.interactive.interactive_mode.JsonHistory"):
                    with patch("joshu.core.translate.establish_connection"):
                        with patch(
                            "joshu.ui.interactive.interactive_mode.PROMPT_TOOLKIT_AVAILABLE", False
                        ):
                            mode = InteractiveMode("test-model", sandbox=True)

                            # Mock the command handler
                            mode.command_handler = Mock()
                            mode.command_handler.handle_slash_command.return_value = True

                            # Test that slash commands are dispatched correctly
                            result = mode._handle_user_input("/search test query")

                            # Should call the command handler
                            mode.command_handler.handle_slash_command.assert_called_once_with(
                                "/search test query"
                            )
                            assert result is True

    def test_search_command_in_interactive_session_flow(self):
        """Test /search command in a simulated interactive session."""
        from joshu.ui.interactive.commands import CommandHandler

        mock_interactive = Mock()
        mock_interactive.context_provider = Mock()
        mock_interactive.config_manager = Mock()

        # Mock prompt_history for /history command
        mock_interactive.prompt_history = Mock()
        mock_interactive.prompt_history.load_history_strings.return_value = []

        handler = CommandHandler(mock_interactive)

        # Simulate a sequence of commands including search
        commands = ["/help", "/search Python", "/history", "/search JavaScript frameworks"]

        with patch("joshu.ui.cli_handlers.search_handler.handle_search_command") as mock_search:
            for cmd in commands:
                result = handler.handle_slash_command(cmd)
                assert result is True  # All should return True (continue session)

            # /search should have been called twice
            assert mock_search.call_count == 2

            # Check the queries
            calls = mock_search.call_args_list
            assert calls[0][0][0] == "Python"
            assert calls[1][0][0] == "JavaScript frameworks"


class TestSearchCommandEdgeCases:
    """Test edge cases for search command in interactive mode."""

    def test_search_with_special_characters(self):
        """Test search with special characters in query."""
        from joshu.ui.interactive.commands import CommandHandler

        mock_interactive = Mock()
        mock_interactive.context_provider = Mock()
        mock_interactive.config_manager = Mock()

        handler = CommandHandler(mock_interactive)

        with patch("joshu.ui.cli_handlers.search_handler.handle_search_command") as mock_search:
            result = handler.handle_slash_command('/search Python "best practices" 2024')

            # Should preserve quotes and special characters
            mock_search.assert_called_once_with('Python "best practices" 2024', max_results=None)
            assert result is True

    def test_search_with_urls(self):
        """Test search with URLs in query."""
        from joshu.ui.interactive.commands import CommandHandler

        mock_interactive = Mock()
        mock_interactive.context_provider = Mock()
        mock_interactive.config_manager = Mock()

        handler = CommandHandler(mock_interactive)

        with patch("joshu.ui.cli_handlers.search_handler.handle_search_command") as mock_search:
            result = handler.handle_slash_command("/search https://example.com documentation")

            # Should handle URLs in query
            mock_search.assert_called_once_with(
                "https://example.com documentation", max_results=None
            )
            assert result is True

    def test_search_with_only_whitespace_after_command(self):
        """Test /search command with only whitespace."""
        from joshu.ui.interactive.commands import CommandHandler

        mock_interactive = Mock()
        mock_interactive.context_provider = Mock()
        mock_interactive.config_manager = Mock()

        handler = CommandHandler(mock_interactive)

        with patch("joshu.ui.cli_handlers.search_handler.handle_search_command") as mock_search:
            result = handler.handle_slash_command("/search     ")

            # Should show usage message, not call search
            mock_search.assert_not_called()
            assert mock_interactive._show_message.called
            assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
