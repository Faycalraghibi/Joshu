"""Read-only shell commands run without asking; "always allow" keys skip paths."""

import os

import pytest

from joshu.core.permissions import (
    PermissionManager,
    PermissionMode,
    command_key,
    is_read_only_command,
)


@pytest.mark.parametrize(
    "command",
    [
        "dir",
        "ls -la src",
        "type README.md",
        "cat src/app.py",
        "git status",
        "git diff HEAD~1",
        "git log --oneline -5",
        "git branch --show-current",
        "rg TODO src",
    ],
)
def test_read_only_commands(command, tmp_path):
    assert is_read_only_command(command, tmp_path)


@pytest.mark.parametrize(
    "command",
    [
        "rm -rf build",
        "git commit -m x",
        "git branch -D old",
        "git diff --output=patch.txt",
        "rg --pre ./run.sh TODO",
        "cat a.txt > b.txt",
        "dir && del x",
        "type a.txt | more",
        "cat ../../outside.txt",
        "npx skills use x",
    ],
)
def test_not_read_only(command, tmp_path):
    assert not is_read_only_command(command, tmp_path)


def test_paths_outside_the_project_still_ask(tmp_path):
    outside = tmp_path.parent / "elsewhere"
    assert not is_read_only_command(f'dir "{outside}"', tmp_path)
    assert is_read_only_command(f'dir "{tmp_path / "sub"}"', tmp_path)


def test_read_only_command_runs_without_asking(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    asked = []
    manager = PermissionManager(PermissionMode.DEFAULT, approver=lambda r: asked.append(r))
    decision = manager.check("run_shell_command", {"command": "git status"}, True)
    assert decision.allowed and not asked


@pytest.mark.parametrize(
    "command, key",
    [
        ("git diff", "git diff"),
        ("npm test", "npm test"),
        ('dir "C:\\Users\\me\\grill-me" /s /b', "dir"),
        ("type README.md", "type"),
        ("pytest tests/test_x.py", "pytest"),
        ("python -m pytest", "python"),
    ],
)
def test_always_allow_key_skips_paths(command, key):
    assert command_key(command) == key


def test_windows_switches_are_not_paths(tmp_path):
    if os.name != "nt":
        pytest.skip("Windows switches")
    assert is_read_only_command("dir /s /b", tmp_path)
