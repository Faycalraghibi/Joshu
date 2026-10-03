"""Tests for layered configuration and project trust."""

import pytest
import yaml
from typer.testing import CliRunner

from joshu.core import config as config_module
from joshu.core.config import ConfigManager, find_project_config, user_config_path
from joshu.core.paths import joshu_home


@pytest.fixture
def layout(tmp_path, monkeypatch):
    """An install config, a user config and a project with its own config."""
    install = tmp_path / "install" / "config.yaml"
    install.parent.mkdir()
    monkeypatch.setattr(config_module, "install_config_path", lambda: install)

    project = tmp_path / "project"
    (project / ".joshu").mkdir(parents=True)
    (project / "src").mkdir()
    monkeypatch.chdir(project / "src")
    return install, project


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


def test_layers_apply_in_order_when_project_is_trusted(layout):
    install, project = layout
    write(install, {"model": "install-model", "max_tokens": 1000, "agent_max_turns": 10})
    write(user_config_path(), {"max_tokens": 2000, "trusted_projects": [str(project)]})
    write(project / ".joshu" / "config.yaml", {"agent_max_turns": 30})

    manager = ConfigManager()

    assert manager.get("model") == "install-model"
    assert manager.get("max_tokens") == 2000
    assert manager.get("agent_max_turns") == 30
    assert [name for name, _ in manager.layers] == ["install", "user", "project"]


def test_untrusted_project_config_is_ignored_and_reported(layout):
    _, project = layout
    write(project / ".joshu" / "config.yaml", {"hooks": {"before_tool": ["curl evil"]}})

    manager = ConfigManager()

    assert manager.get("hooks") == {}
    assert manager.untrusted_project_config == project / ".joshu" / "config.yaml"


def test_project_config_cannot_trust_itself(layout):
    _, project = layout
    write(user_config_path(), {"trusted_projects": [str(project)]})
    write(project / ".joshu" / "config.yaml", {"trusted_projects": ["/elsewhere"]})

    assert ConfigManager().get("trusted_projects") == [str(project)]


def test_save_writes_only_user_settings(layout):
    install, _ = layout
    write(install, {"model": "install-model"})
    manager = ConfigManager()
    manager.set("max_tokens", 1234)
    manager.save_config()

    saved = yaml.safe_load(user_config_path().read_text(encoding="utf-8"))
    assert saved == {"max_tokens": 1234}
    assert ConfigManager().get("model") == "install-model"


def test_user_config_is_not_mistaken_for_a_project_config(tmp_path, monkeypatch):
    # Running from inside the data directory's parent must not treat
    # ~/.joshu/config.yaml as a project config
    write(user_config_path(), {"max_tokens": 77})
    monkeypatch.chdir(joshu_home().parent)
    assert find_project_config() is None


def test_trust_and_untrust_persist(layout):
    _, project = layout
    manager = ConfigManager()
    manager.trust_project(project)
    manager.save_config()
    assert ConfigManager().get("trusted_projects") == [str(project.resolve())]

    manager = ConfigManager()
    assert manager.untrust_project(project)
    manager.save_config()
    assert ConfigManager().get("trusted_projects") == []


def test_explicit_path_keeps_single_file_behaviour(tmp_path):
    path = tmp_path / "only.yaml"
    manager = ConfigManager(str(path))
    manager.set("max_tokens", 99)
    manager.save_config()
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["model"]  # full dump


def test_trust_command_shows_risky_keys_then_trusts(layout, monkeypatch):
    from joshu.ui.cli import app

    _, project = layout
    write(project / ".joshu" / "config.yaml", {"hooks": {}, "model": "x"})
    monkeypatch.setattr(config_module, "_config_manager_instance", ConfigManager())

    result = CliRunner().invoke(app, ["trust", str(project)])

    assert result.exit_code == 0
    assert "Review these before trusting: hooks" in result.output
    saved = yaml.safe_load(user_config_path().read_text(encoding="utf-8"))
    assert saved["trusted_projects"] == [str(project.resolve())]
