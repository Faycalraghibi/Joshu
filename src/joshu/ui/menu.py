"""
Arrow-key menus where a number key picks its option at once and Esc cancels.

prompt_toolkit's `choice()` numbers the options, but its number keys only move
the selection (Enter still has to be pressed), and key bindings passed to it
sit below the focused list's own, so they can't change that. These menus add
their keys to the list itself.
"""

from __future__ import annotations

import sys
from typing import Any, Sequence, Tuple


class MenuUnavailable(RuntimeError):
    """The terminal can't show an arrow-key menu (not a console, or output redirected)."""


def can_show_menu() -> bool:
    """True when both input and output are a terminal (menus need to draw and read keys)."""
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except (AttributeError, ValueError):
        return False


def menu(
    question: Any,
    options: Sequence[Tuple[Any, Any]],
    *,
    cancel: Any = None,
    default: Any = None,
) -> Any:
    """
    Show `options` ((value, label) pairs) and return the chosen value.

    `cancel` is returned for Esc; Ctrl+C raises KeyboardInterrupt as usual.
    Raises MenuUnavailable when the terminal can't show it; callers then fall
    back to text.
    """
    if not can_show_menu():
        raise MenuUnavailable("not a terminal")
    from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings
    from prompt_toolkit.shortcuts.choice_input import ChoiceInput

    keys = KeyBindings()

    @keys.add("escape", eager=True)
    def _(event):
        event.app.exit(result=cancel)

    for number, (value, _label) in enumerate(options[:9], start=1):

        def pick(event, value=value):
            event.app.exit(result=value)

        keys.add(str(number), eager=True)(pick)

    chooser = ChoiceInput(message=question, options=list(options), default=default, symbol="❯")
    try:
        app = chooser._create_application()
    except Exception as e:  # e.g. a Windows pipe or mintty instead of a console
        raise MenuUnavailable(str(e)) from e
    control = app.layout.current_control
    # Bindings merged later win over the list's own (which only select)
    control.key_bindings = (
        merge_key_bindings([control.key_bindings, keys]) if control.key_bindings else keys
    )
    return app.run()


def multi_menu(question: Any, options: Sequence[Tuple[Any, Any]], *, cancel: Any = None) -> Any:
    """
    A checkbox list: arrows move, Space (or a number key) toggles, Enter
    confirms. Returns the chosen values in option order, or `cancel` for Esc.
    Raises MenuUnavailable when the terminal can't show it.
    """
    if not can_show_menu():
        raise MenuUnavailable("not a terminal")
    from prompt_toolkit.application import Application
    from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings
    from prompt_toolkit.layout import HSplit, Layout
    from prompt_toolkit.widgets import CheckboxList, Label

    checkboxes = CheckboxList(values=list(options))
    keys = KeyBindings()

    @keys.add("enter", eager=True)
    def _(event):
        chosen = set(checkboxes.current_values)
        event.app.exit(result=[value for value, _label in options if value in chosen])

    @keys.add("escape", eager=True)
    def _(event):
        event.app.exit(result=cancel)

    @keys.add("c-c", eager=True)
    def _(event):
        event.app.exit(exception=KeyboardInterrupt)

    for number, (value, _label) in enumerate(options[:9], start=1):

        def toggle(event, value=value):
            if value in checkboxes.current_values:
                checkboxes.current_values.remove(value)
            else:
                checkboxes.current_values.append(value)

        keys.add(str(number), eager=True)(toggle)

    control = checkboxes.control
    control.key_bindings = (
        merge_key_bindings([control.key_bindings, keys]) if control.key_bindings else keys
    )
    hint = Label(text="  space to select, enter to confirm, esc to skip", style="class:hint")
    body = HSplit([Label(text=question), checkboxes, hint])
    try:
        app = Application(layout=Layout(body, focused_element=checkboxes), full_screen=False)
    except Exception as e:  # e.g. a Windows pipe or mintty instead of a console
        raise MenuUnavailable(str(e)) from e
    return app.run()
