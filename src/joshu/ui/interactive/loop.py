"""
/loop: run a prompt again and again, every interval, for this session.

`/loop 5m check the CI and fix what broke` runs the prompt now, then again
5 minutes after each run ends (runs never overlap). The prompt waiting for
your input is interrupted when a run is due; what you typed is kept.
`/loop stop` ends it. One loop at a time.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Optional, Tuple

DEFAULT_SECONDS = 600
MIN_SECONDS = 30
MAX_SECONDS = 24 * 3600
_INTERVAL = re.compile(r"^(\d+)\s*([smh]?)$", re.I)
_UNIT = {"s": 1, "m": 60, "h": 3600, "": 60}  # a bare number means minutes


@dataclass
class Loop:
    prompt: str
    seconds: int
    next_at: float = field(default_factory=time.time)  # due at once when started
    runs: int = 0

    def due(self, now: Optional[float] = None) -> bool:
        return (time.time() if now is None else now) >= self.next_at

    def ran(self, now: Optional[float] = None) -> None:
        """A run finished: the next one is an interval from now."""
        self.runs += 1
        self.next_at = (time.time() if now is None else now) + self.seconds


def parse_interval(text: str) -> Optional[int]:
    """'30s', '5m', '2h' or '10' (minutes) -> seconds; None if it isn't an interval."""
    match = _INTERVAL.match(text.strip())
    if not match:
        return None
    return int(match.group(1)) * _UNIT[match.group(2).lower()]


def parse_loop_args(arg: str) -> Tuple[int, str]:
    """`[interval] <prompt>` -> (seconds, prompt); the interval defaults to 10 minutes."""
    first, _, rest = arg.strip().partition(" ")
    seconds = parse_interval(first)
    if seconds is None:
        return DEFAULT_SECONDS, arg.strip()
    return seconds, rest.strip()


def short_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    if seconds >= 3600 and seconds % 3600 == 0:
        return f"{seconds // 3600}h"
    if seconds >= 60:
        return f"{round(seconds / 60)}m"
    return f"{seconds}s"


def describe(loop: Loop, now: Optional[float] = None) -> str:
    """For the bar under the input: '⟳ every 5m · next in 3m'."""
    left = loop.next_at - (time.time() if now is None else now)
    nxt = "now" if left <= 0 else f"in {short_duration(left)}"
    return f"⟳ every {short_duration(loop.seconds)} · next {nxt}"
