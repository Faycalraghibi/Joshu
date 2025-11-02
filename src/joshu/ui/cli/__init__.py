"""CLI command handlers module."""

# Export main functions for easy access
from .code_handlers import handle_code_command
from .commands import (
    handle_config,
    handle_history,
    handle_repeat_last,
    handle_explain_last,
    handle_examples,
    handle_commands_list,
    handle_explain
)
from .translation_helpers import (
    check_conversational_response,
    handle_translation_execution,
    display_safety_report
)
from .init import initialize_context, setup_logging

__all__ = [
    'handle_code_command',
    'handle_config',
    'handle_history',
    'handle_repeat_last',
    'handle_explain_last',
    'handle_examples',
    'handle_commands_list',
    'handle_explain',
    'check_conversational_response',
    'handle_translation_execution',
    'display_safety_report',
    'initialize_context',
    'setup_logging'
]

