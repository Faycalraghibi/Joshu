"""Credential files are hidden from sandboxed commands (shell_sandbox.hide)."""

import pytest

from joshu.core.sandbox import (
    DEFAULT_HIDDEN,
    BubblewrapSandbox,
    SandboxSettings,
    SeatbeltSandbox,
)


@pytest.fixture
def home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".ssh").mkdir(parents=True)
    (home / ".ssh" / "id_ed25519").write_text("secret", encoding="utf-8")
    (home / ".netrc").write_text("machine x password y", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return home


def test_bubblewrap_hides_existing_credentials(home, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    argv = BubblewrapSandbox(project).argv("ls")
    ssh, netrc = str((home / ".ssh").resolve()), str((home / ".netrc").resolve())
    assert argv[argv.index(ssh) - 1] == "--tmpfs"  # a directory: an empty tmpfs over it
    assert argv[argv.index(netrc) - 2 : argv.index(netrc)] == ["--ro-bind", "/dev/null"]
    assert str(home / ".aws") not in " ".join(argv)  # missing paths are skipped
    # After the read-only root, so the hiding wins
    assert argv.index("--ro-bind") < argv.index("--tmpfs", argv.index(ssh) - 1)


def test_seatbelt_denies_reading_them(home, tmp_path):
    profile = SeatbeltSandbox(tmp_path).profile()
    assert f'(deny file-read* (subpath "{(home / ".ssh").resolve()}"))' in profile
    assert f'(deny file-read* (literal "{(home / ".netrc").resolve()}"))' in profile


def test_never_hides_the_project(home):
    project = home / ".ssh" / "work"  # an odd place, but the project must stay visible
    project.mkdir()
    assert str((home / ".ssh").resolve()) not in BubblewrapSandbox(project).argv("ls")


def test_setting(home, tmp_path):
    assert SandboxSettings.from_config({"mode": "auto"}).hide == DEFAULT_HIDDEN
    assert SandboxSettings.from_config({"hide": []}).hide == []
    custom = SandboxSettings.from_config({"hide": ["~/secrets"]}).hide
    assert custom == ["~/secrets"]
    none = BubblewrapSandbox(tmp_path, hide=[])
    assert str((home / ".ssh").resolve()) not in none.argv("ls")
    assert "can't be read" in BubblewrapSandbox(tmp_path).describe()
    assert "can't be read" not in none.describe()
