"""
Keys pressed while the agent is working.

Esc interrupts the running request the same way Ctrl+C does (the agent keeps
the conversation valid, so you can follow up). Anything else typed meanwhile
is kept and offered as the start of the next prompt, so you can type ahead.

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
from typing import Iterator, List, Optional

ESC = "\x1b"
POLL_SECONDS = 0.05

_active: Optional["KeyListener"] = None


class KeyListener:
    """Watch for Esc and collect type-ahead while a request runs."""

    def __init__(self) -> None:
        self.interrupted = False
        self._typed: List[str] = []
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
                self._add(key)

    def _add(self, key: str) -> None:
        if key in ("\x08", "\x7f"):
            if self._typed:
                self._typed.pop()
        elif key in ("\r", "\n"):
            self._typed.append(" ")
        elif key.isprintable():
            self._typed.append(key)

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
                msvcrt.getwch()  # second half of an arrow / function key
                return None
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
        # A lone Esc, or the start of a sequence like ESC [ A
        more, _, _ = select.select([fd], [], [], 0.03)
        if more:
            os.read(fd, 16)
            return None
    return key
