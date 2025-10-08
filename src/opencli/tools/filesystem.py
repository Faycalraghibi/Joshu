from __future__ import annotations

from pathlib import Path
from typing import List


def list_python_files(root: str) -> List[str]:
    return [str(p) for p in Path(root).rglob("*.py")]


