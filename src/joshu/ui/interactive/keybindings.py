"""Keyboard bindings for interactive mode."""

import os
import subprocess
from typing import Optional

try:
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.filters import Condition
    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    KeyBindings = None
    Condition = None
    PROMPT_TOOLKIT_AVAILABLE = False


def create_key_bindings(interactive_mode) -> Optional[KeyBindings]:
    """Create key bindings for interactive mode."""
    if not PROMPT_TOOLKIT_AVAILABLE:
        return None
    
    kb = KeyBindings()
    
    @kb.add('c-j')
    def _(event):
        """Ctrl+J for line navigation down"""
        if interactive_mode.vim_mode == 'NORMAL':
            interactive_mode._navigate_history('down')
    
    @kb.add('c-k')
    def _(event):
        """Ctrl+K for line navigation up"""
        if interactive_mode.vim_mode == 'NORMAL':
            interactive_mode._navigate_history('up')
    
    @kb.add('c-r')
    def _(event):
        """Ctrl+R for reverse search"""
        interactive_mode._start_reverse_search()
    
    @kb.add('c-b')
    def _(event):
        """Ctrl+B to send command to background bash"""
        if hasattr(interactive_mode, 'buffer') and interactive_mode.buffer.text:
            interactive_mode._send_to_background(interactive_mode.buffer.text)
    
    @kb.add('c-c')
    def _(event):
        """Ctrl+C for graceful interrupt"""
        event.app.exit(exception=KeyboardInterrupt)
    
    @kb.add('c-d')
    def _(event):
        """Ctrl+D for exit"""
        if not hasattr(interactive_mode, 'buffer') or not interactive_mode.buffer.text:
            event.app.exit()
    
    @kb.add('c-l')
    def _(event):
        """Ctrl+L for clear screen"""
        subprocess.run('clear' if os.name != 'nt' else 'cls', shell=True)
    
    @kb.add('c-t')
    def _(event):
        """Ctrl+T for command suggestion toggle"""
        interactive_mode.suggestions_enabled = not interactive_mode.suggestions_enabled
        interactive_mode._show_message(f"Command suggestions: {'ON' if interactive_mode.suggestions_enabled else 'OFF'}")
    
    @kb.add('escape')
    def _(event):
        """Escape key to switch to NORMAL mode"""
        interactive_mode.vim_mode = 'NORMAL'
    
    # Vim-style navigation in NORMAL mode
    @kb.add('h', filter=Condition(lambda: interactive_mode.vim_mode == 'NORMAL'))
    def _(event):
        """Vim 'h' for left"""
        interactive_mode._move_cursor('left')
    
    @kb.add('l', filter=Condition(lambda: interactive_mode.vim_mode == 'NORMAL'))
    def _(event):
        """Vim 'l' for right"""
        interactive_mode._move_cursor('right')
    
    @kb.add('j', filter=Condition(lambda: interactive_mode.vim_mode == 'NORMAL'))
    def _(event):
        """Vim 'j' for down"""
        interactive_mode._navigate_history('down')
    
    @kb.add('k', filter=Condition(lambda: interactive_mode.vim_mode == 'NORMAL'))
    def _(event):
        """Vim 'k' for up"""
        interactive_mode._navigate_history('up')
    
    @kb.add('w', filter=Condition(lambda: interactive_mode.vim_mode == 'NORMAL'))
    def _(event):
        """Vim 'w' for word forward"""
        interactive_mode._move_cursor('word-forward')
    
    @kb.add('b', filter=Condition(lambda: interactive_mode.vim_mode == 'NORMAL'))
    def _(event):
        """Vim 'b' for word backward"""
        interactive_mode._move_cursor('word-backward')
    
    @kb.add('i', filter=Condition(lambda: interactive_mode.vim_mode == 'NORMAL'))
    def _(event):
        """Vim 'i' to enter INSERT mode"""
        interactive_mode.vim_mode = 'INSERT'
    
    @kb.add('a', filter=Condition(lambda: interactive_mode.vim_mode == 'NORMAL'))
    def _(event):
        """Vim 'a' to append after cursor"""
        interactive_mode.vim_mode = 'INSERT'
        interactive_mode._move_cursor('right')
    
    @kb.add(':', filter=Condition(lambda: interactive_mode.vim_mode == 'NORMAL'))
    def _(event):
        """Vim ':' for command mode"""
        interactive_mode._enter_command_mode()
    
    @kb.add('d', filter=Condition(lambda: interactive_mode.vim_mode == 'NORMAL'))
    def _(event):
        """Start of delete command"""
        interactive_mode._start_vim_delete()
    
    @kb.add('y', filter=Condition(lambda: interactive_mode.vim_mode == 'NORMAL'))
    def _(event):
        """Start of yank command"""
        interactive_mode._start_vim_yank()
    
    @kb.add('p', filter=Condition(lambda: interactive_mode.vim_mode == 'NORMAL'))
    def _(event):
        """Vim 'p' to paste"""
        interactive_mode._paste_from_clipboard()
    
    return kb

