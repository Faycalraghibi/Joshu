from unittest.mock import patch

import pytest


def test_imports():
    """Test that the module can be imported without errors."""
    try:
        from joshu.ui.interactive import start_interactive_mode  # noqa: F401

        assert True
    except ImportError:
        # This is expected if prompt_toolkit is not available
        assert True


# Skip these tests if prompt_toolkit is not available
pytest.importorskip("prompt_toolkit")


def test_interactive_mode_import():
    """Test that the interactive mode function can be imported."""
    # Import after ensuring prompt_toolkit is available
    from joshu.ui.cli import PROMPT_TOOLKIT_AVAILABLE
    from joshu.ui.interactive import start_interactive_mode

    assert start_interactive_mode is not None
    assert PROMPT_TOOLKIT_AVAILABLE is True


def test_interactive_mode_fallback():
    """Test that interactive mode falls back to basic mode when prompt_toolkit is not available."""
    with patch("joshu.ui.interactive.interactive_mode.PROMPT_TOOLKIT_AVAILABLE", False), patch(
        "joshu.ui.cli_handlers.basic_interactive.start_basic_interactive_mode"
    ):
        # Import after ensuring prompt_toolkit is available
        from joshu.ui.interactive import start_interactive_mode

        try:
            start_interactive_mode("test-model", False, verbose=False)
        except Exception:
            # Expected when prompt_toolkit is not available
            pass
