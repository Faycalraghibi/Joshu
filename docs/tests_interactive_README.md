# Interactive Mode Tests

This directory contains all interactive mode related tests for the Joshu Assistant project.

## Organization

- `test_interactive_mode.py` - Basic interactive mode tests
- `test_interactive_modes.py` - Tests for interactive mode handlers (ask, plan, agent)
- `test_interactive_commands.py` - Tests for interactive CLI commands
- `test_interactive_mode_end_to_end.py` - End-to-end interactive mode tests
- `test_enhanced_interactive_mode.py` - Enhanced interactive mode tests
- `test_enhanced_interactive_mode_clean.py` - Clean enhanced interactive mode tests
- `test_enhanced_interactive_mode_proper.py` - Proper enhanced interactive mode tests

## Test Structure

All tests use mocking to avoid requiring actual interactive environments or user input.

## Refactored Tests

All interactive mode related tests have been moved from the main tests directory to this dedicated folder for better organization.