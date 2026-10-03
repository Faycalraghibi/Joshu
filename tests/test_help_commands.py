from typer.testing import CliRunner

from joshu.ui.cli import app

runner = CliRunner()


def test_examples_command():
    """Test the examples command."""
    result = runner.invoke(app, ["examples"])
    assert result.exit_code == 0
    assert "Joshu Usage Examples" in result.output
    assert "Basic Commands:" in result.output
    assert "File System Intelligence:" in result.output
    assert "Code Generation:" in result.output


def test_commands_command():
    """Test the commands command without category."""
    result = runner.invoke(app, ["commands"])
    assert result.exit_code == 0
    assert "Joshu Command Categories" in result.output
    assert "Available Categories:" in result.output
    assert "file" in result.output
    assert "system" in result.output


def test_commands_command_with_category():
    """Test the commands command with a specific category."""
    result = runner.invoke(app, ["commands", "file"])
    assert result.exit_code == 0
    assert "File System Commands:" in result.output
    assert "List files:" in result.output
    assert "Find files:" in result.output


def test_commands_command_with_unknown_category():
    """Test the commands command with an unknown category."""
    result = runner.invoke(app, ["commands", "unknown"])
    assert result.exit_code == 0
    assert "Unknown category: unknown" in result.output
    assert "Available Categories:" in result.output


class _FakeClient:
    model = "fake"

    def __init__(self, answer):
        self.answer = answer
        self.requests = []

    def complete(self, messages, tools=None, **kwargs):
        from joshu.core.llm_client import AssistantTurn

        self.requests.append(list(messages))
        return AssistantTurn(content=self.answer)


def test_explain_command():
    """explain asks the agent, read-only, and prints its answer."""
    from unittest.mock import patch

    client = _FakeClient("tar creates and extracts archives; -c creates, -z gzips.")
    with (
        patch("joshu.ui.cli.print_banner"),
        patch("joshu.core.agent.create_chat_client", return_value=client),
    ):
        result = runner.invoke(app, ["explain", "tar -czf out.tgz src"])

    assert result.exit_code == 0
    assert "tar creates and extracts archives" in result.output
    system_prompt, prompt = client.requests[0][0]["content"], client.requests[0][-1]["content"]
    assert "tar -czf out.tgz src" in prompt
    assert "PLAN mode" in system_prompt  # read-only: nothing is run or changed


def test_explain_command_without_provider():
    """explain reports a missing provider instead of crashing."""
    from unittest.mock import patch

    from joshu.core.llm_client import LLMError

    error = LLMError("Provider 'openrouter' needs an API key: set OPENROUTER_API_KEY.")
    with (
        patch("joshu.ui.cli.print_banner"),
        patch("joshu.core.agent.create_chat_client", side_effect=error),
    ):
        result = runner.invoke(app, ["explain", "tar"])

    assert result.exit_code == 1
    assert "OPENROUTER_API_KEY" in result.output


def test_help_command():
    """Test the built-in help command."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Joshu - Natural language meets your terminal." in result.output
    # Check that our new commands are listed
    assert "commands" in result.output
    assert "examples" in result.output
    assert "explain" in result.output
    # Check for the Commands section header (in a box)
    assert "Commands" in result.output
