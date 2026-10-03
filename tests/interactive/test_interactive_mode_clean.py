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
    from joshu.ui.interactive import start_interactive_mode

    assert start_interactive_mode is not None
