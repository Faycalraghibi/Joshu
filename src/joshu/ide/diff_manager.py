"""
Diff Manager.

Manages proposed code changes and their display in the IDE.
"""

from __future__ import annotations

import difflib
import logging
import secrets
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DiffProposal:
    """A proposed file modification."""

    proposal_id: str
    file_path: str
    original_content: str
    proposed_content: str
    description: str = ""
    status: str = "pending"  # pending, accepted, rejected, edited
    edited_content: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def get_unified_diff(self) -> str:
        """Generate unified diff between original and proposed."""
        original_lines = self.original_content.splitlines(keepends=True)
        proposed_lines = self.proposed_content.splitlines(keepends=True)

        diff = difflib.unified_diff(
            original_lines,
            proposed_lines,
            fromfile=f"a/{Path(self.file_path).name}",
            tofile=f"b/{Path(self.file_path).name}",
        )
        return "".join(diff)

    def get_effective_content(self) -> str:
        """Get the effective content (edited if available, otherwise proposed)."""
        if self.edited_content is not None:
            return self.edited_content
        return self.proposed_content


class DiffManager:
    """
    Manages diff proposals for IDE integration.

    Responsible for:
    - Creating and tracking proposals
    - Notifying IDE of new proposals
    - Handling accept/reject actions
    - Applying changes to files
    """

    def __init__(self):
        """Initialize the diff manager."""
        self.proposals: Dict[str, DiffProposal] = {}
        self._callbacks: Dict[str, List[Callable]] = {
            "proposal_created": [],
            "proposal_accepted": [],
            "proposal_rejected": [],
        }

    def on(self, event: str, callback: Callable) -> None:
        """Register an event callback."""
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    def _emit(self, event: str, data: Any = None) -> None:
        """Emit an event to callbacks."""
        for callback in self._callbacks.get(event, []):
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Callback error for {event}: {e}")

    def create_proposal(
        self,
        file_path: str,
        original_content: str,
        proposed_content: str,
        description: str = "",
    ) -> DiffProposal:
        """
        Create a new diff proposal.

        Args:
            file_path: Path to the file.
            original_content: Original file content.
            proposed_content: Proposed new content.
            description: Description of the change.

        Returns:
            Created DiffProposal.
        """
        proposal = DiffProposal(
            proposal_id=secrets.token_urlsafe(8),
            file_path=file_path,
            original_content=original_content,
            proposed_content=proposed_content,
            description=description,
        )

        self.proposals[proposal.proposal_id] = proposal
        self._emit("proposal_created", proposal)

        logger.info(f"Created diff proposal {proposal.proposal_id} for {file_path}")
        return proposal

    def accept_proposal(self, proposal_id: str, apply: bool = True) -> bool:
        """
        Accept a diff proposal.

        Args:
            proposal_id: ID of the proposal.
            apply: Whether to apply changes to file.

        Returns:
            True if accepted successfully.
        """
        if proposal_id not in self.proposals:
            logger.warning(f"Proposal not found: {proposal_id}")
            return False

        proposal = self.proposals[proposal_id]
        proposal.status = "accepted"

        if apply:
            try:
                content = proposal.get_effective_content()
                Path(proposal.file_path).write_text(content)
                logger.info(f"Applied proposal {proposal_id} to {proposal.file_path}")
            except Exception as e:
                logger.error(f"Failed to apply proposal: {e}")
                return False

        self._emit("proposal_accepted", proposal)
        return True

    def reject_proposal(self, proposal_id: str) -> bool:
        """
        Reject a diff proposal.

        Args:
            proposal_id: ID of the proposal.

        Returns:
            True if rejected successfully.
        """
        if proposal_id not in self.proposals:
            logger.warning(f"Proposal not found: {proposal_id}")
            return False

        proposal = self.proposals[proposal_id]
        proposal.status = "rejected"

        self._emit("proposal_rejected", proposal)
        logger.info(f"Rejected proposal {proposal_id}")
        return True

    def edit_proposal(self, proposal_id: str, edited_content: str) -> bool:
        """
        Edit a proposal's content.

        Args:
            proposal_id: ID of the proposal.
            edited_content: New edited content.

        Returns:
            True if edited successfully.
        """
        if proposal_id not in self.proposals:
            return False

        proposal = self.proposals[proposal_id]
        proposal.edited_content = edited_content
        proposal.status = "edited"
        return True

    def get_pending_proposals(self) -> List[DiffProposal]:
        """Get all pending proposals."""
        return [p for p in self.proposals.values() if p.status == "pending"]

    def get_proposal(self, proposal_id: str) -> Optional[DiffProposal]:
        """Get a proposal by ID."""
        return self.proposals.get(proposal_id)

    def clear_resolved(self) -> int:
        """
        Clear resolved (accepted/rejected) proposals.

        Returns:
            Number of proposals cleared.
        """
        resolved = [
            pid for pid, p in self.proposals.items() if p.status in ("accepted", "rejected")
        ]
        for pid in resolved:
            del self.proposals[pid]
        return len(resolved)


# Global diff manager instance
_diff_manager: Optional[DiffManager] = None


def get_diff_manager() -> DiffManager:
    """Get the global diff manager instance."""
    global _diff_manager
    if _diff_manager is None:
        _diff_manager = DiffManager()
    return _diff_manager
