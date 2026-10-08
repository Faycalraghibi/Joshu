"""MCP servers of a plugin installed during a session start without a restart."""

import sys
from pathlib import Path

from joshu.core.config import get_config_manager
from joshu.core.plugins import install
from joshu.core.tool_registry import ToolRegistry
from joshu.mcp.loop import run as run_on_mcp_loop
from joshu.mcp.registry import get_mcp_registry
from joshu.mcp.startup import load_new_mcp_servers

SERVER = Path(__file__).with_name("fake_mcp_server.py")


def test_new_plugin_servers_start_now(tmp_path, monkeypatch):
    monkeypatch.setenv("JOSHU_HOME", str(tmp_path / "home"))
    # Only the plugin's server: not the repository's config/mcp.json
    monkeypatch.setattr("joshu.ui.cli_handlers.mcp_handler._load_from_mcp_json", lambda r: 0)
    get_config_manager().set("mcp_enabled", True)
    plugin = tmp_path / "with-mcp"
    plugin.mkdir()
    (plugin / "joshu-plugin.yaml").write_text(
        "name: with-mcp\n"
        "mcp_servers:\n"
        "  plugin-fake:\n"
        f"    command: {sys.executable!r}\n"
        f"    args: [{str(SERVER)!r}]\n",
        encoding="utf-8",
    )
    install(str(plugin))
    registry = get_mcp_registry()
    lines = []
    try:
        assert load_new_mcp_servers(report=lines.append) > 0
        assert "plugin-fake" in lines[0]
        assert any("echo" in name for name in ToolRegistry().list_tools())
        assert load_new_mcp_servers() == 0  # already running: nothing new
    finally:
        if registry.get_server("plugin-fake"):
            run_on_mcp_loop(registry.disconnect_server("plugin-fake"))
            registry.remove_server("plugin-fake")
        tools = ToolRegistry()
        for name in list(tools.list_tools()):
            if "echo" in name:
                tools.unregister(name)
