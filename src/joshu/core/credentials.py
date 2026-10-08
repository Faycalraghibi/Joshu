"""
API keys saved by /login: ~/.joshu/.env (KEY=value lines), loaded at startup
after the environment and the project's .env (which win). The file is
readable only by its owner where the system allows it.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional


def credentials_path() -> Path:
    from joshu.core.paths import joshu_home

    return joshu_home() / ".env"


def _read(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip() and not key.strip().startswith("#"):
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _write(path: Path, values: Dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# API keys saved by Joshu's /login; remove one with /logout"]
    lines += [f"{key}={value}" for key, value in sorted(values.items())]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def save_key(variable: str, value: str) -> Path:
    """Save `variable=value` and set it in this process."""
    path = credentials_path()
    values = _read(path)
    values[variable] = value
    _write(path, values)
    os.environ[variable] = value
    return path


def remove_key(variable: str) -> bool:
    """Forget a saved key (and unset it here when it came from the file)."""
    path = credentials_path()
    values = _read(path)
    if variable not in values:
        return False
    saved = values.pop(variable)
    _write(path, values)
    if os.environ.get(variable) == saved:
        del os.environ[variable]
    return True


def saved_key(variable: str) -> Optional[str]:
    return _read(credentials_path()).get(variable)


def load_saved_keys() -> None:
    """Set the saved keys that aren't already set (environment and project .env win)."""
    for key, value in _read(credentials_path()).items():
        os.environ.setdefault(key, value)
