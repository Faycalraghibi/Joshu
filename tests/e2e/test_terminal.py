"""
The interactive prompt in a real pseudo-terminal: keys go in as bytes, the
screen comes back as text. Uses ConPTY (pywinpty) on Windows and pexpect
elsewhere; skipped when neither is installed.
"""

from __future__ import annotations

import os
import re
import sys
import threading
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("JOSHU_SKIP_TERMINAL_TESTS") == "1", reason="terminal tests disabled"
)

if os.name == "nt":
    winpty = pytest.importorskip("winpty")
else:
    pexpect = pytest.importorskip("pexpect")

ROOT = Path(__file__).resolve().parents[2]
START = (
    "from joshu.ui.interactive.interactive_mode import InteractiveMode; "
    "InteractiveMode('test-model').start()"
)
ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07]*\x07|\x1b[=>()][0-9A-Za-z]?")


class Terminal:
    """Joshu's prompt running in a pseudo-terminal."""

    def __init__(self, home: Path) -> None:
        env = dict(
            os.environ,
            PYTHONPATH=str(ROOT / "src"),
            PYTHONIOENCODING="utf-8",
            JOSHU_HOME=str(home),
            TERM="xterm-256color",
        )
        self._chunks: list[str] = []
        argv = [sys.executable, "-c", START]
        if os.name == "nt":
            self._process = winpty.PtyProcess.spawn(
                argv, cwd=str(home), env=env, dimensions=(40, 120)
            )
        else:
            self._process = pexpect.spawn(
                argv[0],
                argv[1:],
                cwd=str(home),
                env=env,
                dimensions=(40, 120),
                encoding="utf-8",
            )
        threading.Thread(target=self._reader, daemon=True).start()
        if os.name == "nt":
            time.sleep(0.5)
            self._process.write("\x1b[?1;0c")  # answer ConPTY's device-attributes query

    def _reader(self) -> None:
        while True:
            try:
                if os.name == "nt":
                    data = self._process.read(4096)
                else:
                    data = self._process.read_nonblocking(4096, timeout=None)
            except Exception:  # EOF or the process ended
                return
            self._chunks.append(data)
            if "\x1b[6n" in data:  # cursor position query
                self.send("\x1b[1;1R", pause=0)

    @property
    def screen(self) -> str:
        return ANSI.sub("", "".join(self._chunks))

    def mark(self) -> int:
        return len(self.screen)

    def wait_for(self, text: str, since: int = 0, seconds: float = 20) -> bool:
        deadline = time.time() + seconds
        while time.time() < deadline:
            if text in self.screen[since:]:
                return True
            time.sleep(0.1)
        return False

    def send(self, keys: str, pause: float = 0.5) -> None:
        if os.name == "nt":
            self._process.write(keys)
        else:
            self._process.send(keys)
        time.sleep(pause)

    def alive(self) -> bool:
        return self._process.isalive()

    def close(self) -> None:
        if self.alive():
            if os.name == "nt":
                self._process.terminate(force=True)
            else:
                self._process.terminate(force=True)


@pytest.fixture
def terminal(tmp_path):
    term = Terminal(tmp_path)
    assert term.wait_for("? for shortcuts", seconds=60), term.screen[-2000:]
    yield term
    term.close()


def test_keys_in_a_real_terminal(terminal):
    mark = terminal.mark()
    terminal.send("?\r")
    assert terminal.wait_for("ctrl+o", mark), terminal.screen[-2000:]

    # Ctrl+D with text in the prompt deletes a character instead of exiting
    terminal.send("abc\x01\x04", pause=1.0)
    assert terminal.alive()
    terminal.send("\x03")

    mark = terminal.mark()
    terminal.send("\x0f")
    assert terminal.wait_for("No tool output yet", mark), terminal.screen[-2000:]

    # Vim mode: "/xcost", Esc, 0, l, x gives "/cost"
    terminal.send("/vim\r", pause=1.5)
    mark = terminal.mark()
    terminal.send("/xcost\x1b", pause=0.8)
    terminal.send("0lx", pause=0.6)
    terminal.send("\r", pause=1.0)
    assert terminal.wait_for("N /cost", mark), terminal.screen[-2000:]

    # Ctrl+D on an empty prompt exits
    terminal.send("\x04", pause=0)
    deadline = time.time() + 10
    while terminal.alive() and time.time() < deadline:
        time.sleep(0.1)
    assert not terminal.alive()
