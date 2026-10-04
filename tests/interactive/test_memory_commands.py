"""Tests for semantic memory CLI commands."""

from unittest.mock import MagicMock, patch

import pytest

from joshu.core.storage.semantic_memory import SemanticMemoryEntry
from joshu.ui.interactive.commands import CommandHandler


@pytest.fixture
def mock_interactive_mode():
    """Create a mock interactive mode."""
    mock = MagicMock()
    mock._show_message = MagicMock()

    # Mock context provider with semantic memory
    mock.context_provider = MagicMock()
    mock.context_provider.semantic_memory = MagicMock()
    mock.context_provider.semantic_memory.enabled = True
    mock.context_provider.semantic_memory.count = MagicMock(return_value=5)

    # Mock config manager
    mock.config_manager = MagicMock()
    mock.config_manager.config = MagicMock()
    mock.config_manager.config.semantic_memory_similarity_threshold = 0.3
    mock.config_manager.config.semantic_memory_max_results = 5
    mock.config_manager.config.semantic_memory_min_content_length = 10

    return mock


@pytest.fixture
def command_handler(mock_interactive_mode):
    """Create a CommandHandler instance."""
    return CommandHandler(mock_interactive_mode)


class TestMemoryCommands:
    """Test semantic memory CLI commands."""

    def test_memory_help(self, command_handler, mock_interactive_mode):
        """/memory lists saved memories and the semantic memory subcommands."""
        result = command_handler.handle_memory_command("/memory")

        assert result is True
        calls = mock_interactive_mode._show_message.call_args_list
        shown = "\n".join(call[0][0] for call in calls)

        assert "Project memory" in shown and "User memory" in shown
        assert "/memory forget" in shown
        assert "/memory status | search <q> | clear" in shown

    def test_memory_status_enabled(self, command_handler, mock_interactive_mode):
        """Test /memory status when semantic memory is enabled."""
        result = command_handler.handle_memory_command("/memory status")

        assert result is True

        # Should show status information
        calls = mock_interactive_mode._show_message.call_args_list
        messages = [call[0][0] for call in calls]

        assert any("Semantic Memory Status" in msg for msg in messages)
        assert any("Enabled" in msg for msg in messages)
        assert any("Total memories: 5" in msg for msg in messages)
        assert any("ChromaDB" in msg for msg in messages)

    def test_memory_status_disabled(self, command_handler, mock_interactive_mode):
        """Test /memory status when semantic memory is disabled."""
        mock_interactive_mode.context_provider.semantic_memory.enabled = False

        result = command_handler.handle_memory_command("/memory status")

        assert result is True

        calls = mock_interactive_mode._show_message.call_args_list
        messages = [call[0][0] for call in calls]

        assert any("disabled" in msg.lower() for msg in messages)
        assert any("pip install" in msg for msg in messages)

    def test_memory_search_no_query(self, command_handler, mock_interactive_mode):
        """Test /memory search without query shows error."""
        result = command_handler.handle_memory_command("/memory search")

        assert result is True

        calls = mock_interactive_mode._show_message.call_args_list
        messages = [call[0][0] for call in calls]

        assert any("Usage:" in msg for msg in messages)

    def test_memory_search_with_results(self, command_handler, mock_interactive_mode):
        """Test /memory search with results."""
        # Mock search results
        mock_results = [
            SemanticMemoryEntry(
                id="entry-1",
                content="I prefer using Python for data science",
                role="user",
                session_id="session-123",
                timestamp=1700000000.0,
            ),
            SemanticMemoryEntry(
                id="entry-2",
                content="Python is great for machine learning",
                role="assistant",
                session_id="session-123",
                timestamp=1700000100.0,
            ),
        ]
        mock_interactive_mode.context_provider.semantic_memory.search = MagicMock(
            return_value=mock_results
        )

        result = command_handler.handle_memory_command("/memory search python")

        assert result is True

        # Verify search was called
        mock_interactive_mode.context_provider.semantic_memory.search.assert_called_once()

        # Check output
        calls = mock_interactive_mode._show_message.call_args_list
        messages = [call[0][0] for call in calls]

        assert any("Found 2 relevant memories" in msg for msg in messages)
        assert any("Python" in msg for msg in messages)

    def test_memory_search_no_results(self, command_handler, mock_interactive_mode):
        """Test /memory search with no results."""
        mock_interactive_mode.context_provider.semantic_memory.search = MagicMock(return_value=[])

        result = command_handler.handle_memory_command("/memory search irrelevant")

        assert result is True

        calls = mock_interactive_mode._show_message.call_args_list
        messages = [call[0][0] for call in calls]

        assert any("No relevant memories found" in msg for msg in messages)

    def test_memory_clear_success(self, command_handler, mock_interactive_mode):
        """Test /memory clear successfully clears memories."""
        mock_interactive_mode.context_provider.semantic_memory.count = MagicMock(return_value=10)
        mock_interactive_mode.context_provider.semantic_memory.clear = MagicMock(return_value=True)

        result = command_handler.handle_memory_command("/memory clear")

        assert result is True

        # Verify clear was called
        mock_interactive_mode.context_provider.semantic_memory.clear.assert_called_once()

        # Check output
        calls = mock_interactive_mode._show_message.call_args_list
        messages = [call[0][0] for call in calls]

        assert any("Cleared 10" in msg for msg in messages)

    def test_memory_clear_empty(self, command_handler, mock_interactive_mode):
        """Test /memory clear when no memories exist."""
        mock_interactive_mode.context_provider.semantic_memory.count = MagicMock(return_value=0)

        result = command_handler.handle_memory_command("/memory clear")

        assert result is True

        calls = mock_interactive_mode._show_message.call_args_list
        messages = [call[0][0] for call in calls]

        assert any("No memories to clear" in msg for msg in messages)

    def test_memory_clear_failure(self, command_handler, mock_interactive_mode):
        """Test /memory clear handles failures."""
        mock_interactive_mode.context_provider.semantic_memory.count = MagicMock(return_value=5)
        mock_interactive_mode.context_provider.semantic_memory.clear = MagicMock(return_value=False)

        result = command_handler.handle_memory_command("/memory clear")

        assert result is True

        calls = mock_interactive_mode._show_message.call_args_list
        messages = [call[0][0] for call in calls]

        assert any("Failed to clear" in msg for msg in messages)

    def test_memory_unknown_subcommand(self, command_handler, mock_interactive_mode):
        """Test /memory with unknown subcommand."""
        result = command_handler.handle_memory_command("/memory invalid")

        assert result is True

        calls = mock_interactive_mode._show_message.call_args_list
        messages = [call[0][0] for call in calls]

        assert any("Unknown memory command" in msg for msg in messages)

    def test_memory_no_context_provider(self, mock_interactive_mode):
        """Test memory commands when context provider is not available."""
        mock_interactive_mode.context_provider = None
        handler = CommandHandler(mock_interactive_mode)

        result = handler.handle_memory_command("/memory status")

        assert result is True

        calls = mock_interactive_mode._show_message.call_args_list
        messages = [call[0][0] for call in calls]

        assert any("Context provider not available" in msg for msg in messages)

    def test_memory_uses_config_values(self, command_handler, mock_interactive_mode):
        """Test that memory search uses configuration values."""
        # Set custom config values
        mock_interactive_mode.config_manager.config.semantic_memory_similarity_threshold = 0.5
        mock_interactive_mode.config_manager.config.semantic_memory_max_results = 10

        mock_interactive_mode.context_provider.semantic_memory.search = MagicMock(return_value=[])

        command_handler.handle_memory_command("/memory search test")

        # Verify search was called with config values
        call_args = mock_interactive_mode.context_provider.semantic_memory.search.call_args
        assert call_args[1]["limit"] == 10
        assert call_args[1]["min_score"] == 0.5


class TestMemoryCommandIntegration:
    """Test integration of memory commands with slash command handler."""

    def test_slash_handler_routes_memory_commands(self, command_handler, mock_interactive_mode):
        """Test that /memory commands are routed correctly."""
        with patch.object(
            command_handler, "handle_memory_command", return_value=True
        ) as mock_handler:
            result = command_handler.handle_slash_command("/memory status")

            assert result is True
            mock_handler.assert_called_once_with("/memory status")
