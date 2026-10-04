"""Keyboard bindings for interactive mode.

Vim keys come from prompt_toolkit's own vi mode (`vim_mode: true` or /vim),
and Ctrl+R history search from its built-in bindings.
"""

import os
import time
from typing import Optional

try:
    from prompt_toolkit.application import get_app, run_in_terminal
    from prompt_toolkit.enums import EditingMode
    from prompt_toolkit.filters import Condition
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.key_binding.vi_state import InputMode

    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    KeyBindings = None
    Condition = None
    get_app = None
    PROMPT_TOOLKIT_AVAILABLE = False


def vi_normal_mode() -> bool:
    """True while the prompt is in vi NORMAL (navigation) mode."""
    if not PROMPT_TOOLKIT_AVAILABLE:
        return False
    try:
        app = get_app()
    except Exception:
        return False
    return app.editing_mode == EditingMode.VI and app.vi_state.input_mode == InputMode.NAVIGATION


def open_in_editor(buffer) -> None:
    """Edit the input in $VISUAL / $EDITOR (Notepad on Windows when neither is set)."""
    if os.name == "nt" and not (os.environ.get("VISUAL") or os.environ.get("EDITOR")):
        os.environ["EDITOR"] = "notepad"
    buffer.open_in_editor(validate_and_handle=False)


def create_key_bindings(interactive_mode) -> Optional[KeyBindings]:
    """Create key bindings for interactive mode."""
    if not PROMPT_TOOLKIT_AVAILABLE:
        return None

    kb = KeyBindings()
    vim_enabled = Condition(lambda: bool(getattr(interactive_mode, "vim_enabled", False)))

    @kb.add("c-c")
    def _(event):
        """Ctrl+C clears the input; on an empty prompt, twice in a row exits."""
        buffer = event.app.current_buffer
        if buffer.text:
            buffer.reset()
            interactive_mode.notice = ""
            return
        now = time.monotonic()
        if now - getattr(interactive_mode, "_last_ctrl_c", 0.0) < 2.0:
            event.app.exit(exception=KeyboardInterrupt)
            return
        interactive_mode._last_ctrl_c = now
        interactive_mode.notice = "Press Ctrl+C again to exit"
        event.app.invalidate()

    @kb.add("c-d")
    def _(event):
        """Ctrl+D on an empty prompt exits; otherwise deletes the next character."""
        buffer = event.app.current_buffer
        if buffer.text:
            buffer.delete()
        else:
            event.app.exit(exception=EOFError)

    @kb.add("escape", "enter")
    def _(event):
        """Alt+Enter (or Shift+Enter set up with /terminal-setup) inserts a new line."""
        event.current_buffer.insert_text("\n")

    @kb.add(
        "enter",
        filter=Condition(lambda: get_app().current_buffer.text.endswith("\\")),
    )
    def _(event):
        """A backslash at the end of the line continues on the next line."""
        buffer = event.current_buffer
        buffer.delete_before_cursor(1)
        buffer.insert_text("\n")

    @kb.add("c-g")
    def _(event):
        """Ctrl+G: write the prompt in your editor."""
        open_in_editor(event.current_buffer)

    @kb.add("escape", "v")
    def _(event):
        """Alt+V: attach the image in the clipboard."""
        from joshu.ui.clipboard import (
            ClipboardError,
            grab_clipboard_image,
            image_reference,
        )

        try:
            path = grab_clipboard_image()
        except ClipboardError as e:
            interactive_mode.notice = str(e)
            event.app.invalidate()
            return
        if path is None:
            interactive_mode.notice = "No image in the clipboard"
        else:
            event.current_buffer.insert_text(image_reference(path))
            interactive_mode.notice = ""
        event.app.invalidate()

    @kb.add("s-tab")
    def _(event):
        """Shift+Tab cycles default -> accept edits -> plan."""
        interactive_mode.cycle_mode()
        interactive_mode.notice = ""
        event.app.invalidate()

    @kb.add("c-o")
    def _(event):
        """Ctrl+O: the last request's tool output in full."""
        ui = getattr(interactive_mode, "agent_ui", None)
        if ui is not None:
            run_in_terminal(ui.show_expanded)

    @kb.add("c-l")
    def _(event):
        """Ctrl+L clears the screen, keeping what you typed."""
        event.app.renderer.clear()

    @kb.add("escape", filter=~vim_enabled)
    def _(event):
        """Esc clears the input (in vim mode it switches to NORMAL instead)."""
        buffer = event.app.current_buffer
        if buffer.complete_state:
            buffer.cancel_completion()
        else:
            buffer.reset()

    return kb
