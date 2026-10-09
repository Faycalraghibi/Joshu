"""
Keys pressed while the agent is working.

Esc interrupts the running request the same way Ctrl+C does (the agent keeps
the conversation valid, so you can follow up). Anything else typed meanwhile
is kept and offered as the start of the next prompt, so you can type ahead;
it shows in the input box under the working line, where ←/→, Home/End
(Ctrl+A/Ctrl+E), Delete and Ctrl+U (clear) edit it. Enter on `/btw <question>` asks a side
question right away (see `on_submit`) while the request keeps running.

The listener reads the terminal on a background thread and only runs while
the agent runs. Approval prompts pause it (see `paused`) so they can read
their answer normally. It does nothing when stdin isn't a terminal.
"""

from __future__ import annotations

import _thread
import contextlib
import os
import sys
import threading
from typing import Callable, Dict, Iterator, List, Optional

ESC = "\x1b"
CTRL_O = "\x0f"
CTRL_B = "\x02"
POLL_SECONDS = 0.05

# Editing keys, as _read_key reports them
LEFT, RIGHT, HOME, END, DELETE = "<left>", "<right>", "<home>", "<end>", "<delete>"
CTRL_A, CTRL_E, CTRL_U = "\x01", "\x05", "\x15"
_WINDOWS_KEYS = {"K": LEFT, "M": RIGHT, "G": HOME, "O": END, "S": DELETE}
_ESCAPE_KEYS = {
    "[D": LEFT,
    "[C": RIGHT,
    "[H": HOME,
    "OH": HOME,
    "[1~": HOME,
    "[F": END,
    "OF": END,
    "[4~": END,
    "[3~": DELETE,
}

_active: Optional["KeyListener"] = None


class KeyListener:
    """Watch for Esc and collect type-ahead while a request runs."""

    def __init__(
        self,
        actions: Optional[Dict[str, Callable[[], None]]] = None,
        on_submit: Optional[Callable[[str], bool]] = None,
    ) -> None:
        """
        Args:
            actions: Keys that run a callback instead of being typed ahead,
                e.g. {CTRL_O: show_more}
            on_submit: Called with the typed line when Enter is pressed; True
                means it was handled (e.g. /btw) and the line is cleared
        """
        self.actions = actions or {}
        self.on_submit = on_submit
        self.interrupted = False
        self._typed: List[str] = []
        self._cursor = 0  # where the next key goes in _typed
        self._stop = threading.Event()
        self._running = threading.Event()  # set while reading keys (not paused)
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._term_state = None

    @property
    def typed(self) -> str:
        """Text typed while the request ran (one line; Enter becomes a space)."""
        with self._lock:
            return "".join(self._typed).strip()

    # ---------------------------------------------------------------- control

    def __enter__(self) -> "KeyListener":
        global _active
        if not _is_terminal():
            return self
        _active = self
        self._enter_raw()
        self._running.set()
        self._thread = threading.Thread(target=self._loop, name="joshu-keys", daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        global _active
        if _active is self:
            _active = None
        self._stop.set()
        self._running.set()  # let a paused loop see the stop
        if self._thread is not None:
            self._thread.join(timeout=1)
        self._leave_raw()

    @contextlib.contextmanager
    def pause(self) -> Iterator[None]:
        """Stop reading keys (and restore normal terminal input) for a while."""
        if self._thread is None:
            yield
            return
        self._running.clear()
        # Wait for the loop to finish its current poll before handing stdin over
        with self._lock:
            self._leave_raw()
        try:
            yield
        finally:
            self._enter_raw()
            self._running.set()

    # ------------------------------------------------------------------- loop

    def _loop(self) -> None:
        while not self._stop.is_set():
            if not self._running.wait(timeout=POLL_SECONDS):
                continue
            with self._lock:
                if not self._running.is_set() or self._stop.is_set():
                    continue
                key = _read_key(POLL_SECONDS)
                if key is None:
                    continue
                if key in (ESC, "\x03"):
                    self.interrupted = True
                    self._stop.set()
                    _thread.interrupt_main()
                    return
                action = self.actions.get(key)
                if action is not None:
                    try:
                        action()
                    except Exception:  # a display toggle must never stop the request
                        pass
                    continue
                self._add(key)

    def _add(self, key: str) -> None:
        typed = self._typed
        if key in ("\x08", "\x7f"):
            if self._cursor > 0:
                self._cursor -= 1
                typed.pop(self._cursor)
        elif key == DELETE:
            if self._cursor < len(typed):
                typed.pop(self._cursor)
        elif key == LEFT:
            self._cursor = max(0, self._cursor - 1)
        elif key == RIGHT:
            self._cursor = min(len(typed), self._cursor + 1)
        elif key in (HOME, CTRL_A):
            self._cursor = 0
        elif key in (END, CTRL_E):
            self._cursor = len(typed)
        elif key == CTRL_U:
            typed.clear()
            self._cursor = 0
        elif key in ("\r", "\n"):
            line = "".join(typed).strip()
            if self.on_submit is not None and line:
                try:
                    handled = self.on_submit(line)
                except Exception:  # a side question must never stop the request
                    handled = False
                if handled:
                    typed.clear()
                    self._cursor = 0
                    return
            typed.append(" ")
            self._cursor = len(typed)
        elif len(key) == 1 and key.isprintable():
            typed.insert(self._cursor, key)
            self._cursor += 1

    # --------------------------------------------------------------- terminal

    def _enter_raw(self) -> None:
        if os.name == "nt" or self._term_state is not None:
            return
        import termios
        import tty

        fd = sys.stdin.fileno()
        self._term_state = termios.tcgetattr(fd)
        # cbreak: keys arrive one by one without echo; Ctrl+C still sends SIGINT
        tty.setcbreak(fd)
        attrs = termios.tcgetattr(fd)
        attrs[3] &= ~termios.ECHO
        termios.tcsetattr(fd, termios.TCSANOW, attrs)

    def _leave_raw(self) -> None:
        if os.name == "nt" or self._term_state is None:
            return
        import termios

        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self._term_state)
        self._term_state = None


def listening() -> bool:
    """Whether keys typed now are read (a request runs in interactive mode)."""
    listener = _active
    return listener is not None and listener._thread is not None


def typing_now() -> str:
    """What has been typed during the running request so far (for display)."""
    listener = _active
    if listener is None:
        return ""
    return "".join(listener._typed)


def typing_cursor() -> int:
    """Where the cursor is in typing_now() (for display)."""
    listener = _active
    return listener._cursor if listener is not None else 0


@contextlib.contextmanager
def paused() -> Iterator[None]:
    """Pause the active listener, if any (for prompts that read stdin)."""
    listener = _active
    if listener is None:
        yield
    else:
        with listener.pause():
            yield


def _is_terminal() -> bool:
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except (AttributeError, ValueError):
        return False


def _read_key(timeout: float) -> Optional[str]:
    """One key, or None if none arrived within `timeout`. Escape sequences
    (arrow keys and the like) are swallowed so they don't count as Esc."""
    if os.name == "nt":
        return _read_key_windows(timeout)
    return _read_key_posix(timeout)


def _read_key_windows(timeout: float) -> Optional[str]:
    import msvcrt
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if msvcrt.kbhit():
            key = msvcrt.getwch()
            if key in ("\x00", "\xe0"):
                # An arrow or function key comes in two halves
                return _WINDOWS_KEYS.get(msvcrt.getwch())
            return key
        time.sleep(0.01)
    return None


def _read_key_posix(timeout: float) -> Optional[str]:
    import select

    fd = sys.stdin.fileno()
    ready, _, _ = select.select([fd], [], [], timeout)
    if not ready:
        return None
    key = os.read(fd, 1).decode("utf-8", errors="ignore")
    if key == ESC:
        # A lone Esc, or the start of a sequence like ESC [ D (left arrow)
        more, _, _ = select.select([fd], [], [], 0.03)
        if more:
            sequence = os.read(fd, 16).decode("utf-8", errors="ignore")
            return _ESCAPE_KEYS.get(sequence)
    return key
