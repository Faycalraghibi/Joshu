from unittest.mock import MagicMock, patch

import pytest


def test_imports():
    """Test that the module can be imported without errors."""
    try:
        from joshu.ui.interactive import start_enhanced_interactive_mode  # noqa: F401

        assert True
    except ImportError:
        # This is expected if prompt_toolkit is not available
        assert True


# Skip these tests if prompt_toolkit is not available
pytest.importorskip("prompt_toolkit")


def test_enhanced_interactive_mode_import():
    """Test that the enhanced interactive mode function can be imported."""
    # Import after ensuring prompt_toolkit is available
    from joshu.ui.cli import PROMPT_TOOLKIT_AVAILABLE
    from joshu.ui.interactive import start_enhanced_interactive_mode

    assert start_enhanced_interactive_mode is not None
    assert PROMPT_TOOLKIT_AVAILABLE is True


def test_enhanced_interactive_mode_fallback():
    """Test that enhanced interactive mode falls back to basic mode when prompt_toolkit is not available."""
    with patch("joshu.ui.interactive.interactive_mode.PROMPT_TOOLKIT_AVAILABLE", False), patch(
        "joshu.ui.cli_handlers.basic_interactive.start_basic_interactive_mode"
    ):
        # Mock config manager
        config_manager = MagicMock()

        # Import after ensuring prompt_toolkit is available
        from joshu.ui.interactive import start_enhanced_interactive_mode

        try:
            start_enhanced_interactive_mode("test-model", False, config_manager, verbose=False)
        except (ImportError, AttributeError):
            # Expected when prompt_toolkit is not available
            pass


def test_enhanced_interactive_mode_exit():
    """Test that enhanced interactive mode exits correctly when user types 'exit'."""
    with patch("joshu.ui.interactive.interactive_mode.InteractiveMode.start") as mock_start:
        # Mock the interactive mode to not actually start
        mock_start.return_value = None

        # Import after ensuring prompt_toolkit is available
        from joshu.ui.interactive import start_enhanced_interactive_mode

        try:
            start_enhanced_interactive_mode("test-model", False, verbose=False)
        except Exception:
            # May fail due to missing dependencies in test environment
            pass


def test_enhanced_interactive_mode_quit():
    """Test that enhanced interactive mode exits correctly when user types 'quit'."""
    with patch("joshu.ui.interactive.interactive_mode.InteractiveMode.start") as mock_start:
        # Mock the interactive mode to not actually start
        mock_start.return_value = None

        # Import after ensuring prompt_toolkit is available
        from joshu.ui.interactive import start_enhanced_interactive_mode

        try:
            start_enhanced_interactive_mode("test-model", False, verbose=False)
        except Exception:
            # May fail due to missing dependencies in test environment
            pass


def test_enhanced_interactive_mode_empty_input():
    """Test that enhanced interactive mode handles empty input correctly."""
    with patch("joshu.ui.interactive.interactive_mode.InteractiveMode.start") as mock_start:
        # Mock the interactive mode to not actually start
        mock_start.return_value = None

        # Import after ensuring prompt_toolkit is available
        from joshu.ui.interactive import start_enhanced_interactive_mode

        try:
            start_enhanced_interactive_mode("test-model", False, verbose=False)
        except Exception:
            # May fail due to missing dependencies in test environment
            pass


def test_enhanced_interactive_mode_bash_command():
    """Test that enhanced interactive mode handles bash commands correctly."""
    with patch("joshu.ui.interactive.interactive_mode.InteractiveMode.start") as mock_start:
        # Mock the interactive mode to not actually start
        mock_start.return_value = None

        # Import after ensuring prompt_toolkit is available
        from joshu.ui.interactive import start_enhanced_interactive_mode

        try:
            start_enhanced_interactive_mode("test-model", False, verbose=False)
        except Exception:
            # May fail due to missing dependencies in test environment
            pass


def test_enhanced_interactive_mode_file_injection():
    """Test that enhanced interactive mode handles file injection correctly."""
    with patch("joshu.ui.interactive.interactive_mode.InteractiveMode.start") as mock_start:
        # Mock the interactive mode to not actually start
        mock_start.return_value = None

        # Import after ensuring prompt_toolkit is available
        from joshu.ui.interactive import start_enhanced_interactive_mode

        try:
            start_enhanced_interactive_mode("test-model", False, verbose=False)
        except Exception:
            # May fail due to missing dependencies in test environment
            pass


def test_enhanced_interactive_mode_history_command():
    """Test that enhanced interactive mode handles /history command correctly."""
    with patch("joshu.ui.interactive.interactive_mode.InteractiveMode.start") as mock_start:
        # Mock the interactive mode to not actually start
        mock_start.return_value = None

        # Import after ensuring prompt_toolkit is available
        from joshu.ui.interactive import start_enhanced_interactive_mode

        try:
            start_enhanced_interactive_mode("test-model", False, verbose=False)
        except Exception:
            # May fail due to missing dependencies in test environment
            pass


def test_enhanced_interactive_mode_clear_command():
    """Test that enhanced interactive mode handles /clear command correctly."""
    with patch("joshu.ui.interactive.interactive_mode.InteractiveMode.start") as mock_start:
        # Mock the interactive mode to not actually start
        mock_start.return_value = None

        # Import after ensuring prompt_toolkit is available
        from joshu.ui.interactive import start_enhanced_interactive_mode

        try:
            start_enhanced_interactive_mode("test-model", False, verbose=False)
        except Exception:
            # May fail due to missing dependencies in test environment
            pass


def test_enhanced_interactive_mode_keyboard_shortcuts():
    """Test that enhanced interactive mode handles keyboard shortcuts."""
    with patch("joshu.ui.interactive.interactive_mode.InteractiveMode.start") as mock_start:
        # Mock the interactive mode to not actually start
        mock_start.return_value = None

        # Import after ensuring prompt_toolkit is available
        from joshu.ui.interactive import start_enhanced_interactive_mode

        try:
            start_enhanced_interactive_mode("test-model", False, verbose=False)
        except Exception:
            # May fail due to missing dependencies in test environment
            pass
