"""
Every built-in slash command in one place.

The list drives dispatch (CommandHandler), `/help` and the completion menu
that opens when you type `/`, so they can't disagree.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class SlashCommand:
    name: str  # without the slash
    description: str
    group: str
    args: str = ""  # e.g. "[n]" or "<query>"
    aliases: Tuple[str, ...] = ()
    handler: str = ""  # CommandHandler method; defaults to cmd_<name>

    @property
    def method(self) -> str:
        return self.handler or "cmd_" + self.name.replace("-", "_")

    @property
    def usage(self) -> str:
        return f"/{self.name}" + (f" {self.args}" if self.args else "")


GROUPS = ["Conversation", "Context", "Model & mode", "Project", "Settings", "Other"]

COMMANDS: List[SlashCommand] = [
    # Conversation
    SlashCommand(
        "clear",
        "Start a new conversation (the old one stays saved)",
        "Conversation",
        aliases=("reset", "new", "new-session"),
    ),
    SlashCommand(
        "compact", "Summarize the conversation to free context", "Conversation", "[focus]"
    ),
    SlashCommand(
        "rewind", "Go back to an earlier request and restore its files", "Conversation", "[n]"
    ),
    SlashCommand("undo", "Revert the file edits of the last request", "Conversation"),
    SlashCommand("resume", "List saved conversations, or continue one", "Conversation", "[id]"),
    SlashCommand("copy", "Copy the last reply to the clipboard", "Conversation"),
    SlashCommand(
        "rename", "Give this conversation a title (shown in /resume)", "Conversation", "<title>"
    ),
    SlashCommand(
        "fork", "Continue in a copy of this conversation; the original stays", "Conversation"
    ),
    SlashCommand("export", "Save the conversation as Markdown", "Conversation", "[file]"),
    SlashCommand(
        "session", "Manage saved sessions (list, switch, delete)", "Conversation", "[...]"
    ),
    SlashCommand("paste", "Attach the image in the clipboard (or press Alt+V)", "Conversation"),
    # Context
    SlashCommand("context", "Show how much of the context window is used", "Context"),
    SlashCommand("cost", "Tokens and cost of this conversation", "Context"),
    SlashCommand("todos", "Show the agent's current todo list", "Context"),
    SlashCommand(
        "memory", "The agent's saved memories (forget <name> deletes)", "Context", "[...]"
    ),
    SlashCommand("init", "Write or update AGENTS.md for this project", "Context", "[notes]"),
    # Model & mode
    SlashCommand("model", "Show or switch the model for this conversation", "Model & mode", "[id]"),
    SlashCommand("models", "List the provider's models", "Model & mode", "[search]"),
    SlashCommand("agent", "Agent mode: read, edit and run commands", "Model & mode"),
    SlashCommand("plan", "Plan mode: read-only, proposes a plan", "Model & mode"),
    SlashCommand("ask", "Ask mode: answers without tools", "Model & mode"),
    SlashCommand(
        "permissions", "Show or set the permission mode and rules", "Model & mode", "[mode]"
    ),
    # Project
    SlashCommand("review", "Review the current changes for bugs", "Project", "[focus]"),
    SlashCommand(
        "skills", "List, add or remove skills (/<skill> runs one)", "Project", "[add|remove]"
    ),
    SlashCommand(
        "plugin",
        "Plugins and marketplaces (Joshu or Claude Code format)",
        "Project",
        "[install|remove|update|marketplace add] ...",
        aliases=("plugins",),
    ),
    SlashCommand(
        "background",
        "Run a request as a background job in its own worktree",
        "Project",
        "<request>",
        aliases=("bg",),
    ),
    SlashCommand("jobs", "Background jobs", "Project", "[show|apply|stop|log] <id>"),
    SlashCommand(
        "btw",
        "Ask a side question; not added to the conversation (works while a task runs)",
        "Conversation",
        "<question>",
    ),
    SlashCommand(
        "agents", "Sub-agents: list them, or create one", "Project", "[new <name> <what>]"
    ),
    SlashCommand("subagent", "Run a sub-agent on a task yourself", "Project", "<name> <task>"),
    SlashCommand("commands", "List custom commands", "Project"),
    SlashCommand("mcp", "MCP servers and their tools", "Project"),
    SlashCommand("search", "Search the web", "Project", "<query>"),
    SlashCommand(
        "security-review", "Review the current changes for security issues", "Project", "[focus]"
    ),
    SlashCommand(
        "pr-comments", "Bring a pull request's review comments into the chat", "Project", "[number]"
    ),
    SlashCommand("add-dir", "Let the agent work in another directory too", "Project", "<path>"),
    SlashCommand(
        "bashes",
        "Background commands and their live output (kill <id> stops one)",
        "Project",
        "[list | kill <id>]",
    ),
    SlashCommand("hooks", "Show, add or remove hooks", "Project", "[add|remove ...]"),
    # Settings
    SlashCommand("login", "Save a provider's API key", "Settings", "[provider]"),
    SlashCommand("logout", "Remove a provider's saved API key", "Settings", "[provider]"),
    SlashCommand(
        "install-github-action",
        "Set up the @joshu GitHub Action in this repository",
        "Project",
    ),
    SlashCommand(
        "feedback",
        "Report a problem or idea (opens a GitHub issue)",
        "Other",
        "[text]",
        aliases=("bug",),
    ),
    SlashCommand("status", "Version, model, mode and loaded configuration", "Settings"),
    SlashCommand("doctor", "Check the setup: API key, model, tools", "Settings"),
    SlashCommand("config", "Show or set a setting", "Settings", "[key [value]]"),
    SlashCommand("theme", "Choose the color theme", "Settings", "[name]"),
    SlashCommand("vim", "Toggle vim keys in the input", "Settings"),
    SlashCommand(
        "output-style",
        "How replies are written: concise, explanatory, learning",
        "Settings",
        "[name]",
    ),
    SlashCommand(
        "statusline", "Show a command's output under the input", "Settings", "[command|off]"
    ),
    SlashCommand("sandbox", "Show or set the shell sandbox", "Settings", "[mode]"),
    SlashCommand("terminal-setup", "Set up Shift+Enter for new lines", "Settings"),
    # Other
    SlashCommand("help", "Show commands and shortcuts", "Other"),
    SlashCommand("release-notes", "What's new in this version", "Other"),
    SlashCommand("history", "Show your recent input (clear to erase it)", "Other", "[clear]"),
    SlashCommand("exit", "Leave Joshu", "Other", aliases=("quit",)),
]

_BY_NAME: Dict[str, SlashCommand] = {}
for _command in COMMANDS:
    _BY_NAME[_command.name] = _command
    for _alias in _command.aliases:
        _BY_NAME[_alias] = _command


def find_command(name: str) -> Optional[SlashCommand]:
    """The command called `name` (with or without the slash), aliases included."""
    return _BY_NAME.get(name.lstrip("/").lower())


def all_names() -> List[str]:
    return sorted(_BY_NAME)
