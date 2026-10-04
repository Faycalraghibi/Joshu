"""System prompt for the agent loop: identity, working rules, environment, project rules."""

from __future__ import annotations

import logging
import os
import platform
import subprocess
from datetime import date
from pathlib import Path
from typing import Optional, Sequence

logger = logging.getLogger(__name__)

BASE_PROMPT = """You are Joshu, an AI assistant that works in the user's terminal and codebase.
You complete tasks by calling tools: reading and searching files, editing them, and running shell commands. Keep going until the task is done, then reply with a short summary.

Working rules:
- Look before you act. Read a file before editing it; search the codebase rather than guessing names, paths or APIs.
- Edit with `replace` (exact old_string → new_string, with enough context to be unique). Use `write_file` only for new files or full rewrites.
- Run commands with `run_shell_command`. Each call starts a fresh shell in the working directory, so `cd` does not persist; use `working_directory` or chain with `&&`.
- After changing code, verify it: run the relevant tests, linter or the program itself.
- If a tool call is denied, do not retry it unchanged. Adjust or ask the user.
- Never invent tool results, file contents or command output.
- Be concise. Answer questions directly; plain conversation needs no tools.
- Use commands for the user's platform (see Environment)."""

PLAN_MODE_PROMPT = """You are in PLAN mode (read-only).
Investigate with read-only tools, then reply with a concrete, numbered plan: the files to change, what to change in each, and how to verify it. Do not try to edit files or run commands; those tools are denied in this mode."""

SUBAGENT_PROMPT = """You are a sub-agent of Joshu, given one focused task by the main agent.
You have read-only tools. Investigate, then reply with a complete, self-contained answer: the main agent sees only your final message, not your tool calls. Include file paths and line numbers where relevant."""


def build_system_prompt(
    cwd: Optional[Path] = None,
    plan_mode: bool = False,
    subagent: bool = False,
    project_context: Optional[str] = None,
    sections: Sequence[str] = (),
) -> str:
    """
    Assemble the system prompt.

    Args:
        cwd: Working directory (defaults to the process cwd)
        plan_mode: Add the read-only plan-mode instructions
        subagent: Use the sub-agent preamble instead of the main one
        project_context: Override for project rules + user memory (JOSHU.md);
            loaded from disk when None
        sections: Extra sections added at the end (skills, memory)
    """
    cwd = cwd or Path.cwd()
    parts = [SUBAGENT_PROMPT if subagent else BASE_PROMPT]

    if plan_mode and not subagent:
        parts.append(PLAN_MODE_PROMPT)

    parts.append(environment_block(cwd))

    if project_context is None:
        project_context = _load_project_context(cwd)
    if project_context:
        parts.append(
            "Project instructions and user memory (follow these; they override the "
            "defaults above):\n\n" + project_context
        )

    parts.extend(s for s in sections if s)
    return "\n\n".join(parts)


CUSTOM_SUBAGENT_NOTE = """You are running as a sub-agent of Joshu, given one task by the main agent. Only your final message is returned to it, so make that message complete and self-contained, with file paths and line numbers where relevant."""


def build_subagent_prompt(instructions: str, cwd: Optional[Path] = None) -> str:
    """System prompt for a user-defined sub-agent: its instructions plus context."""
    cwd = cwd or Path.cwd()
    parts = [instructions.strip(), CUSTOM_SUBAGENT_NOTE, environment_block(cwd)]
    project_context = _load_project_context(cwd)
    if project_context:
        parts.append("Project instructions and user memory:\n\n" + project_context)
    return "\n\n".join(parts)


def environment_block(cwd: Path) -> str:
    """Describe the machine and working directory."""
    system = platform.system() or "Unknown"
    if system == "Windows":
        shell = "cmd.exe (commands run through the Windows shell)"
    else:
        shell = os.environ.get("SHELL", "/bin/sh")

    lines = [
        "Environment:",
        f"- Working directory: {cwd}",
        f"- Platform: {system} {platform.release()}",
        f"- Shell: {shell}",
        f"- Date: {date.today().isoformat()}",
    ]

    from joshu.tools.shell_tool import get_shell_config

    sandbox = get_shell_config().sandbox
    if sandbox is not None:
        lines.append(f"- Sandbox: {sandbox.describe()}")

    branch = _git_branch(cwd)
    if branch is not None:
        lines.append(f"- Git repository: yes (branch: {branch or 'detached'})")
    else:
        lines.append("- Git repository: no")

    return "\n".join(lines)


def _git_branch(cwd: Path) -> Optional[str]:
    """Current branch name, "" when detached, None when not a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    branch = result.stdout.strip()
    return "" if branch == "HEAD" else branch


def _load_project_context(cwd: Path) -> str:
    """Instruction files (AGENTS.md, JOSHU.md) plus facts saved with save_memory."""
    parts = []
    try:
        from joshu.core.instructions import load_instructions

        instructions = load_instructions(cwd)
        if instructions:
            parts.append(instructions)
    except Exception as e:
        logger.debug(f"Could not load instruction files: {e}")
    try:
        from joshu.tools.memory import load_memory

        memory = load_memory().strip()
        if memory:
            parts.append("Saved memory (from save_memory):\n" + memory)
    except Exception as e:
        logger.debug(f"Could not load saved memory: {e}")
    return "\n\n".join(parts)
