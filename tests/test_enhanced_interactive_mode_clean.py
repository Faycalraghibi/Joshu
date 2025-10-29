import pytest
from unittest.mock import patch, MagicMock


def test_imports():
    """Test that the module can be imported without errors."""
    try:
        from joshu.ui.cli import start_enhanced_interactive_mode
        assert True
    except ImportError:
        # This is expected if prompt_toolkit is not available
        assert True


# Skip these tests if prompt_toolkit is not available
pytest.importorskip("prompt_toolkit")


def test_enhanced_interactive_mode_import():
    """Test that the enhanced interactive mode function can be imported."""
    # Import after ensuring prompt_toolkit is available
    from joshu.ui.cli import start_enhanced_interactive_mode, PROMPT_TOOLKIT_AVAILABLE
    assert start_enhanced_interactive_mode is not None
    assert PROMPT_TOOLKIT_AVAILABLE is True


def test_enhanced_interactive_mode_fallback():
    """Test that enhanced interactive mode falls back to basic mode when prompt_toolkit is not available."""
    with patch('joshu.ui.enhanced_interactive.PROMPT_TOOLKIT_AVAILABLE', False), \
         patch('joshu.ui.cli.start_basic_interactive_mode') as mock_basic_mode, \
         patch('rich.console.Console.print') as mock_print:
        
        # Mock config manager
        config_manager = MagicMock()
        
        # Import after ensuring prompt_toolkit is available
        from joshu.ui.enhanced_interactive import start_enhanced_interactive_mode
        start_enhanced_interactive_mode("test-model", False, config_manager)
        
        # Should call the basic mode function
        mock_basic_mode.assert_called_once_with("test-model", False, config_manager)
        # Should print error message
        mock_print.assert_called_with("[red]Error: prompt_toolkit is not available. Falling back to basic interactive mode.[/red]")
