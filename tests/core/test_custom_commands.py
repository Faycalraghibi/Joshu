"""Tests for custom slash commands."""

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from joshu.core.custom_commands import (
    discover_commands,
    expand_slash_command,
    load_command,
    split_command,
)
from joshu.core.llm_client import AssistantTurn
from joshu.core.permissions import PermissionManager, PermissionMode
from joshu.core.sessions import joshu_home


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    commands = tmp_path / ".joshu" / "commands"
    commands.mkdir(parents=True)
    return commands


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_markdown_command_with_front_matter_and_arguments(project):
    write(
        project / "review.md",
        "---\ndescription: Review a file\n---\nReview $ARGUMENTS for bugs.\n",
    )
    command = load_command(project / "review.md")

    assert command.description == "Review a file"
    assert command.expand("src/app.py") == "Review src/app.py for bugs."


def test_arguments_are_appended_when_template_has_no_placeholder(project):
    write(project / "explain.md", "Explain this codebase.")
    command = load_command(project / "explain.md")
    assert command.expand("focus on auth") == "Explain this codebase.\n\nfocus on auth"


def test_toml_command_shell_step_runs_when_allowed(project):
    write(
        project / "status.toml",
        'description = "Status"\nshell = "echo {{args}}"\nprompt = "Output: {{shell_output}}"\n',
    )
    prompt = expand_slash_command("/status hello", PermissionManager(PermissionMode.BYPASS))
    assert prompt.startswith("Output: hello")


def test_toml_command_shell_step_needs_approval(project):
    write(project / "status.toml", 'shell = "echo hi"\nprompt = "Output: {{shell_output}}"\n')
    prompt = expand_slash_command("/status", PermissionManager(PermissionMode.DEFAULT))
    assert "shell step not run" in prompt and "requires approval" in prompt


def test_project_commands_override_user_commands(project):
    write(joshu_home() / "commands" / "deploy.md", "user version")
    write(joshu_home() / "commands" / "only-user.md", "from home")
    write(project / "deploy.md", "project version")

    commands = discover_commands()
    assert commands["deploy"].prompt == "project version"
    assert commands["only-user"].prompt == "from home"


def test_invalid_files_are_ignored(project):
    write(project / "empty.md", "---\ndescription: nothing\n---\n")
    write(project / "notes.txt", "not a command")
    write(project / "bad name.md", "spaces are not allowed")
    assert discover_commands() == {}


def test_unknown_command_and_split():
    assert split_command("/review a b") == ("review", "a b")
    assert split_command("plain text") is None
    assert expand_slash_command("/nope", PermissionManager()) is None


# ---------------------------------------------------------------------- CLI


class FakeClient:
    model = "fake"

    def __init__(self, answer):
        self.answer = answer
        self.requests = []

    def complete(self, messages, tools=None, **kwargs):
        self.requests.append(list(messages))
        return AssistantTurn(content=self.answer)


def test_cli_runs_expanded_custom_command(project):
    from joshu.ui.cli import app

    write(project / "review.md", "Review $ARGUMENTS carefully.")
    client = FakeClient("looks fine")
    with patch("joshu.core.agent.create_chat_client", return_value=client):
        result = CliRunner().invoke(app, ["run", "-p", "/review main.py"])

    assert result.exit_code == 0
    assert client.requests[0][-1]["content"] == "Review main.py carefully."


def test_cli_rejects_unknown_custom_command(project):
    from joshu.ui.cli import app

    with patch("joshu.core.agent.create_chat_client", return_value=FakeClient("x")):
        result = CliRunner().invoke(app, ["run", "-p", "/missing"])
    assert result.exit_code == 2
