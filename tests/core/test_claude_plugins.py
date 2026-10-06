"""Claude Code plugins and marketplaces, and Claude Code hook scripts, in Joshu."""

import json
import sys

import pytest

from joshu.core import claude_compat, plugins
from joshu.core.plugins import (
    PluginError,
    add_marketplace,
    github_url,
    install,
    installed_plugins,
    list_marketplaces,
    read_plugin,
)

# A hook written for Claude Code: reads its stdin fields, answers in its format
HOOK = r"""
import json, sys
event = json.load(sys.stdin)
if event.get("hook_event_name") == "SessionStart":
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
          "additionalContext": "context from " + event.get("source", "?")}}))
elif event.get("tool_name") == "Bash" and "rm -rf" in event["tool_input"]["command"]:
    print(json.dumps({"decision": "block", "reason": "no rm -rf"}))
"""


@pytest.fixture
def home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("JOSHU_HOME", str(home))
    return home


@pytest.fixture
def market(tmp_path):
    """A marketplace repo laid out like Claude Code's, with one plugin at its root."""
    root = tmp_path / "learn-market"
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps(
            {
                "name": "learn-market",
                "metadata": {"description": "Learning plugins"},
                "plugins": [
                    {"name": "teach", "source": "./", "description": "Teaches"},
                    {"name": "gone", "source": "./missing"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "teach", "version": "0.1.0", "description": "Teaches"}),
        encoding="utf-8",
    )
    (root / "hooks").mkdir()
    (root / "hooks" / "hook.py").write_text(HOOK, encoding="utf-8")
    (root / "hooks" / "hooks.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "SessionStart": [
                        {
                            "matcher": "startup|resume",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": f'"{sys.executable}" "${{CLAUDE_PLUGIN_ROOT}}/hooks/hook.py"',
                                    "timeout": 5,
                                }
                            ],
                        }
                    ],
                    "PreToolUse": [
                        {
                            "matcher": "Bash",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": f'"{sys.executable}" "${{CLAUDE_PLUGIN_ROOT}}/hooks/hook.py"',
                                }
                            ],
                        }
                    ],
                    "UnknownEvent": [{"hooks": [{"type": "command", "command": "x"}]}],
                }
            }
        ),
        encoding="utf-8",
    )
    (root / ".mcp.json").write_text(
        json.dumps(
            {"mcpServers": {"notes": {"command": "node", "args": ["${CLAUDE_PLUGIN_ROOT}/s.js"]}}}
        ),
        encoding="utf-8",
    )
    (root / "skills" / "learn").mkdir(parents=True)
    (root / "skills" / "learn" / "SKILL.md").write_text(
        "---\nname: learn\ndescription: Learning mode\ndisable-model-invocation: true\n---\nTeach.\n",
        encoding="utf-8",
    )
    (root / "agents").mkdir()
    (root / "agents" / "tutor.md").write_text(
        "---\nname: tutor\ndescription: Explains code\ntools: Read, Grep, Glob\nmodel: sonnet\n---\nExplain.\n",
        encoding="utf-8",
    )
    return root


def test_reads_a_claude_code_plugin(market):
    plugin = read_plugin(market)
    assert (plugin.name, plugin.version) == ("teach", "0.1.0")
    (start,) = plugin.hooks["session_start"]
    assert str(market) in start["command"] and start["matcher"] == "startup|resume"
    assert plugin.hooks["before_tool"][0]["matcher"] == "Bash"
    assert set(plugin.hooks) == {"session_start", "before_tool"}
    assert plugin.mcp_servers["notes"]["args"] == [f"{market}/s.js"]
    assert "agents: tutor" in plugin.contents()


def test_marketplace_add_install_update(home, market):
    added = add_marketplace(str(market))
    assert added.name == "learn-market" and [p["name"] for p in added.plugins] == ["teach", "gone"]
    assert [m.name for m in list_marketplaces()] == ["learn-market"]

    plugin = install("teach@learn-market")
    assert plugin.source == "teach@learn-market"
    assert [p.name for p in installed_plugins()] == ["teach"]  # the marketplace isn't a plugin
    with pytest.raises(PluginError, match="has no plugin 'nope'"):
        install("nope@learn-market")
    with pytest.raises(PluginError, match="isn't a directory"):
        install("gone@learn-market")

    # A plain name works when one marketplace has it
    plugins.remove("teach")
    assert install("teach").name == "teach"

    data = json.loads((market / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    data["version"] = "0.2.0"
    (market / ".claude-plugin" / "plugin.json").write_text(json.dumps(data), encoding="utf-8")
    assert plugins.update("teach").version == "0.2.0"  # the marketplace is fetched again
    plugins.remove_marketplace("learn-market")
    assert list_marketplaces() == [] and installed_plugins()[0].name == "teach"


def test_the_loaders_use_it(home, market, tmp_path):
    install(str(market))
    from joshu.core.skills import discover_skills
    from joshu.core.subagents import discover_subagents

    project = tmp_path / "project"
    project.mkdir()
    assert discover_skills(project)["learn"].scope == "plugin"
    tutor = discover_subagents(project)["tutor"]
    assert tutor.tools == ["read_file", "search_file_content", "glob"] and tutor.model is None


def test_claude_code_hooks_run_with_their_input_and_output(home, market):
    install(str(market))
    from joshu.hooks.dispatcher import (
        configure_hooks_from_settings,
        dispatch_before_tool,
        dispatch_session_start,
        get_hook_dispatcher,
    )

    assert configure_hooks_from_settings({}) == []
    try:
        result = dispatch_session_start("s1", {"source": "startup"})
        assert result.context == "context from startup"
        # The matcher picks events: a "clear" start doesn't run it
        assert dispatch_session_start("s1", {"source": "clear"}).context is None

        blocked = dispatch_before_tool("s1", "run_shell_command", {"command": "rm -rf /"})
        assert blocked.should_block and blocked.response.message == "no rm -rf"
        assert not dispatch_before_tool("s1", "run_shell_command", {"command": "ls"}).should_block
        # Matcher "Bash": a read doesn't run the hook at all
        assert not dispatch_before_tool("s1", "read_file", {"path": "rm -rf"}).should_block
    finally:
        get_hook_dispatcher().clear_script_hooks()


def test_translation_helpers(monkeypatch):
    fields = claude_compat.hook_input(
        "before_tool", "s", {"tool_name": "read_file", "arguments": {"path": "a.py"}}
    )
    assert fields["hook_event_name"] == "PreToolUse" and fields["tool_name"] == "Read"
    assert fields["tool_input"] == {"path": "a.py", "file_path": "a.py"}
    assert claude_compat.matches("Edit|Write", "before_tool", {"tool_name": "replace"})
    assert not claude_compat.matches("Bash", "before_tool", {"tool_name": "replace"})
    assert claude_compat.response_fields({"continue": False, "stopReason": "x"}) == {
        "action": "block",
        "message": "x",
    }
    deny = {"hookSpecificOutput": {"permissionDecision": "deny", "permissionDecisionReason": "r"}}
    assert claude_compat.response_fields(deny) == {"action": "block", "message": "r"}

    monkeypatch.setattr(claude_compat.sys, "platform", "win32")
    monkeypatch.setattr(
        claude_compat.shutil, "which", lambda name: {"python": r"C:\Python\python.exe"}.get(name)
    )
    assert claude_compat._python_command("python3 x.py") == "python x.py"


def test_github_shorthand(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert github_url("nykooi1/vibe-wise") == "https://github.com/nykooi1/vibe-wise.git"
    assert github_url("https://x/y") is None and github_url("one-part") is None
    (tmp_path / "local" / "dir").mkdir(parents=True)
    assert github_url("local/dir") is None  # an existing directory wins


def test_slash_command(home, market):
    from io import StringIO

    from rich.console import Console

    from joshu.ui.cli_plugins import PluginCommands

    out = StringIO()
    commands = PluginCommands(Console(file=out, width=200), lambda question, default: True)
    commands.run(f'marketplace add "{market}"')
    assert "Added marketplace learn-market" in out.getvalue()
    assert "plugin install teach@learn-market" in out.getvalue()
    commands.run("install teach@learn-market")
    assert "Installed teach" in out.getvalue()
    commands.run("")
    assert "Marketplaces: learn-market" in out.getvalue()
    commands.run("remove nope")
    assert "No plugin named" in out.getvalue()
    commands.run("frobnicate")
    assert "Usage: /plugin" in out.getvalue()
