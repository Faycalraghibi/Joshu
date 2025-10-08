from __future__ import annotations

import subprocess
from typing import Tuple


def run_command(command: str, timeout: int = 60) -> Tuple[int, str, str]:
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=timeout,
            encoding='utf-8', errors='replace'  # Handle encoding issues
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return -1, "", str(e)