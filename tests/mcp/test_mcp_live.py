"""A real MCP server over stdio (tests/mcp/fake_mcp_server.py): tool calls after
discovery, prompts as slash commands and resources as @server:uri attachments."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from joshu.core.tool_registry import ToolRegistry
from joshu.mcp import extras
from joshu.mcp.discovery import discover_mcp_tools, register_mcp_tools_with_joshu
from joshu.mcp.loop import run as run_on_mcp_loop
from joshu.mcp.registry import get_mcp_registry

SERVER = Path(__file__).with_name("fake_mcp_server.py")


@pytest.fixture(scope="module")
def fake_server():
    # One server for the module: disconnecting waits for the process to exit
    registry = get_mcp_registry()
    registry.add_server_from_dict("fake", {"command": sys.executable, "args": [str(SERVER)]})
    tools = run_on_mcp_loop(discover_mcp_tools(connect_if_needed=True))
    run_on_mcp_loop(register_mcp_tools_with_joshu(tools))
    yield registry
    run_on_mcp_loop(registry.disconnect_server("fake"))
    registry.remove_server("fake")
    tool_registry = ToolRegistry()
    for name in list(tool_registry.list_tools()):
        if "echo" in name:
            tool_registry.unregister(name)


def echo_tool():
    return next(s for s in ToolRegistry().get_available_tools() if "echo" in s.name)


def test_tool_calls_work_after_discovery(fake_server):
    # Regression: discovery and calls used different event loops, so every call failed
    tool = echo_tool()
    assert tool.function(text="hi") == {
        "success": True,
        "result": "echo: hi",
        "tool_name": "echo",
        "server_name": "fake",
    }
    assert tool.function(text="again")["success"]


def test_prompts(fake_server):
    [prompt] = extras.list_prompts()
    assert prompt.command == "fake:review" and prompt.description == "Review a file"
    arguments = extras.parse_prompt_arguments(prompt, "calc.py error handling")
    assert arguments == {"path": "calc.py", "focus": "error handling"}
    assert extras.parse_prompt_arguments(prompt, "focus=speed path=a.py") == {
        "focus": "speed",
        "path": "a.py",
    }
    text = extras.get_prompt_text(prompt, arguments)
    assert text == "Review calc.py focusing on error handling."
    with pytest.raises(ValueError, match="needs: path"):
        extras.get_prompt_text(prompt, {})


def test_resources(fake_server):
    assert [(s, r.uri) for s, r in extras.list_resources()] == [("fake", "notes://todo")]
    message = extras.with_resources("what is left in @fake:notes://todo?")
    assert message.startswith("what is left in [resource: fake:notes://todo]?")
    assert "[Resource fake:notes://todo]\n1. ship v0.3.0" in message


def test_unknown_servers_and_paths_are_left_alone(fake_server):
    text = r"look at @C:\work\x.png and @other:thing"
    assert extras.with_resources(text) == text


def test_prompt_slash_command_runs_the_agent(fake_server):
    from joshu.ui.interactive.commands import CommandHandler

    mode = MagicMock()
    mode._ensure_agent.return_value = True
    CommandHandler(mode).handle_slash_command("/fake:review shapes.py naming")
    mode._run_agent.assert_called_once_with("Review shapes.py focusing on naming.")


def test_mcp_command_lists_prompts_and_resources(fake_server):
    import io

    from rich.console import Console

    from joshu.ui import display
    from joshu.ui.interactive.commands import CommandHandler

    buffer = io.StringIO()
    original = display.console
    display.console = Console(file=buffer, width=120, color_system=None)
    try:
        CommandHandler(MagicMock()).handle_slash_command("/mcp")
    finally:
        display.console = original
    shown = buffer.getvalue()
    assert "/fake:review <path> <focus>" in shown and "@fake:notes://todo" in shown
    assert "1 tools" in shown
