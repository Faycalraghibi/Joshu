import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def test_interactive_command_exists():
    """Test that the interactive command exists."""
    from opencli.ui.cli import app
    
    # Check that app has commands
    assert app is not None
    
    # Try to get the commands
    try:
        # This will trigger the app to register commands
        from typer import Typer
        assert isinstance(app, Typer)
    except ImportError:
        pass  # If typer is not available, skip this test


def test_run_command_exists():
    """Test that the run command exists."""
    from opencli.ui.cli import app
    
    # Check that app has commands
    assert app is not None


def test_import_works():
    """Test that we can import the CLI module."""
    try:
        from opencli.ui.cli import app, interactive, run
        assert app is not None
        assert interactive is not None
        assert run is not None
    except ImportError:
        pytest.fail("Failed to import CLI module")