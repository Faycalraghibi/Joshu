"""
Custom status line: the output of a command you choose, shown under the input.

Set it with `/statusline <command>` (the `statusline` setting). The command gets
a JSON object on stdin (model, cwd, mode, session_id, theme) and its first
line of output is shown at the right of the hint line. It runs at most every
few seconds, with a short timeout, so a slow command can't stall typing.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

REFRESH_SECONDS = 5.0
TIMEOUT_SECONDS = 1.0
MAX_CHARS = 120
_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


class StatusLine:
    """Runs the status line command and caches its output."""

    def __init__(self, refresh: float = REFRESH_SECONDS, timeout: float = TIMEOUT_SECONDS):
        self.refresh = refresh
        self.timeout = timeout
        self._command: Optional[str] = None
        self._text = ""
        self._at = 0.0

    def text(self, command: Optional[str], context: Dict[str, Any]) -> str:
        """The status line for `command` ("" when unset or failing)."""
        if not command:
            return ""
        now = time.monotonic()
        if command == self._command and now - self._at < self.refresh:
            return self._text
        self._command, self._at = command, now
        self._text = run_statusline(command, context, self.timeout)
        return self._text

    def reset(self) -> None:
        self._command = None


def run_statusline(command: str, context: Dict[str, Any], timeout: float = TIMEOUT_SECONDS) -> str:
    try:
        result = subprocess.run(
            command,
            shell=True,
            input=json.dumps(context),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as e:
        logger.debug(f"Status line command failed: {e}")
        return ""
    lines = [line for line in _ANSI.sub("", result.stdout).splitlines() if line.strip()]
    if not lines:
        return ""
    text = " ".join(lines[0].split())
    return text if len(text) <= MAX_CHARS else text[: MAX_CHARS - 1] + "…"
