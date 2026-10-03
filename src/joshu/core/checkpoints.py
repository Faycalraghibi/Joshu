"""
Undo for the agent's file edits.

Before an edit tool changes a file, its original bytes (or the fact that it did
not exist) are recorded in the checkpoint for the current request. Undoing a
checkpoint puts every recorded file back. Changes made through shell commands
are not tracked.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Checkpoint:
    """Original state of the files changed while handling one request."""

    prompt: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    # Absolute path -> original bytes, or None if the file did not exist
    files: Dict[Path, Optional[bytes]] = field(default_factory=dict)


class CheckpointStore:
    """Checkpoints for one conversation, newest last."""

    def __init__(self) -> None:
        self.checkpoints: List[Checkpoint] = []
        self._pending: Optional[Checkpoint] = None

    def begin(self, prompt: str) -> None:
        """Start the checkpoint for a new request (kept only if something is edited)."""
        self._pending = Checkpoint(prompt=prompt)

    def snapshot(self, path: Path) -> None:
        """Record a file's current state before it is changed (once per request)."""
        if self._pending is None:
            self.begin("")
        checkpoint = self._pending
        path = path.resolve()
        if path in checkpoint.files:
            return

        try:
            original = path.read_bytes() if path.is_file() else None
        except OSError as e:
            logger.warning(f"Could not snapshot {path}: {e}")
            return

        checkpoint.files[path] = original
        if not self.checkpoints or self.checkpoints[-1] is not checkpoint:
            self.checkpoints.append(checkpoint)

    def undo(self) -> Optional[Checkpoint]:
        """
        Restore the files of the most recent checkpoint.

        Returns:
            The undone checkpoint, or None when there is nothing to undo.
        """
        if not self.checkpoints:
            return None

        checkpoint = self.checkpoints.pop()
        if checkpoint is self._pending:
            self._pending = None

        for path, original in checkpoint.files.items():
            try:
                if original is None:
                    if path.exists():
                        path.unlink()
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(original)
            except OSError as e:
                logger.error(f"Could not restore {path}: {e}")
        return checkpoint
