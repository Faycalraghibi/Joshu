"""
Tests for IDE Server.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from joshu.ide.server import DiffProposal, IdeContext, IDEServer, ServerConfig


class TestIdeContext:
    """Tests for IdeContext dataclass."""

    def test_default_values(self):
        """Should have sensible defaults."""
        ctx = IdeContext()
        assert ctx.workspace_path == ""
        assert ctx.recent_files == []
        assert ctx.active_file is None
        assert ctx.selected_text == ""

    def test_to_dict(self):
        """Should serialize to dictionary."""
        ctx = IdeContext(
            workspace_path="/test/workspace",
            active_file="/test/file.py",
            cursor_line=10,
            cursor_column=5,
            selected_text="hello",
        )

        data = ctx.to_dict()

        assert data["workspace_path"] == "/test/workspace"
        assert data["active_file"] == "/test/file.py"
        assert data["cursor_position"]["line"] == 10
        assert data["cursor_position"]["column"] == 5
        assert data["selected_text"] == "hello"


class TestServerConfig:
    """Tests for ServerConfig."""

    def test_default_host(self):
        """Should default to localhost."""
        config = ServerConfig()
        assert config.host == "127.0.0.1"

    def test_default_port_is_zero(self):
        """Should default to port 0 for dynamic assignment."""
        config = ServerConfig()
        assert config.port == 0

    def test_generates_token(self):
        """Should auto-generate a token."""
        config = ServerConfig()
        assert config.token is not None
        assert len(config.token) > 20


class TestIDEServer:
    """Tests for IDEServer."""

    def test_initialization(self):
        """Should initialize with default config."""
        server = IDEServer()
        assert server.config is not None
        assert server.is_running is False
        assert server.port == 0

    def test_custom_config(self):
        """Should accept custom config."""
        config = ServerConfig(port=8080, workspace_path="/custom")
        server = IDEServer(config=config)
        assert server.config.port == 8080
        assert server.config.workspace_path == "/custom"

    def test_context_update(self):
        """Should update context from data."""
        server = IDEServer()

        server._update_context(
            {
                "workspace_path": "/test",
                "active_file": "main.py",
                "cursor_position": {"line": 5, "column": 10},
                "selected_text": "def foo():",
            }
        )

        assert server.context.workspace_path == "/test"
        assert server.context.active_file == "main.py"
        assert server.context.cursor_line == 5
        assert server.context.cursor_column == 10
        assert server.context.selected_text == "def foo():"

    def test_context_limits_recent_files(self):
        """Should limit recent files to 10."""
        server = IDEServer()

        server._update_context({"recent_files": [{"path": f"file{i}.py"} for i in range(20)]})

        assert len(server.context.recent_files) == 10

    def test_context_limits_selected_text(self):
        """Should limit selected text to 16KB."""
        server = IDEServer()
        long_text = "x" * 20000

        server._update_context({"selected_text": long_text})

        assert len(server.context.selected_text) == 16384

    def test_event_callbacks(self):
        """Should call callbacks on events."""
        server = IDEServer()
        callback = MagicMock()
        server.on("context_update", callback)

        server._update_context({"workspace_path": "/test"})

        callback.assert_called_once()

    def test_accept_diff(self):
        """Should update proposal status on accept."""
        server = IDEServer()
        proposal = DiffProposal(
            proposal_id="test123",
            file_path="/test.py",
            original_content="old",
            proposed_content="new",
        )
        server.proposals["test123"] = proposal

        server._accept_diff("test123")

        assert server.proposals["test123"].status == "accepted"

    def test_reject_diff(self):
        """Should update proposal status on reject."""
        server = IDEServer()
        proposal = DiffProposal(
            proposal_id="test123",
            file_path="/test.py",
            original_content="old",
            proposed_content="new",
        )
        server.proposals["test123"] = proposal

        server._reject_diff("test123")

        assert server.proposals["test123"].status == "rejected"

    def test_write_server_info(self):
        """Should write server info file."""
        server = IDEServer()
        server._port = 12345
        server.config.workspace_path = "/test"

        with patch.object(Path, "write_text") as mock_write:
            server._write_server_info()
            mock_write.assert_called_once()

            # Verify JSON content
            call_args = mock_write.call_args[0][0]
            data = json.loads(call_args)
            assert data["port"] == 12345
            assert data["workspace_path"] == "/test"
