# Testing Guide

## Overview

Joshu has a comprehensive test suite with **333 passing tests** covering all major features. Tests are organized by feature area and use pytest with mocking to avoid external API calls during testing.

## Test Organization

The test suite has **43 test files** organized into 5 categories:

- **Models & LLM** (12 tests) - Model providers, configuration, pool management
- **Interactive Mode** (8 tests) - Interactive commands and mode behavior
- **Search** (3 tests) - Web search functionality
- **Storage** (2 tests) - Data persistence and session management
- **Core Features** (18 tests) - Safety, auto-fix, context, caching, etc.

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

This skips integration tests that need real LLM connections, making the test suite run much faster.

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

### Model Configuration Fixtures

```python
def test_with_models(deepseek_model, deepseek_api_key):
    # Access configured model identifiers from .env
    model = deepseek_model  # "deepseek/deepseek-chat-v3.1:free"
    api_key = deepseek_api_key
```

Available model fixtures:
- `llama_cpp_model_llama3_8b`
- `llama_cpp_model_mistral_7b`
- `deepseek_model`, `deepseek_api_key`
- `tongyi_model`, `tongyi_api_key`
- `qwen_model`, `qwen_api_key`
- `kimi_dev_model`, `kimi_dev_api_key`
- `agenticat_model`, `agenticat_api_key`

### Sample Data Fixtures

```python
def test_with_sample_data(sample_config_data, sample_translation_data):
    config = sample_config_data  # Dict with default config
    translation = sample_translation_data  # Command translation example
```

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
@patch("joshu.core.translate.translate_with_openrouter")
def test_translation(mock_translate):
    mock_translate.return_value = Translation(
        command="ls -la",
        explanation="List files",
        needs_execution=True
    )

    result = translate_to_command("show files")
    assert result is not None
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

### Local Model Tests

Mark tests requiring local models:

```python
@pytest.mark.requires_local_model
def test_local_model_feature():
    """Requires LOCAL_MODEL_URL and LOCAL_MODEL_IDENTIFIER."""
    pass
```

## Continuous Integration

Tests run automatically on every commit. The CI pipeline:

1. Runs all tests with `pytest -v`
2. Generates coverage report
3. Checks code quality with `ruff` and `mypy`
4. Verifies pre-commit hooks pass

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

### Testing Auto-Fix

```python
from joshu.core.auto_fix import should_attempt_auto_fix

def test_autofix_config():
    config = {
        "auto_fix_enabled": True,
        "auto_fix_max_attempts": 2
    }

    assert should_attempt_auto_fix(config, 0) is True
    assert should_attempt_auto_fix(config, 1) is True
    assert should_attempt_auto_fix(config, 2) is False  # Max reached
```

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
- [Contributing](../README.md) - Contributing guidelines
