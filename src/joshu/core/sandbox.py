"""
OS-level sandbox for the agent's shell commands.

A sandboxed command can write only inside the working directory (and a
private temp directory), and has no network unless allowed. Backends:

    bubblewrap   Linux (`bwrap`)
    seatbelt     macOS (`sandbox-exec`)
    docker       anywhere Docker runs; commands run in a Linux container with
                 the project mounted at /workspace

Configured in config.yaml:

    shell_sandbox:
      mode: auto          # off | auto | bubblewrap | seatbelt | docker
      network: false      # allow network access inside the sandbox
      image: python:3.12-slim   # docker only
      auto_allow: true    # sandboxed commands run without asking
                          # (commands flagged unsafe still ask)

`auto` picks the first backend that works on this machine. If the requested
sandbox isn't available, commands run unsandboxed and still need approval.
"""

from __future__ import annotations

import logging
import platform
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

MODES = ("off", "auto", "bubblewrap", "seatbelt", "docker")
DEFAULT_DOCKER_IMAGE = "python:3.12-slim"
DOCKER_WORKDIR = "/workspace"


@dataclass
class SandboxSettings:
    mode: str = "off"
    network: bool = False
    image: str = DEFAULT_DOCKER_IMAGE
    auto_allow: bool = True

    @classmethod
    def from_config(cls, data: Optional[Dict[str, Any]]) -> "SandboxSettings":
        data = data or {}
        mode = str(data.get("mode", "off")).strip().lower()
        if mode not in MODES:
            raise ValueError(f"shell_sandbox.mode must be one of {', '.join(MODES)}, not '{mode}'")
        return cls(
            mode=mode,
            network=bool(data.get("network", False)),
            image=str(data.get("image") or DEFAULT_DOCKER_IMAGE),
            auto_allow=bool(data.get("auto_allow", True)),
        )


class Sandbox:
    """Wraps a shell command so it runs isolated."""

    name = "none"

    def __init__(self, workspace: Path, network: bool = False) -> None:
        self.workspace = workspace.resolve()
        self.network = network

    def argv(self, command: str, cwd: Optional[Path] = None) -> List[str]:
        """The program and arguments that run `command` inside the sandbox."""
        raise NotImplementedError

    def wrap(self, command: str, cwd: Optional[Path] = None) -> str:
        """`command` wrapped for the sandbox, as one shell command line."""
        return join_command(self.argv(command, cwd))

    def describe(self) -> str:
        """One line for the system prompt."""
        net = "network access allowed" if self.network else "no network access"
        return (
            f"Shell commands run in a {self.name} sandbox: they can write only inside the "
            f"working directory and temp files; {net}."
        )

    def _cwd(self, cwd: Optional[Path]) -> Path:
        cwd = (cwd or self.workspace).resolve()
        try:
            cwd.relative_to(self.workspace)
        except ValueError:
            return self.workspace
        return cwd


class BubblewrapSandbox(Sandbox):
    name = "bubblewrap"

    def argv(self, command: str, cwd: Optional[Path] = None) -> List[str]:
        ws = str(self.workspace)
        args = [
            "bwrap",
            "--ro-bind", "/", "/",
            "--dev", "/dev",
            "--proc", "/proc",
            "--tmpfs", "/tmp",
            "--bind", ws, ws,
            "--chdir", str(self._cwd(cwd)),
            "--unshare-pid",
            "--die-with-parent",
        ]  # fmt: skip
        if not self.network:
            args.append("--unshare-net")
        return args + ["--", "/bin/sh", "-c", command]


class SeatbeltSandbox(Sandbox):
    name = "seatbelt"

    def profile(self) -> str:
        rules = [
            "(version 1)",
            "(allow default)",
            "(deny file-write*)",
            "(allow file-write*"
            f' (subpath "{self.workspace}")'
            ' (subpath "/private/tmp") (subpath "/private/var/folders")'
            ' (literal "/dev/null") (literal "/dev/tty") (literal "/dev/zero"))',
        ]
        if not self.network:
            rules.append("(deny network*)")
        return "\n".join(rules)

    def argv(self, command: str, cwd: Optional[Path] = None) -> List[str]:
        inner = f"cd {shlex.quote(str(self._cwd(cwd)))} && {command}"
        return ["sandbox-exec", "-p", self.profile(), "/bin/sh", "-c", inner]


class DockerSandbox(Sandbox):
    name = "docker"

    def __init__(self, workspace: Path, network: bool = False, image: str = "") -> None:
        super().__init__(workspace, network)
        self.image = image or DEFAULT_DOCKER_IMAGE

    def argv(self, command: str, cwd: Optional[Path] = None) -> List[str]:
        relative = self._cwd(cwd).relative_to(self.workspace)
        workdir = str(PurePosixPath(DOCKER_WORKDIR, *relative.parts))
        args = ["docker", "run", "--rm", "-v", f"{self.workspace}:{DOCKER_WORKDIR}", "-w", workdir]
        if not self.network:
            args += ["--network", "none"]
        return args + [self.image, "sh", "-c", command]

    def describe(self) -> str:
        net = "network access allowed" if self.network else "no network access"
        return (
            f"Shell commands run in a Linux Docker container ({self.image}) with the working "
            f"directory mounted at {DOCKER_WORKDIR}: use POSIX shell syntax and relative paths; "
            f"only files under {DOCKER_WORKDIR} persist; {net}."
        )


def join_command(argv: List[str]) -> str:
    """Quote an argument list as one command line for the platform's shell."""
    if platform.system() == "Windows":
        return subprocess.list2cmdline(argv)
    return shlex.join(argv)


def resolve_sandbox(
    settings: SandboxSettings, workspace: Path
) -> Tuple[Optional[Sandbox], Optional[str]]:
    """
    The sandbox to use, and a warning when the requested one isn't available.

    Returns:
        (sandbox or None, warning or None)
    """
    if settings.mode == "off":
        return None, None

    candidates = {
        "bubblewrap": lambda: BubblewrapSandbox(workspace, settings.network),
        "seatbelt": lambda: SeatbeltSandbox(workspace, settings.network),
        "docker": lambda: DockerSandbox(workspace, settings.network, settings.image),
    }
    order = list(candidates) if settings.mode == "auto" else [settings.mode]
    for name in order:
        if _available(name):
            return candidates[name](), None

    wanted = (
        "any sandbox (bubblewrap, seatbelt or docker)" if settings.mode == "auto" else settings.mode
    )
    return None, (
        f"Shell sandbox unavailable: {wanted} can't run on this machine. "
        "Commands run unsandboxed and need approval."
    )


def backend_available(name: str) -> bool:
    """Whether the sandbox backend `name` can run on this machine."""
    return _available(name)


def _available(name: str) -> bool:
    system = platform.system()
    if name == "bubblewrap":
        return system == "Linux" and _runs(["bwrap", "--ro-bind", "/", "/", "true"])
    if name == "seatbelt":
        return system == "Darwin" and shutil.which("sandbox-exec") is not None
    if name == "docker":
        # Commands run in a Linux image; an engine in Windows-container mode can't run it
        return _output(["docker", "info", "--format", "{{.OSType}}"]) == "linux"
    return False


def _runs(argv: List[str]) -> bool:
    return _output(argv) is not None


def _output(argv: List[str]) -> Optional[str]:
    """The command's stripped stdout if it exits 0, else None."""
    if shutil.which(argv[0]) is None:
        return None
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def configure_shell_sandbox(
    data: Optional[Dict[str, Any]], workspace: Path
) -> Tuple[Optional[Sandbox], bool, Optional[str]]:
    """
    Set up the shell sandbox from the `shell_sandbox` setting.

    Returns:
        (active sandbox or None, whether sandboxed commands skip approval,
        warning for the user or None)
    """
    from joshu.tools.shell_tool import set_shell_sandbox

    try:
        settings = SandboxSettings.from_config(data)
    except ValueError as e:
        set_shell_sandbox(None)
        return None, False, f"Invalid shell_sandbox setting: {e}"

    sandbox, warning = resolve_sandbox(settings, workspace)
    set_shell_sandbox(sandbox)
    return sandbox, sandbox is not None and settings.auto_allow, warning
