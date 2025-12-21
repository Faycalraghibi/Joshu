"""
Unit tests for command processing system.

Run with: pytest tests/commands/test_commands.py -v
"""

from pathlib import Path

import pytest

from joshu.commands import (
    CommandActionType,
    ErrorActionReturn,
    LoadHistoryActionReturn,
    MessageActionReturn,
    NoOpActionReturn,
    RestoreToolCallData,
    SubmitPromptActionReturn,
    ToolActionReturn,
    list_extensions,
    perform_init,
    perform_restore,
)


class TestCommandActionTypes:
    """Test CommandActionReturn types."""

    def test_tool_action_return(self):
        """Test ToolActionReturn."""
        action = ToolActionReturn(
            tool_name="web_search",
            tool_arguments={"query": "test"},
            requires_approval=True,
        )
        assert action.action_type == CommandActionType.TOOL_CALL
        assert action.tool_name == "web_search"

        data = action.to_dict()
        assert data["tool_name"] == "web_search"

    def test_message_action_return(self):
        """Test MessageActionReturn."""
        action = MessageActionReturn(
            message="Hello, world!",
            message_type="info",
        )
        assert action.action_type == CommandActionType.MESSAGE
        assert action.message == "Hello, world!"

    def test_load_history_action_return(self):
        """Test LoadHistoryActionReturn."""
        history = [{"role": "user", "content": "Hi"}]
        action = LoadHistoryActionReturn(
            history=history,
            replace_existing=True,
        )
        assert action.action_type == CommandActionType.LOAD_HISTORY
        assert len(action.history) == 1

    def test_submit_prompt_action_return(self):
        """Test SubmitPromptActionReturn."""
        action = SubmitPromptActionReturn(
            prompt="Generate code",
            system_instruction="You are a coder",
        )
        assert action.action_type == CommandActionType.SUBMIT_PROMPT
        assert action.include_context is True

    def test_error_action_return(self):
        """Test ErrorActionReturn."""
        action = ErrorActionReturn(
            error_message="Something went wrong",
            error_code="ERR_001",
            recoverable=False,
        )
        assert action.action_type == CommandActionType.ERROR
        assert action.recoverable is False

    def test_noop_action_return(self):
        """Test NoOpActionReturn."""
        action = NoOpActionReturn(reason="Nothing to do")
        assert action.action_type == CommandActionType.NO_OP


class TestPerformInit:
    """Test perform_init command."""

    def test_init_when_gemini_md_exists(self, tmp_path: Path):
        """Test init when GEMINI.md already exists."""
        gemini_path = tmp_path / "GEMINI.md"
        gemini_path.write_text("# Project")

        result = perform_init(tmp_path)

        assert isinstance(result, NoOpActionReturn)
        assert "already exists" in result.reason

    def test_init_when_gemini_md_not_exists(self, tmp_path: Path):
        """Test init when GEMINI.md doesn't exist."""
        result = perform_init(tmp_path)

        assert isinstance(result, SubmitPromptActionReturn)
        assert "GEMINI.md" in result.prompt
        assert result.system_instruction is not None

    def test_init_with_explicit_exists_flag(self, tmp_path: Path):
        """Test init with explicit existence flag."""
        # Override to say it exists even if it doesn't
        result = perform_init(tmp_path, does_gemini_md_exist=True)
        assert isinstance(result, NoOpActionReturn)

        # Override to say it doesn't exist
        result = perform_init(tmp_path, does_gemini_md_exist=False)
        assert isinstance(result, SubmitPromptActionReturn)


class TestPerformRestore:
    """Test perform_restore command."""

    def test_restore_history_only(self):
        """Test restoration with history only."""
        data = RestoreToolCallData(
            checkpoint_tag="checkpoint_1",
            history=[{"role": "user", "content": "Hello"}],
            client_history=[],
        )

        results = list(perform_restore(data))

        # Should have: start message, load history, success message
        assert len(results) >= 2
        assert any(isinstance(r, MessageActionReturn) for r in results)
        assert any(isinstance(r, LoadHistoryActionReturn) for r in results)

    def test_restore_with_git_commit(self, tmp_path: Path):
        """Test restoration with Git commit."""
        from joshu.commands import GitService

        git_service = GitService(project_root=tmp_path)
        data = RestoreToolCallData(
            checkpoint_tag="checkpoint_2",
            history=[],
            client_history=[],
            commit_hash="abc123",
        )

        results = list(perform_restore(data, git_service))

        # Should have messages about Git restoration
        assert len(results) >= 2

    def test_restore_empty_history(self):
        """Test restoration with empty history."""
        data = RestoreToolCallData(
            checkpoint_tag="empty_checkpoint",
            history=[],
            client_history=[],
        )

        results = list(perform_restore(data))

        # Should still have start and success messages
        assert len(results) >= 2
        # No LoadHistoryActionReturn for empty history
        assert not any(isinstance(r, LoadHistoryActionReturn) for r in results)


class TestListExtensions:
    """Test list_extensions command."""

    def test_list_with_extensions(self):
        """Test listing configured extensions."""
        config = {"extensions": ["mcp-server", "file-browser", "git-tools"]}
        result = list_extensions(config)

        assert isinstance(result, MessageActionReturn)
        assert "mcp-server" in result.message
        assert len(result.metadata["extensions"]) == 3

    def test_list_no_extensions(self):
        """Test listing when no extensions configured."""
        config = {}
        result = list_extensions(config)

        assert isinstance(result, MessageActionReturn)
        assert "No extensions" in result.message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
