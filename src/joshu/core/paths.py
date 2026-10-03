"""Where Joshu keeps per-user data."""

from __future__ import annotations

import os
from pathlib import Path


def joshu_home() -> Path:
    """
    Joshu's per-user data directory: ~/.joshu, or $JOSHU_HOME.

    Sessions, input history, memory and semantic-memory data live here, so
    running Joshu never leaves files in the project directory.
    """
    return Path(os.getenv("JOSHU_HOME") or Path.home() / ".joshu")
