"""Interactive mode module for Joshu CLI."""

from .interactive_mode import InteractiveMode, start_interactive_mode

__all__ = ["InteractiveMode", "start_interactive_mode"]


# Backward compatibility alias
def start_enhanced_interactive_mode(
    model: str, sandbox: bool = False, config_manager=None, verbose: bool = False
):
    """Backward compatibility wrapper for start_interactive_mode."""
    start_interactive_mode(model, sandbox, verbose=verbose)
