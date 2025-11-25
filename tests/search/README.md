# Web Search Tests

This directory contains all tests for the web search functionality.

## Test Files

### `test_web_search.py`
Tests for core search functionality in `joshu.tools.web_search`.

- Search execution (success, errors, edge cases)
- Result formatting
- Configuration integration
- Error handling (library not available, network errors, empty queries)

**13 tests**

### `test_cli_search.py`
Tests for CLI search command in `joshu.ui.cli` and `joshu.ui.cli_handlers.search_handler`.

- CLI command execution (`joshu search`)
- Command-line flags (`--max-results`)
- Configuration states (enabled/disabled)
- Missing library handling
- Handler functionality

**9 tests**

### `test_interactive_search.py`
Tests for interactive mode `/search` slash command in `joshu.ui.interactive.commands`.

- Slash command handling
- Help text integration
- Edge cases (special characters, URLs, whitespace)
- Session flow testing

**9 tests**

## Running Tests

```bash
# Run all search tests
pytest tests/search/ -v

# Run specific test file
pytest tests/search/test_web_search.py -v

# Run with coverage
pytest tests/search/ --cov=joshu.tools.web_search --cov=joshu.ui.cli_handlers.search_handler

# Run specific test
pytest tests/search/test_web_search.py::TestWebSearch::test_search_web_success -v
```

## Test Coverage

- **Total Tests**: 31
- **Pass Rate**: 100% (31/31)
- **Coverage**: Core functionality, CLI, interactive mode, configuration, error handling

## Test Organization

```
tests/search/
├── __init__.py                     # Package marker
├── test_web_search.py              # Core functionality
├── test_cli_search.py              # CLI integration
├── test_interactive_search.py      # Interactive mode
└── README.md                       # This file
```
