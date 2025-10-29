import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def test_interactive_mode_can_be_imported():
    """Test that the interactive mode components can be imported."""
    try:
        from opencli.ui.enhanced_interactive import EnhancedInteractiveMode, PROMPT_TOOLKIT_AVAILABLE
        assert EnhancedInteractiveMode is not None
        # PROMPT_TOOLKIT_AVAILABLE should be True in the test environment
        assert PROMPT_TOOLKIT_AVAILABLE is True
    except ImportError:
        pytest.fail("Failed to import enhanced interactive mode")


def test_interactive_mode_can_be_instantiated():
    """Test that the enhanced interactive mode can be instantiated."""
    with patch('opencli.ui.enhanced_interactive.get_config_manager') as mock_config_manager, \
         patch('opencli.ui.enhanced_interactive.ContextProvider') as mock_context_provider:
        
        # Mock config manager
        mock_config = MagicMock()
        mock_config.get.return_value = 1000
        mock_config_manager.return_value = mock_config
        
        # Mock context provider
        mock_context_provider.return_value = MagicMock()
        
        from opencli.ui.enhanced_interactive import EnhancedInteractiveMode
        mode = EnhancedInteractiveMode("test-model")
        
        assert mode is not None
        assert mode.model == "test-model"


def test_cli_commands_can_be_imported():
    """Test that CLI commands can be imported."""
    try:
        from opencli.ui.cli import interactive, run
        assert interactive is not None
        assert run is not None
    except ImportError:
        pytest.fail("Failed to import CLI commands")