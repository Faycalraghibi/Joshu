"""Plugins: install, discovery by the loaders, hooks and MCP servers, CLI."""

import json
import subprocess
import sys

import pytest
from typer.testing import CliRunner

from joshu.core import plugins
from joshu.core.plugins import PluginError, install, installed_plugins, read_plugin

MANIFEST = """name: release-tools
version: 1.2.0
description: Release helpers
hooks:
  stop:
    - python ${PLUGIN_DIR}/hooks/check.py
mcp_servers:
  tracker:
    command: node
    args: ["${PLUGIN_DIR}/server.js"]
"""


@pytest.fixture
def home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("JOSHU_HOME", str(home))
    return home


@pytest.fixture
def source(tmp_path):
    src = tmp_path / "release-tools"
    (src / "skills" / "changelog").mkdir(parents=True)
    (src / "skills" / "changelog" / "SKILL.md").write_text(
        "---\nname: changelog\ndescription: Write the changelog\n---\nSteps.\n", encoding="utf-8"
    )
    (src / "commands").mkdir()
    (src / "commands" / "ship.md").write_text("Ship it: $ARGUMENTS\n", encoding="utf-8")
    (src / "output-styles").mkdir()
    (src / "output-styles" / "terse.md").write_text(
        "description: Very short\nAnswer in one line.\n", encoding="utf-8"
    )
    (src / "joshu-plugin.yaml").write_text(MANIFEST, encoding="utf-8")
    return src


def test_read_plugin_expands_the_plugin_dir(source):
    plugin = read_plugin(source)
    assert (plugin.name, plugin.version) == ("release-tools", "1.2.0")
    assert plugin.hooks["stop"] == [f"python {source}/hooks/check.py"]
    assert plugin.mcp_servers["tracker"]["args"] == [f"{source}/server.js"]
    assert "skills: changelog" in plugin.contents()
    assert any(line.startswith("hook stop:") for line in plugin.contents())


@pytest.mark.parametrize(
    "manifest, error",
    [
        ("", "name must be"),
        ("name: Bad Name\n", "name must be"),
        ("name: ok\nhooks: [1]\n", "hooks must be a mapping"),
        ("name: [unclosed\n", "joshu-plugin.yaml"),
    ],
)
def test_bad_manifests(tmp_path, manifest, error):
    (tmp_path / "joshu-plugin.yaml").write_text(manifest, encoding="utf-8")
    with pytest.raises(PluginError, match=error):
        read_plugin(tmp_path)
    with pytest.raises(PluginError, match="has no"):
        read_plugin(tmp_path / "missing")


def test_install_from_a_directory_then_the_loaders_find_it(home, source, tmp_path):
    plugin = install(str(source))
    assert plugin.path == home / "plugins" / "release-tools"
    assert plugin.source == str(source.resolve())
    with pytest.raises(PluginError, match="already installed"):
        install(str(source))

    from joshu.core.custom_commands import discover_commands
    from joshu.core.output_styles import available_styles
    from joshu.core.skills import discover_skills

    project = tmp_path / "project"
    project.mkdir()
    assert discover_skills(project)["changelog"].scope == "plugin"
    assert "ship" in discover_commands(project)
    assert "terse" in available_styles(project)

    # The user's own command of the same name wins
    (home / "commands").mkdir()
    (home / "commands" / "ship.md").write_text("Mine: $ARGUMENTS\n", encoding="utf-8")
    assert "Mine" in discover_commands(project)["ship"].prompt


def test_hooks_and_mcp_servers_are_registered(home, source):
    install(str(source))
    from joshu.hooks.dispatcher import (
        configure_hooks_from_settings,
        get_hook_dispatcher,
    )

    def commands():
        return [h.command for hooks in get_hook_dispatcher()._hooks.values() for h in hooks]

    assert configure_hooks_from_settings({}) == []
    assert any("hooks/check.py" in c for c in commands())
    configure_hooks_from_settings({})  # replaced, not added twice
    assert len([c for c in commands() if "check.py" in c]) == 1

    assert set(plugins.plugin_mcp_servers()) == {"tracker"}
    plugins.set_enabled("release-tools", False)
    assert plugins.plugin_mcp_servers() == {} and plugins.plugin_dirs("skills") == []
    configure_hooks_from_settings({})
    assert not [c for c in commands() if "check.py" in c]
    assert installed_plugins()[0].enabled is False
    get_hook_dispatcher().clear_script_hooks()


def test_install_from_git(home, source):
    git = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run(git + ["init", "-q"], cwd=source, check=True)
    subprocess.run(git + ["add", "."], cwd=source, check=True)
    subprocess.run(git + ["commit", "-qm", "init"], cwd=source, check=True)
    url = source.resolve().as_uri() + "/.git"  # file:// URLs clone like remote ones
    plugin = install(url)
    assert plugin.source == url and not (plugin.path / ".git").exists()

    (source / "joshu-plugin.yaml").write_text(MANIFEST.replace("1.2.0", "1.3.0"), encoding="utf-8")
    subprocess.run(git + ["commit", "-qam", "bump"], cwd=source, check=True)
    assert plugins.update("release-tools").version == "1.3.0"


def test_update_and_remove(home, source):
    install(str(source))
    plugins.set_enabled("release-tools", False)
    (source / "joshu-plugin.yaml").write_text(MANIFEST.replace("1.2.0", "2.0.0"), encoding="utf-8")
    updated = plugins.update("release-tools")
    assert updated.version == "2.0.0" and updated.enabled is False  # stays disabled
    plugins.remove("release-tools")
    assert installed_plugins() == []
    with pytest.raises(PluginError, match="No plugin named"):
        plugins.remove("release-tools")


def test_cli(home, source):
    from joshu.ui.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["plugin", "install", str(source)], input="n\n")
    assert "run commands" in result.output and "Not installed" in result.output
    result = runner.invoke(app, ["plugin", "install", str(source), "--yes"])
    assert result.exit_code == 0, result.output
    result = runner.invoke(app, ["plugin", "list"])
    assert "release-tools" in result.output and "skills: changelog" in result.output
    assert "disabled" in runner.invoke(app, ["plugin", "disable", "release-tools"]).output
    assert runner.invoke(app, ["plugin", "remove", "release-tools"]).exit_code == 0
    assert runner.invoke(app, ["plugin", "remove", "nope"]).exit_code == 1
    assert "No plugins" in runner.invoke(app, ["plugin"]).output


def test_plugins_dir_follows_joshu_home(home):
    assert plugins.plugins_dir() == home / "plugins"
    assert json.dumps(installed_plugins()) == "[]"
    assert sys.modules["joshu.core.plugins"] is plugins
