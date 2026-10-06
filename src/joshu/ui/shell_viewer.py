"""
The background shells viewer: commands the agent started with
`background: true`, and the live output of one.

List: arrows move, Enter shows the output, k stops the command, Esc closes.
Output: follows the end while the command writes; k stops it, Esc goes back.
Opened with Down on an empty prompt (the bottom bar says when shells run) or
/bashes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, List, Optional, Tuple

from joshu.tools.shell_tool import (
    ProcessInfo,
    list_background_processes,
    peek_process_output,
    stop_background_process,
)

Fragments = List[Tuple[str, str]]

LIST_KEYS = "↑/↓ select · enter view output · k stop · esc close"
OUTPUT_KEYS = "k stop · esc back"


def elapsed_since(started_at: str, now: Optional[datetime] = None) -> str:
    """'4s', '2m 05s', '1h 03m' since an ISO timestamp."""
    try:
        seconds = int(
            ((now or datetime.now()) - datetime.fromisoformat(started_at)).total_seconds()
        )
    except ValueError:
        return ""
    seconds = max(0, seconds)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60:02d}s"
    return f"{seconds // 3600}h {seconds % 3600 // 60:02d}m"


def _state(info: ProcessInfo) -> Tuple[str, str]:
    code = info.process.poll()
    if code is None:
        return "class:running", f"● running {elapsed_since(info.started_at)}"
    return "class:exited", f"○ exited {code}"


def _fit(text: str, width: int) -> str:
    return text if len(text) <= width else text[: max(0, width - 1)] + "…"


class ShellViewer:
    """What the viewer shows and how keys change it (drawn by run_viewer)."""

    def __init__(self, processes: Callable[[], List[ProcessInfo]] = list_background_processes):
        self.processes = processes
        self.index = 0
        self.opened: Optional[str] = None  # process_id whose output is shown
        self.message = ""

    # ------------------------------------------------------------- keys

    def selected(self) -> Optional[ProcessInfo]:
        processes = self.processes()
        if self.opened is not None:
            return next((p for p in processes if p.process_id == self.opened), None)
        if not processes:
            return None
        self.index = min(self.index, len(processes) - 1)
        return processes[self.index]

    def move(self, step: int) -> None:
        count = len(self.processes())
        if self.opened is None and count:
            self.index = (self.index + step) % count

    def enter(self) -> None:
        info = self.selected()
        if info is not None:
            self.opened = info.process_id
            self.message = ""

    def back(self) -> bool:
        """Esc: from the output to the list; True when the viewer should close."""
        if self.opened is not None:
            self.opened = None
            return False
        return True

    def kill(self) -> None:
        info = self.selected()
        if info is None:
            return
        result = stop_background_process(info.process_id)
        self.message = str(result.get("message") or result.get("error") or "")
        self.opened = None

    # ----------------------------------------------------------- render

    def render(self, width: int, height: int) -> Fragments:
        if self.opened is not None:
            info = self.selected()
            if info is not None:
                return self._render_output(info, width, height)
            self.opened = None
        return self._render_list(width)

    def _render_list(self, width: int) -> Fragments:
        out: Fragments = [("class:title", " Background shells\n\n")]
        processes = self.processes()
        if not processes:
            out.append(("", " No background commands.\n"))
        for number, info in enumerate(processes):
            pointer = "❯" if number == self.index else " "
            state_style, state = _state(info)
            line_style = "class:selected" if number == self.index else ""
            out += [
                (line_style, f" {pointer} {info.process_id}  "),
                (state_style, f"{state:<20}"),
                (line_style, _fit(info.command, max(10, width - 36)) + "\n"),
            ]
        if self.message:
            out.append(("class:message", f"\n {self.message}\n"))
        out.append(("class:hint", f"\n {LIST_KEYS}"))
        return out

    def _render_output(self, info: ProcessInfo, width: int, height: int) -> Fragments:
        state_style, state = _state(info)
        rule = "─" * max(1, width - 1)
        body_rows = max(1, height - 5)
        lines = peek_process_output(info).splitlines() or ["(no output yet)"]
        shown = [_fit(line, width - 2) for line in lines[-body_rows:]]
        return [
            ("class:title", f" {info.process_id}  "),
            (state_style, state),
            ("", "  " + _fit(info.command, max(10, width - 40)) + "\n"),
            ("class:rule", f"{rule}\n"),
            ("", "".join(f" {line}\n" for line in shown)),
            ("class:rule", f"{rule}\n"),
            ("class:hint", f" {OUTPUT_KEYS}"),
        ]


def run_viewer(viewer: Optional[ShellViewer] = None, **app_options: Any) -> None:
    """Show the viewer full screen until Esc (redrawn twice a second)."""
    from prompt_toolkit.application import Application, get_app
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Layout, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.styles import Style

    viewer = viewer or ShellViewer()
    keys = KeyBindings()
    keys.add("up")(lambda event: viewer.move(-1))
    keys.add("down")(lambda event: viewer.move(1))
    keys.add("enter")(lambda event: viewer.enter())
    keys.add("k")(lambda event: viewer.kill())

    @keys.add("escape", eager=True)
    @keys.add("q")
    @keys.add("left")
    def _(event):
        if viewer.back():
            event.app.exit()

    @keys.add("c-c")
    def _(event):
        event.app.exit()

    def text():
        size = get_app().output.get_size()
        return viewer.render(size.columns, size.rows)

    style = Style.from_dict(
        {
            "title": "bold",
            "running": "ansigreen",
            "exited": "ansibrightblack",
            "selected": "bold",
            "rule": "ansibrightblack",
            "hint": "ansibrightblack",
            "message": "ansiyellow",
        }
    )
    app: Application = Application(
        layout=Layout(Window(FormattedTextControl(text, focusable=True), wrap_lines=False)),
        key_bindings=keys,
        style=style,
        full_screen=True,
        refresh_interval=0.5,
        **app_options,
    )
    app.run()
