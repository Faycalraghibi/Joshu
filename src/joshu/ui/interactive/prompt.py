"""Prompt generation and styling for interactive mode."""

try:
    from prompt_toolkit.styles import Style
    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    Style = None
    PROMPT_TOOLKIT_AVAILABLE = False


def get_style():
    """Get prompt_toolkit style configuration."""
    if not PROMPT_TOOLKIT_AVAILABLE:
        return None
    return Style.from_dict({
        'prompt': '#00aa00 bold',
        'normal-mode': '#0000aa bold',
        'multiline': '#aa0000 bold',
        'reverse-search': '#aaaa00 bold',
        'bash-command': '#aa00aa',
        'file-injection': '#00aaaa',
    })


def get_prompt(interaction_mode: str, vim_mode: str, multiline_mode: bool) -> list:
    """Get the current prompt based on mode."""
    if not PROMPT_TOOLKIT_AVAILABLE:
        return f"[{interaction_mode}] > "
    
    mode_indicator = vim_mode[0] if vim_mode == 'NORMAL' else ''
    multiline_indicator = '>' if multiline_mode else ''
    interaction_mode_display = interaction_mode.upper()
    
    if vim_mode == 'NORMAL':
        return [('class:normal-mode', f'NORMAL [{interaction_mode_display}] {mode_indicator}{multiline_indicator} ')]
    elif multiline_mode:
        return [('class:multiline', f'MULTILINE [{interaction_mode_display}] {multiline_indicator} ')]
    else:
        return [('class:prompt', f'[{interaction_mode_display}]{multiline_indicator} ')]

