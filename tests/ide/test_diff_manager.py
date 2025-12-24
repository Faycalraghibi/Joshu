"""
Tests for IDE Diff Manager.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from joshu.ide.diff_manager import DiffManager, DiffProposal, get_diff_manager


class TestDiffProposal:
    """Tests for DiffProposal dataclass."""

    def test_default_status(self):
        """Should have pending status by default."""
        proposal = DiffProposal(
            proposal_id="test",
            file_path="/test.py",
            original_content="old",
            proposed_content="new",
        )
        assert proposal.status == "pending"

    def test_get_unified_diff(self):
        """Should generate unified diff."""
        proposal = DiffProposal(
            proposal_id="test",
            file_path="/test.py",
            original_content="line1\nline2\n",
            proposed_content="line1\nmodified\n",
        )

        diff = proposal.get_unified_diff()

        assert "-line2" in diff
        assert "+modified" in diff

    def test_get_effective_content_default(self):
        """Should return proposed content by default."""
        proposal = DiffProposal(
            proposal_id="test",
            file_path="/test.py",
            original_content="old",
            proposed_content="new",
        )

        assert proposal.get_effective_content() == "new"

    def test_get_effective_content_edited(self):
        """Should return edited content when set."""
        proposal = DiffProposal(
            proposal_id="test",
            file_path="/test.py",
            original_content="old",
            proposed_content="new",
            edited_content="edited",
        )

        assert proposal.get_effective_content() == "edited"


class TestDiffManager:
    """Tests for DiffManager."""

    @pytest.fixture
    def manager(self):
        """Create fresh diff manager."""
        return DiffManager()

    def test_create_proposal(self, manager):
        """Should create and track proposal."""
        proposal = manager.create_proposal(
            file_path="/test.py",
            original_content="old",
            proposed_content="new",
            description="test change",
        )

        assert proposal.proposal_id is not None
        assert proposal.file_path == "/test.py"
        assert proposal.status == "pending"
        assert proposal.proposal_id in manager.proposals

    def test_create_proposal_emits_event(self, manager):
        """Should emit event on creation."""
        callback = MagicMock()
        manager.on("proposal_created", callback)

        manager.create_proposal(
            file_path="/test.py",
            original_content="old",
            proposed_content="new",
        )

        callback.assert_called_once()

    def test_accept_proposal(self, manager):
        """Should mark proposal as accepted."""
        proposal = manager.create_proposal(
            file_path="/test.py",
            original_content="old",
            proposed_content="new",
        )

        # Don't apply to file in test
        result = manager.accept_proposal(proposal.proposal_id, apply=False)

        assert result is True
        assert proposal.status == "accepted"

    def test_accept_proposal_applies_changes(self, manager):
        """Should write content to file."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".py") as f:
            f.write("old content")
            temp_path = f.name

        try:
            proposal = manager.create_proposal(
                file_path=temp_path,
                original_content="old content",
                proposed_content="new content",
            )

            result = manager.accept_proposal(proposal.proposal_id, apply=True)

            assert result is True
            assert Path(temp_path).read_text() == "new content"
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_accept_proposal_emits_event(self, manager):
        """Should emit event on acceptance."""
        callback = MagicMock()
        manager.on("proposal_accepted", callback)

        proposal = manager.create_proposal(
            file_path="/test.py",
            original_content="old",
            proposed_content="new",
        )
        manager.accept_proposal(proposal.proposal_id, apply=False)

        callback.assert_called_once()

    def test_reject_proposal(self, manager):
        """Should mark proposal as rejected."""
        proposal = manager.create_proposal(
            file_path="/test.py",
            original_content="old",
            proposed_content="new",
        )

        result = manager.reject_proposal(proposal.proposal_id)

        assert result is True
        assert proposal.status == "rejected"

    def test_reject_proposal_emits_event(self, manager):
        """Should emit event on rejection."""
        callback = MagicMock()
        manager.on("proposal_rejected", callback)

        proposal = manager.create_proposal(
            file_path="/test.py",
            original_content="old",
            proposed_content="new",
        )
        manager.reject_proposal(proposal.proposal_id)

        callback.assert_called_once()

    def test_edit_proposal(self, manager):
        """Should update proposal with edited content."""
        proposal = manager.create_proposal(
            file_path="/test.py",
            original_content="old",
            proposed_content="new",
        )

        result = manager.edit_proposal(proposal.proposal_id, "edited")

        assert result is True
        assert proposal.edited_content == "edited"
        assert proposal.status == "edited"

    def test_get_pending_proposals(self, manager):
        """Should return only pending proposals."""
        p1 = manager.create_proposal("/a.py", "old", "new")
        p2 = manager.create_proposal("/b.py", "old", "new")
        manager.accept_proposal(p1.proposal_id, apply=False)

        pending = manager.get_pending_proposals()

        assert len(pending) == 1
        assert pending[0].proposal_id == p2.proposal_id

    def test_get_proposal(self, manager):
        """Should retrieve proposal by ID."""
        proposal = manager.create_proposal("/test.py", "old", "new")

        retrieved = manager.get_proposal(proposal.proposal_id)

        assert retrieved == proposal

    def test_get_proposal_not_found(self, manager):
        """Should return None for unknown ID."""
        assert manager.get_proposal("unknown") is None

    def test_clear_resolved(self, manager):
        """Should remove accepted/rejected proposals."""
        p1 = manager.create_proposal("/a.py", "old", "new")
        p2 = manager.create_proposal("/b.py", "old", "new")
        p3 = manager.create_proposal("/c.py", "old", "new")

        manager.accept_proposal(p1.proposal_id, apply=False)
        manager.reject_proposal(p2.proposal_id)

        count = manager.clear_resolved()

        assert count == 2
        assert len(manager.proposals) == 1
        assert p3.proposal_id in manager.proposals

    def test_accept_unknown_proposal(self, manager):
        """Should return False for unknown proposal."""
        assert manager.accept_proposal("unknown") is False

    def test_reject_unknown_proposal(self, manager):
        """Should return False for unknown proposal."""
        assert manager.reject_proposal("unknown") is False

    def test_edit_unknown_proposal(self, manager):
        """Should return False for unknown proposal."""
        assert manager.edit_proposal("unknown", "content") is False


class TestGetDiffManager:
    """Tests for get_diff_manager function."""

    def test_returns_singleton(self):
        """Should return same instance."""
        m1 = get_diff_manager()
        m2 = get_diff_manager()

        assert m1 is m2
