"""
Arrow-key menus where a number key picks its option at once and Esc cancels.

prompt_toolkit's `choice()` numbers the options, but its number keys only move
the selection (Enter still has to be pressed), and key bindings passed to it
sit below the focused list's own, so they can't change that. These menus add
their keys to the list itself.
"""

from __future__ import annotations

from typing import Any, Sequence, Tuple


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
    """
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
    app = chooser._create_application()
    control = app.layout.current_control
    # Bindings merged later win over the list's own (which only select)
    control.key_bindings = (
        merge_key_bindings([control.key_bindings, keys]) if control.key_bindings else keys
    )
    return app.run()
