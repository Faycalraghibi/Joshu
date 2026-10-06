"""Managed settings: an administrator's file that wins and locks settings."""

import pytest
import yaml
from typer.testing import CliRunner

from joshu.core import config as config_module
from joshu.core.config import ConfigManager, managed_settings_path, user_config_path
from joshu.core.permissions import PermissionManager, PermissionMode


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


@pytest.fixture
def managed(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module, "install_config_path", lambda: tmp_path / "none.yaml")
    monkeypatch.chdir(tmp_path)
    return managed_settings_path()


def test_path(monkeypatch, tmp_path):
    assert managed_settings_path() == tmp_path / "managed-settings.yaml"  # set by conftest
    monkeypatch.delenv("JOSHU_MANAGED_SETTINGS")
    default = managed_settings_path()
    assert default.parts[-2:] == ("joshu", "managed-settings.yaml")
    if config_module.os.name == "nt":
        assert "ProgramData" in str(default)


def test_managed_settings_win_and_are_locked(managed):
    write(user_config_path(), {"max_tokens": 2000, "mcp_enabled": True, "theme": "light"})
    write(managed, {"mcp_enabled": False, "max_tokens": 4000})
    manager = ConfigManager()
    assert manager.get("mcp_enabled") is False and manager.get("max_tokens") == 4000
    assert manager.get("theme") == "light"  # not managed: the user's
    assert ("managed", managed) in manager.layers
    assert manager.locked_keys() == ["max_tokens", "mcp_enabled"]
    assert manager.set("mcp_enabled", True) is False
    assert "administrator" in manager.locked_reason("mcp_enabled")
    assert manager.set("theme", "dark") is True


def test_managed_rules_are_added_to_everyones(managed):
    write(user_config_path(), {"permissions": {"allow": ["read_file"], "deny": []}})
    write(managed, {"permissions": {"deny": ["run_shell_command(git push*)"]}})
    manager = ConfigManager()
    rules = manager.get("permissions")
    assert rules["allow"] == ["read_file"]
    assert rules["deny"] == ["run_shell_command(git push*)"]
    # The user can add rules, never drop the administrator's
    assert manager.set("permissions", {"allow": [], "deny": ["write_file(.env*)"]})
    assert manager.get("permissions")["deny"] == [
        "write_file(.env*)",
        "run_shell_command(git push*)",
    ]
    assert manager.locked_keys() == []


def test_no_bypass_anywhere(managed, monkeypatch):
    write(user_config_path(), {"permission_mode": "bypass"})
    write(managed, {"allow_bypass": False})
    manager = ConfigManager()
    monkeypatch.setattr(config_module, "_config_manager_instance", manager)
    assert manager.get("permission_mode") == "default"
    assert manager.set("permission_mode", "bypass") is False
    assert manager.set("permission_mode", "accept_edits") is True

    permissions = PermissionManager(PermissionMode.BYPASS)
    assert permissions.mode == PermissionMode.DEFAULT and permissions.bypass_refused
    permissions.mode = PermissionMode.BYPASS
    assert permissions.mode == PermissionMode.DEFAULT
    permissions.mode = PermissionMode.PLAN
    assert permissions.mode == PermissionMode.PLAN


def test_bypass_still_works_without_managed_settings(managed, monkeypatch):
    manager = ConfigManager()
    monkeypatch.setattr(config_module, "_config_manager_instance", manager)
    assert PermissionManager(PermissionMode.BYPASS).mode == PermissionMode.BYPASS
    assert manager.locked_keys() == []


def test_config_set_says_why(managed, monkeypatch):
    write(managed, {"mcp_enabled": False})
    monkeypatch.setattr(config_module, "_config_manager_instance", ConfigManager())
    from joshu.ui.cli import app

    result = CliRunner().invoke(app, ["config", "--set", "mcp_enabled=true"])
    assert result.exit_code == 1 and "administrator" in result.output
    result = CliRunner().invoke(app, ["config", "--list"])
    assert "managed" in result.output and "set by your administrator: mcp_enabled" in result.output
