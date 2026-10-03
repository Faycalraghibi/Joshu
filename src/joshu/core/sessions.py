"""
Saved agent conversations.

Each conversation is stored as JSON under ~/.joshu/sessions (or
$JOSHU_HOME/sessions) after every request, so it can be resumed later with
`--resume <id>`, `--continue` or `/resume`.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from joshu.core.agent import Agent

logger = logging.getLogger(__name__)

SESSION_VERSION = 1


class SessionError(Exception):
    """A session can't be found or read."""


@dataclass
class SessionInfo:
    """Summary of a saved session."""

    id: str
    title: str
    cwd: str
    model: str
    created_at: str
    updated_at: str
    message_count: int


def joshu_home() -> Path:
    """Joshu's per-user data directory (~/.joshu, or $JOSHU_HOME)."""
    return Path(os.getenv("JOSHU_HOME") or Path.home() / ".joshu")


def sessions_dir() -> Path:
    return joshu_home() / "sessions"


def save_session(agent: "Agent") -> Path:
    """Write the agent's conversation (without the system prompt) to disk."""
    messages = agent.messages[1:]
    title = next(
        (m["content"] for m in messages if m.get("role") == "user" and m.get("content")), ""
    )
    data = {
        "version": SESSION_VERSION,
        "id": agent.session_id,
        "title": " ".join(title.split())[:100],
        "cwd": str(agent.cwd),
        "model": getattr(agent.client, "model", ""),
        "created_at": agent.created_at,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "usage": dict(agent.usage),
        "messages": messages,
    }

    directory = sessions_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{agent.session_id}.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)
    return path


def load_session(session_id: str) -> Dict[str, Any]:
    """
    Load a saved session by id (a unique prefix is enough).

    Raises:
        SessionError: when no session, or more than one, matches.
    """
    directory = sessions_dir()
    exact = directory / f"{session_id}.json"
    if exact.is_file():
        return _read(exact)

    matches = sorted(directory.glob(f"{session_id}*.json")) if session_id else []
    if not matches:
        raise SessionError(f"No saved session '{session_id}'. List them with `joshu sessions`.")
    if len(matches) > 1:
        ids = ", ".join(p.stem for p in matches[:5])
        raise SessionError(f"'{session_id}' matches several sessions ({ids}); use more of the id.")
    return _read(matches[0])


def list_sessions(cwd: Optional[Path] = None, limit: int = 20) -> List[SessionInfo]:
    """Saved sessions, most recently updated first; only those for `cwd` if given."""
    directory = sessions_dir()
    if not directory.is_dir():
        return []

    infos = []
    for path in directory.glob("*.json"):
        try:
            data = _read(path)
        except SessionError:
            continue
        if cwd is not None and Path(data.get("cwd", "")) != Path(cwd):
            continue
        infos.append(
            SessionInfo(
                id=data["id"],
                title=data.get("title", ""),
                cwd=data.get("cwd", ""),
                model=data.get("model", ""),
                created_at=data.get("created_at", ""),
                updated_at=data.get("updated_at", ""),
                message_count=len(data.get("messages", [])),
            )
        )
    infos.sort(key=lambda info: info.updated_at, reverse=True)
    return infos[:limit]


def latest_session(cwd: Path) -> Optional[SessionInfo]:
    """The most recently updated session started in `cwd`."""
    sessions = list_sessions(cwd, limit=1)
    return sessions[0] if sessions else None


def _read(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise SessionError(f"Could not read session {path.name}: {e}") from e
    if not isinstance(data, dict) or "id" not in data or "messages" not in data:
        raise SessionError(f"{path.name} is not a Joshu session")
    return data
