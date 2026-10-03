"""Tests for the shell sandbox."""

import platform
import shutil
import subprocess
from pathlib import Path

import pytest

from joshu.core import sandbox as sandbox_module
from joshu.core.permissions import (
    ApprovalChoice,
    PermissionManager,
    PermissionMode,
)
from joshu.core.sandbox import (
    BubblewrapSandbox,
    DockerSandbox,
    Sandbox,
    SandboxSettings,
    SeatbeltSandbox,
    configure_shell_sandbox,
    resolve_sandbox,
)
from joshu.tools.shell_tool import (
    get_shell_config,
    run_shell_command,
    set_shell_sandbox,
)


@pytest.fixture(autouse=True)
def no_sandbox_after_test():
    yield
    set_shell_sandbox(None)


# -------------------------------------------------------------- settings


def test_settings_defaults_and_validation():
    settings = SandboxSettings.from_config(None)
    assert (settings.mode, settings.network, settings.auto_allow) == ("off", False, True)
    assert SandboxSettings.from_config({"mode": "Docker", "network": True}).mode == "docker"
    with pytest.raises(ValueError, match="must be one of"):
        SandboxSettings.from_config({"mode": "chroot"})


# --------------------------------------------------------- command lines


def test_bubblewrap_binds_workspace_and_cuts_network(tmp_path):
    ws = str(tmp_path.resolve())
    argv = BubblewrapSandbox(tmp_path).argv("make test", tmp_path / "sub")
    assert argv[0] == "bwrap"
    assert ["--ro-bind", "/", "/"] == argv[1:4]
    assert ["--bind", ws, ws] == argv[argv.index("--bind") : argv.index("--bind") + 3]
    assert argv[argv.index("--chdir") + 1] == str((tmp_path / "sub").resolve())
    assert "--unshare-net" in argv
    assert argv[-3:] == ["/bin/sh", "-c", "make test"]
    assert "--unshare-net" not in BubblewrapSandbox(tmp_path, network=True).argv("x")


def test_seatbelt_profile_limits_writes_and_network(tmp_path):
    box = SeatbeltSandbox(tmp_path)
    profile = box.profile()
    assert "(deny file-write*)" in profile
    assert f'(subpath "{tmp_path.resolve()}")' in profile
    assert "(deny network*)" in profile
    assert "(deny network*)" not in SeatbeltSandbox(tmp_path, network=True).profile()
    argv = box.argv("ls")
    assert argv[:3] == ["sandbox-exec", "-p", profile] and argv[-1].endswith("&& ls")


def test_docker_mounts_workspace_and_maps_working_directory(tmp_path):
    argv = DockerSandbox(tmp_path, image="alpine:3").argv("ls", tmp_path / "src" / "app")
    assert f"{tmp_path.resolve()}:/workspace" in argv
    assert argv[argv.index("-w") + 1] == "/workspace/src/app"
    assert ["--network", "none"] == argv[argv.index("--network") : argv.index("--network") + 2]
    assert argv[-4:] == ["alpine:3", "sh", "-c", "ls"]
    # A working directory outside the workspace falls back to the workspace root
    assert (
        DockerSandbox(tmp_path).argv("ls", Path("/elsewhere"))[
            DockerSandbox(tmp_path).argv("ls", Path("/elsewhere")).index("-w") + 1
        ]
        == "/workspace"
    )
    assert (
        "Linux Docker container (alpine:3)" in DockerSandbox(tmp_path, image="alpine:3").describe()
    )


# ------------------------------------------------------------ resolution


def test_off_mode_has_no_sandbox_and_no_warning(tmp_path):
    assert resolve_sandbox(SandboxSettings(mode="off"), tmp_path) == (None, None)


def test_auto_mode_picks_first_available(tmp_path, monkeypatch):
    monkeypatch.setattr(sandbox_module, "_available", lambda name: name == "docker")
    box, warning = resolve_sandbox(SandboxSettings(mode="auto"), tmp_path)
    assert isinstance(box, DockerSandbox) and warning is None


def test_unavailable_sandbox_warns_and_disables_auto_allow(tmp_path, monkeypatch):
    monkeypatch.setattr(sandbox_module, "_available", lambda name: False)
    box, auto_allow, warning = configure_shell_sandbox({"mode": "bubblewrap"}, tmp_path)
    assert box is None and auto_allow is False
    assert "unavailable" in warning and "need approval" in warning
    assert get_shell_config().sandbox is None


def test_invalid_setting_is_reported(tmp_path):
    box, auto_allow, warning = configure_shell_sandbox({"mode": "nope"}, tmp_path)
    assert box is None and not auto_allow and "Invalid shell_sandbox" in warning


# ----------------------------------------------------------- permissions


def asking_manager(mode=PermissionMode.DEFAULT):
    asked = []

    def approver(request):
        asked.append(request.tool_name)
        return ApprovalChoice.YES

    return PermissionManager(mode, approver=approver, sandboxed_shell=True), asked


def test_sandboxed_commands_run_without_asking():
    manager, asked = asking_manager()
    assert manager.check("run_shell_command", {"command": "pytest -q"}, True).allowed
    assert asked == []


def test_unsafe_commands_still_ask_when_sandboxed():
    manager, asked = asking_manager()
    dangerous = "format C:" if platform.system() == "Windows" else "rm -rf /"
    manager.check("run_shell_command", {"command": dangerous}, True)
    assert asked == ["run_shell_command"]


def test_plan_mode_still_denies_shell():
    manager, _ = asking_manager(PermissionMode.PLAN)
    assert not manager.check("run_shell_command", {"command": "ls"}, True).allowed


# ------------------------------------------------------------ shell tool


class MarkerSandbox(Sandbox):
    """Replaces every command, so the test can see it was wrapped."""

    name = "marker"

    def argv(self, command, cwd=None):
        raise AssertionError("wrap() is overridden")

    def wrap(self, command, cwd=None):
        return "echo WRAPPED"


def test_shell_tool_runs_wrapped_command(tmp_path):
    set_shell_sandbox(MarkerSandbox(tmp_path))
    result = run_shell_command("echo original")
    assert result["stdout"].strip() == "WRAPPED"


def test_blocklist_checks_the_original_command(tmp_path):
    set_shell_sandbox(MarkerSandbox(tmp_path))
    assert "not allowed" in run_shell_command("shutdown now")["error"]


# ------------------------------------------------- real isolation (if any)


def _bwrap_works():
    if platform.system() != "Linux" or shutil.which("bwrap") is None:
        return False
    try:
        return subprocess.run(["bwrap", "--ro-bind", "/", "/", "true"]).returncode == 0
    except OSError:
        return False


def _docker_works():
    if shutil.which("docker") is None:
        return False
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


@pytest.mark.skipif(not _bwrap_works(), reason="bubblewrap not usable here")
def test_bubblewrap_really_isolates(tmp_path):
    ws, outside = tmp_path / "ws", tmp_path / "outside"
    ws.mkdir()
    outside.mkdir()
    set_shell_sandbox(BubblewrapSandbox(ws))

    result = run_shell_command(
        f"touch inside.txt; touch {outside}/escaped.txt; "
        "python3 -c \"import socket; socket.create_connection(('1.1.1.1', 53), 3)\" "
        "&& echo NET_OK || echo NET_BLOCKED",
        cwd=str(ws),
    )
    assert (ws / "inside.txt").exists()
    assert not (outside / "escaped.txt").exists()
    assert "NET_BLOCKED" in result["stdout"]


@pytest.mark.skipif(not _docker_works(), reason="docker not usable here")
def test_docker_really_isolates(tmp_path):
    set_shell_sandbox(DockerSandbox(tmp_path, image="alpine:3"))
    result = run_shell_command(
        "touch inside.txt && pwd && "
        "(wget -q -T 3 -O /dev/null http://example.com && echo NET_OK || echo NET_BLOCKED)",
        cwd=str(tmp_path),
        timeout=300,
    )
    assert (tmp_path / "inside.txt").exists()
    assert "/workspace" in result["stdout"]
    assert "NET_BLOCKED" in result["stdout"]
