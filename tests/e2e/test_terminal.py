"""
The interactive prompt in a real pseudo-terminal: keys go in as bytes, the
screen comes back as text. Uses ConPTY (pywinpty) on Windows and pexpect
elsewhere; skipped when neither is installed.
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
from pathlib import Path
from typing import Any, List, Optional

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

    def __init__(self, home: Path, script: Optional[List[Any]] = None) -> None:
        env = dict(
            os.environ,
            PYTHONPATH=str(ROOT / "src"),
            PYTHONIOENCODING="utf-8",
            JOSHU_HOME=str(home),
            TERM="xterm-256color",
        )
        self._chunks: list[str] = []
        argv = [sys.executable, "-c", START]
        if script is not None:
            # A scripted model (see scripted_joshu.py) instead of a real one
            (home / "script.json").write_text(json.dumps(script), encoding="utf-8")
            env["JOSHU_TEST_SCRIPT"] = str(home / "script.json")
            argv = [sys.executable, str(Path(__file__).with_name("scripted_joshu.py"))]
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

    def rendered(self) -> str:
        """The screen as a terminal draws it (cursor moves applied), scrollback included."""
        pyte = pytest.importorskip("pyte")
        screen = pyte.HistoryScreen(120, 40, history=5000)
        pyte.Stream(screen).feed("".join(self._chunks))
        history = ["".join(char.data for char in line.values()) for line in screen.history.top]
        return "\n".join(line.rstrip() for line in history + screen.display)

    def mark(self) -> int:
        return len(self.screen)

    def wait_for(self, text: str, since: int = 0, seconds: float = 20) -> bool:
        deadline = time.time() + seconds
        while time.time() < deadline:
            if text in self.screen[since:]:
                return True
            time.sleep(0.1)
        return False

    def wait_drawn(self, text: str, seconds: float = 20) -> bool:
        """Like wait_for, on the drawn screen (text that redraws went over is gone)."""
        deadline = time.time() + seconds
        while time.time() < deadline:
            if text in self.rendered():
                return True
            time.sleep(0.3)
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


def scripted(tmp_path, script, config=""):
    (tmp_path / "config.yaml").write_text("mcp_enabled: false\n" + config, encoding="utf-8")
    term = Terminal(tmp_path, script)
    # The placeholder shows in every permission mode
    assert term.wait_for("explain this codebase", seconds=60), term.screen[-2000:]
    return term


def ask(question, options, multi=False):
    return {
        "tool_calls": [
            {
                "name": "ask_user",
                "arguments": {
                    "questions": [
                        {
                            "question": question,
                            "options": [{"label": o} for o in options],
                            "multi_select": multi,
                        }
                    ]
                },
            }
        ]
    }


def test_questions_with_choices(tmp_path):
    script = [
        ask("Which database?", ["Postgres", "SQLite"]),
        ask("Which extras?", ["Docker", "CI", "Docs"], multi=True),
        {"content": "Setting it up."},
    ]
    term = scripted(tmp_path, script)
    try:
        term.send("set up the project\r", pause=1.0)
        assert term.wait_for("Which database?"), term.screen[-2000:]
        mark = term.mark()
        term.send("2", pause=1.0)  # a number picks at once
        assert term.wait_for("SQLite", mark), term.screen[-2000:]
        assert term.wait_for("Which extras?", mark), term.screen[-2000:]
        mark = term.mark()
        term.send("1", pause=0.4)
        term.send("3", pause=0.4)
        term.send("\r", pause=1.0)
        assert term.wait_for("Docker, Docs", mark), term.screen[-2000:]
        assert term.wait_for("Setting it up.", mark), term.screen[-2000:]
    finally:
        term.close()


def test_approval_menu_and_diff(tmp_path):
    (tmp_path / "app.py").write_text("def total(items):\n    return sum(items)\n", encoding="utf-8")
    script = [
        {
            "tool_calls": [
                {
                    "name": "replace",
                    "arguments": {
                        "path": "app.py",
                        "old_string": "    return sum(items)",
                        "new_string": "    return round(sum(items), 2)",
                    },
                }
            ]
        },
        {"content": "Rounded."},
    ]
    term = scripted(tmp_path, script)
    try:
        term.send("round the total\r", pause=1.0)
        assert term.wait_for("Yes"), term.screen[-2000:]  # the approval menu
        term.send("1", pause=1.0)
        assert term.wait_drawn("Rounded."), term.rendered()[-3000:]
        shown = term.rendered()
        assert "⎿  Updated app.py with 1 addition and 1 removal" in shown, shown
        assert (
            "2 -     return sum(items)" in shown and "2 +     return round(sum(items), 2)" in shown
        )
        assert "round(sum(items), 2)" in (tmp_path / "app.py").read_text(encoding="utf-8")
    finally:
        term.close()


def test_background_shell_viewer(tmp_path):
    talk = "import time\nfor i in range(300):\n    print(f'tick {i}', flush=True)\n    time.sleep(0.2)\n"
    (tmp_path / "talk.py").write_text(talk, encoding="utf-8")
    script = [
        {
            "tool_calls": [
                {
                    "name": "run_shell_command",
                    "arguments": {"command": f'"{sys.executable}" talk.py', "background": True},
                }
            ]
        },
        {"content": "Started it."},
    ]
    term = scripted(tmp_path, script, config="permission_mode: bypass\n")
    try:
        term.send("start the ticker\r", pause=1.0)
        assert term.wait_for("Started it."), term.screen[-2000:]
        assert term.wait_for("1 shell · ↓ to view"), term.screen[-2000:]
        mark = term.mark()
        term.send("\x1b[B", pause=1.5)  # Down on the empty prompt
        assert term.wait_for("Background shells", mark), term.screen[-2000:]
        mark = term.mark()
        term.send("\r", pause=2.0)
        assert term.wait_for("tick ", mark), term.screen[-2000:]
        mark = term.mark()
        term.send("k", pause=1.5)
        assert term.wait_for("Background shells", mark), term.screen[-2000:]
        term.send("\x1b", pause=1.0)
        mark = term.mark()
        term.send("?\r")
        assert term.wait_for("ctrl+o", mark), term.screen[-2000:]  # back at the prompt
    finally:
        term.close()
