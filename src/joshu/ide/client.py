"""
IDE Client.

Client for communicating with the IDE server from the CLI.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional

import httpx

from joshu.ide.discovery import IDEServerInfo, get_default_server
from joshu.ide.schemas import IdeContext

logger = logging.getLogger(__name__)


class IDEClientError(Exception):
    """IDE client error."""

    pass


@dataclass
class IDEClient:
    """
    Client for IDE server communication.

    Provides methods to:
    - Get current IDE context
    - Propose diffs
    - Check diff status
    """

    server_info: IDEServerInfo

    @property
    def base_url(self) -> str:
        """Get the server base URL."""
        return f"http://127.0.0.1:{self.server_info.port}"

    @property
    def headers(self) -> Dict[str, str]:
        """Get request headers with auth."""
        return {
            "Authorization": f"Bearer {self.server_info.token}",
            "Content-Type": "application/json",
        }

    def get_context(self) -> Optional[IdeContext]:
        """
        Get the current IDE context.

        Returns:
            IdeContext if successful, None otherwise.
        """
        try:
            response = httpx.get(
                f"{self.base_url}/context",
                headers=self.headers,
                timeout=5.0,
            )
            if response.status_code == 200:
                data = response.json()
                return IdeContext.from_dict(data)
            else:
                logger.warning(f"Failed to get context: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error getting IDE context: {e}")
            return None

    def propose_diff(
        self,
        file_path: str,
        original_content: str,
        proposed_content: str,
        description: str = "",
    ) -> Optional[str]:
        """
        Propose a diff to the IDE.

        Args:
            file_path: Path to the file.
            original_content: Original file content.
            proposed_content: Proposed new content.
            description: Description of the change.

        Returns:
            Proposal ID if successful, None otherwise.
        """
        try:
            response = httpx.post(
                f"{self.base_url}/diff/propose",
                headers=self.headers,
                json={
                    "file_path": file_path,
                    "original_content": original_content,
                    "proposed_content": proposed_content,
                    "description": description,
                },
                timeout=5.0,
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("proposal_id")
            else:
                logger.warning(f"Failed to propose diff: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error proposing diff: {e}")
            return None

    def get_pending_diffs(self) -> list:
        """
        Get all pending diff proposals.

        Returns:
            List of pending proposals.
        """
        try:
            response = httpx.get(
                f"{self.base_url}/diff/pending",
                headers=self.headers,
                timeout=5.0,
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("proposals", [])
            return []
        except Exception as e:
            logger.error(f"Error getting pending diffs: {e}")
            return []

    def is_connected(self) -> bool:
        """Check if connected to IDE server."""
        try:
            response = httpx.get(
                f"{self.base_url}/health",
                timeout=2.0,
            )
            return response.status_code == 200
        except Exception:
            return False


def get_ide_client() -> Optional[IDEClient]:
    """
    Get an IDE client connected to an available server.

    Returns:
        IDEClient if server found, None otherwise.
    """
    server = get_default_server()
    if server:
        return IDEClient(server_info=server)
    return None


def get_current_ide_context() -> Optional[IdeContext]:
    """
    Convenience function to get current IDE context.

    Returns:
        IdeContext if available, None otherwise.
    """
    client = get_ide_client()
    if client:
        return client.get_context()
    return None
