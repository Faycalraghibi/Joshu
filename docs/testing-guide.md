# Testing Guide

## Overview

Joshu has a comprehensive test suite covering all major features. Tests are organized by feature area and use pytest with mocking to avoid external API calls during testing.

## Test Organization

The test suite has **67 test files** organized into these categories:

- **Models & LLM** (14 files) - Model providers, configuration, pool management, availability policies
- **Interactive Mode** (8 files) - Interactive commands and mode behavior
- **Search** (3 files) - Web search functionality
- **Storage** (2 files) - Data persistence and session management
- **Core Features** - Safety, agent loop, providers, context, etc.
- **A2A Server** (5 files) - Agent-to-agent communication, events, task stores
- **Agents** (6 files) - Agent definitions, registry, delegation, schema conversion
- **Commands** (1 file) - CLI command processing and action types
- **MCP** (4 files) - MCP server discovery, registry, security

## Running Tests

### Run All Tests

```bash
# Run all tests with verbose output
pytest -v

# Run all tests with coverage
pytest --cov=joshu --cov-report=html

# Run tests quietly (less output)
pytest -q
```

### Run Specific Test Categories

```bash
# Run only model tests
pytest tests/models/ -v

# Run only storage tests
pytest tests/storage/ -v

# Run only A2A server tests
pytest tests/a2a/ -v

# Run agent tests
pytest tests/agents/ -v

# Run command tests
pytest tests/commands/ -v

# Run a specific test file
pytest tests/test_safety.py -v

# Run a specific test function
pytest tests/test_safety.py::test_safe_commands_unix -v
```

### Fast Testing (Skip LLM Tests)

To run only tests that don't require LLM API calls:

```bash
export SKIP_LLM_TESTS=1
pytest -v
```

Any test that reaches a real model endpoint (the OpenAI SDK's chat
`create` call) is skipped. Tests that use a fake chat client are unaffected.
CI sets this. `0` or `false` disables it.

## Test Fixtures

Joshu uses pytest fixtures defined in `tests/conftest.py`:

### Path Fixtures

```python
def test_example(project_root, src_path, tests_path):
    # project_root = /path/to/joshu
    # src_path = /path/to/joshu/src
    # tests_path = /path/to/joshu/tests
    pass
```

### Isolation Fixtures

Applied to every test automatically:

- `_isolated_config` points the global config manager at a temporary file, so
  tests never write `config/config.yaml`.
- `skip_llm_test_fixture` skips tests that reach a real model when
  `SKIP_LLM_TESTS` is set.

## Writing Tests

### Test Structure

Follow the existing patterns:

```python
from unittest.mock import patch, Mock
import pytest

class TestMyFeature:
    """Test suite for my feature."""

    def test_basic_functionality(self):
        """Test description."""
        # Arrange
        input_data = "test"

        # Act
        result = my_function(input_data)

        # Assert
        assert result == expected_output
```

### Mocking External Services

Mock LLM API calls to avoid real API usage:

```python
@patch("joshu.core.llm_client.create_chat_client")
def test_ask_mode(mock_create):
    mock_create.return_value = FakeClient([AssistantTurn(content="answer")])
    ...
```

### Using Temporary Storage

Always use temporary storage to avoid test interference:

```python
import tempfile
from pathlib import Path
from joshu.core.storage import JsonFileStorage
from joshu.core.context_provider import ContextProvider

def test_with_storage():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = JsonFileStorage(Path(tmpdir) / "test.json")
        context = ContextProvider(storage_backend=storage)

        # Test code here
        context.add_to_history("user", "test")
        assert len(context.conversation_context.messages) == 1
```

### Testing Safety Features

```python
from joshu.core.safety import assess_command_safety

def test_dangerous_command():
    report = assess_command_safety("rm -rf /")
    assert report.safe is False
    assert report.danger_level == "CRITICAL"
    assert len(report.reasons) > 0
```

## Test Markers

### Integration Tests

Mark tests that require real LLM connections:

```python
@pytest.mark.integration
def test_real_llm_connection():
    """This test requires a real LLM API key."""
    pytest.skip("Requires real LLM connection")
```

## Continuous Integration

Tests run automatically on every commit. The CI pipeline:

1. Runs linting via `python scripts/lint.py`
2. Runs the tests on Linux (Python 3.10 to 3.14) and Windows
3. Runs all tests with `pytest`
4. Verifies CLI installation

### Reproduce CI Locally

```bash
pip install -e ".[dev]"
python scripts/lint.py
pytest tests/ -q --tb=short
```

### Pre-commit Hook

Use the pre-commit script to validate changes before commit:

```bash
python scripts/pre_commit.py
```

See [Development Automation](development-automation.md) for linting, CI and benchmarks.

## Common Testing Patterns

### Testing CLI Commands

```python
from typer.testing import CliRunner
from joshu.ui.cli import app

runner = CliRunner()

def test_cli_command():
    result = runner.invoke(app, ["history"])
    assert result.exit_code == 0
    assert "command history" in result.output.lower()
```

### Testing Context Provider

```python
def test_context_operations():
    provider = ContextProvider()

    # Add history
    provider.add_to_history("user", "Hello")
    provider.add_to_history("assistant", "Hi!")

    # Set memory
    provider.set_memory("key", "value")

    # Verify
    assert len(provider.conversation_context.messages) == 2
    assert provider.get_memory("key") == "value"
```

### Testing the Agent Loop

Drive the agent with a scripted fake client instead of a real model (see
`tests/core/test_agent_loop.py`):

```python
from joshu.core.agent import Agent
from joshu.core.llm_client import AssistantTurn, ToolCall
from joshu.core.permissions import PermissionManager, PermissionMode


class FakeClient:
    model = "fake"

    def __init__(self, turns):
        self.turns = list(turns)

    def complete(self, messages, tools=None, **kwargs):
        return self.turns.pop(0)


def test_reads_file(tmp_path):
    client = FakeClient([
        AssistantTurn(tool_calls=[ToolCall("c1", "read_file", '{"path": "a.txt"}')]),
        AssistantTurn(content="done"),
    ])
    agent = Agent(client=client, permissions=PermissionManager(PermissionMode.PLAN))
    assert agent.run("read a.txt").text == "done"
```

## Terminal Tests

`tests/e2e/test_terminal.py` starts interactive Joshu in a real pseudo-terminal
(ConPTY through `pywinpty` on Windows, `pexpect` elsewhere), sends keys as
bytes and checks the screen. `pyte` draws the output as a terminal would, so
checks see the final screen rather than the raw stream (`Terminal.rendered()`,
`wait_drawn`). With `Terminal(home, script)` the agent talks to a scripted
model (`tests/e2e/scripted_joshu.py`): a list of turns with text and tool
calls, so whole requests (questions, approvals, diffs, background shells) run
without an API key.

```bash
pytest tests/e2e -q                     # about 30 seconds
JOSHU_SKIP_TERMINAL_TESTS=1 pytest -q   # skip them
```

### Manual checklist

Before a release, in Windows Terminal, the classic console (conhost), mintty
(Git Bash) and a macOS or Linux terminal:

- [ ] The welcome box, prompt, placeholder and bottom bar draw without broken
      lines at 80 columns and when the window is resized.
- [ ] Shift+Tab cycles the modes; Esc clears the input; Esc Esc opens rewind;
      Ctrl+C twice exits.
- [ ] An approval menu: arrows, number keys and Esc work; the diff in it is
      colored.
- [ ] A question with choices: a number picks at once; a multi-select
      question toggles with Space and numbers; "Other" asks for text; Esc
      skips.
- [ ] An edit shows a colored diff; a long one says "ctrl+o to expand" and
      Ctrl+O shows all of it; the path opens the file where links work.
- [ ] A background command: the bar says "1 shell · ↓ to view"; Down opens
      the viewer; Enter shows live output; k stops it; Esc returns.
- [ ] Esc interrupts a running request; Ctrl+O while it works shows full
      output.
- [ ] mintty (no console): menus fall back to numbered prompts.

## Troubleshooting

### Tests Failing with "Module not found"

Ensure you're in the project root and have installed dev dependencies:

```bash
pip install -e .[dev]
```

### Tests Failing with API Errors

Check that you're either:
- Mocking API calls properly, or
- Have set the required environment variables in `.env`

### Storage-Related Test Failures

Always use temporary directories to avoid conflicts:

```python
with tempfile.TemporaryDirectory() as tmpdir:
    # Use tmpdir for storage
```

## Related Documentation

- [Configuration](configuration.md) - Configure test environments
- [Models & Providers](models-and-providers.md) - LLM provider testing
- [Development Automation](development-automation.md) - Lint, CI, benchmarks and releasing
- [Contributing](contributing.md) - Development setup and workflow
