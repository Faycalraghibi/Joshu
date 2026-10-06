"""
Custom slash commands: reusable prompts stored as files.

Commands live in `.joshu/commands/` in the project and in
`~/.joshu/commands/` (project files win on a name clash). `/name args` expands
the command's prompt and sends it to the agent.

Two formats:

    review.md       Markdown: the body is the prompt; optional front matter
                    ---
                    description: Review the staged changes
                    ---
                    Review the staged changes. Focus on: $ARGUMENTS

    status.toml     TOML (same format as extension commands):
                    description = "Summarize repo status"
                    shell = "git status --short"
                    prompt = "Summarize this git status:\n{{shell_output}}\n{{args}}"

Placeholders: `{{args}}` / `$ARGUMENTS` (text after the command name) and
`{{shell_output}}` (output of the optional TOML `shell` command, which needs
the same approval as the agent's shell tool).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

from joshu.extensions.commands import PLACEHOLDER_PATTERN, parse_toml_command

logger = logging.getLogger(__name__)

COMMANDS_SUBDIR = Path(".joshu") / "commands"
_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.S)


@dataclass
class CustomCommand:
    """A prompt template invoked as /name."""

    name: str
    prompt: str
    description: str = ""
    shell: Optional[str] = None
    path: Optional[Path] = None

    def expand(
        self,
        args: str = "",
        run_shell: Optional[Callable[[str], str]] = None,
    ) -> str:
        """
        Build the prompt for the given arguments.

        Args:
            args: Text after the command name
            run_shell: Runs the command's shell step and returns its output;
                without it, the step is skipped
        """
        values: Dict[str, str] = {"args": args.strip(), "shell_output": ""}
        if self.shell and run_shell is not None:
            shell_command = PLACEHOLDER_PATTERN.sub(
                lambda m: values.get(m.group(1), m.group(0)), self.shell
            )
            values["shell_output"] = run_shell(shell_command)

        prompt = self.prompt.replace("$ARGUMENTS", values["args"])
        prompt = PLACEHOLDER_PATTERN.sub(lambda m: values.get(m.group(1), m.group(0)), prompt)
        # Arguments given to a template that doesn't use them are appended
        if values["args"] and "{{args}}" not in self.prompt and "$ARGUMENTS" not in self.prompt:
            prompt = f"{prompt.rstrip()}\n\n{values['args']}"
        return prompt.strip()


def command_dirs(cwd: Optional[Path] = None) -> List[Path]:
    """Directories searched for commands, lowest priority first."""
    from joshu.core.plugins import plugin_dirs
    from joshu.core.sessions import joshu_home

    cwd = cwd or Path.cwd()
    return [*plugin_dirs("commands"), joshu_home() / "commands", cwd / COMMANDS_SUBDIR]


def discover_commands(cwd: Optional[Path] = None) -> Dict[str, CustomCommand]:
    """All custom commands by name; project commands override user ones."""
    commands: Dict[str, CustomCommand] = {}
    for directory in command_dirs(cwd):
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            command = load_command(path)
            if command is not None:
                commands[command.name] = command
    return commands


def load_command(path: Path) -> Optional[CustomCommand]:
    """Parse one command file (.md or .toml); None for other or invalid files."""
    if not path.is_file() or not _NAME_PATTERN.match(path.stem):
        return None

    if path.suffix == ".md":
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning(f"Could not read command {path}: {e}")
            return None
        description = ""
        match = _FRONT_MATTER.match(text)
        if match:
            for line in match.group(1).splitlines():
                key, _, value = line.partition(":")
                if key.strip() == "description":
                    description = value.strip().strip("\"'")
            text = text[match.end() :]
        if not text.strip():
            return None
        return CustomCommand(path.stem, text.strip(), description=description, path=path)

    if path.suffix == ".toml":
        parsed = parse_toml_command(path)
        if parsed is None or not parsed.prompt.strip():
            return None
        return CustomCommand(
            parsed.name,
            parsed.prompt,
            description=parsed.description,
            shell=parsed.shell,
            path=path,
        )

    return None


def split_command(text: str) -> Optional[tuple[str, str]]:
    """'/name some args' -> ('name', 'some args'); None if not a slash command."""
    if not text.startswith("/") or len(text) < 2:
        return None
    name, _, args = text[1:].partition(" ")
    return name, args


def permission_checked_shell(permissions) -> Callable[[str], str]:
    """Shell runner for a command's shell step, gated like the agent's shell tool."""

    def run(command: str) -> str:
        decision = permissions.check("run_shell_command", {"command": command}, True)
        if not decision.allowed:
            return f"(shell step not run: {decision.reason})"

        from joshu.tools.shell_tool import run_shell_command

        result = run_shell_command(command)
        output = (result.get("stdout") or "") + (result.get("stderr") or "")
        return output or result.get("error") or ""

    return run


def expand_slash_command(text: str, permissions, cwd: Optional[Path] = None) -> Optional[str]:
    """
    Expand '/name args' into the command's prompt.

    Returns:
        The prompt, or None when `text` is not a known custom command.
    """
    parsed = split_command(text)
    if parsed is None:
        return None
    command = discover_commands(cwd).get(parsed[0])
    if command is None:
        return None
    return command.expand(parsed[1], run_shell=permission_checked_shell(permissions))
