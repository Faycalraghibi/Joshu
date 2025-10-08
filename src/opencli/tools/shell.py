from __future__ import annotations

import subprocess
from typing import Tuple


def run_command(command: str, timeout: int = 60) -> Tuple[int, str, str]:
    result = subprocess.run(
        command, shell=True, capture_output=True, text=True, timeout=timeout
    )
    return result.returncode, result.stdout, result.stderr


