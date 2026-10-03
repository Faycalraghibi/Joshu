"""Tests for loading MCP tools at startup (all entry points)."""

from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from joshu.core.config import get_config_manager
from joshu.core.llm_client import AssistantTurn
from joshu.mcp import startup


@pytest.fixture(autouse=True)
def fresh_loader():
    startup.reset()
    yield
    startup.reset()


def test_disabled_mcp_loads_nothing():
    get_config_manager().set("mcp_enabled", False)
    with patch("joshu.ui.cli_handlers.mcp_handler.load_mcp_servers_from_config") as load:
        assert startup.load_mcp_tools() == 0
    load.assert_not_called()


def test_enabled_mcp_registers_tools_once_and_reports():
    get_config_manager().set("mcp_enabled", True)
    lines = []
    with (
        patch("joshu.ui.cli_handlers.mcp_handler.load_mcp_servers_from_config") as load,
        patch("joshu.mcp.discovery.register_mcp_tools_with_joshu", new=AsyncMock(return_value=3)),
    ):
        assert startup.load_mcp_tools(report=lines.append) == 3
        assert startup.load_mcp_tools(report=lines.append) == 0  # already loaded

    load.assert_called_once()
    assert lines == ["[MCP] Registered 3 tools from MCP servers"]


def test_discovery_failure_does_not_break_startup():
    get_config_manager().set("mcp_enabled", True)
    with (
        patch("joshu.ui.cli_handlers.mcp_handler.load_mcp_servers_from_config"),
        patch(
            "joshu.mcp.discovery.register_mcp_tools_with_joshu",
            new=AsyncMock(side_effect=RuntimeError("server crashed")),
        ),
    ):
        assert startup.load_mcp_tools() == 0


class _FakeClient:
    model = "fake"

    def complete(self, messages, tools=None, **kwargs):
        return AssistantTurn(content="ok")


def test_joshu_run_loads_mcp_tools(tmp_path, monkeypatch):
    from joshu.ui.cli import app

    monkeypatch.chdir(tmp_path)
    with (
        patch("joshu.mcp.startup.load_mcp_tools", return_value=0) as load,
        patch("joshu.core.agent.create_chat_client", return_value=_FakeClient()),
    ):
        result = CliRunner().invoke(app, ["run", "-p", "hello"])

    assert result.exit_code == 0
    load.assert_called_once()
