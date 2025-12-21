"""
Credential storage interfaces for LLM API access.

This module provides declarative structures for managing API keys
and OAuth credentials with secure storage backends.

Key principles:
- ZERO execution logic - defines interfaces and data structures
- Supports API key, OAuth, and hybrid storage
- Abstract backend (keychain, file, memory)
- No actual encryption or I/O operations
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class CredentialType(Enum):
    """Type of credential being stored."""

    API_KEY = "api_key"
    OAUTH_TOKEN = "oauth_token"
    SERVICE_ACCOUNT = "service_account"


class StorageBackend(Enum):
    """Backend for credential storage."""

    MEMORY = "memory"  # In-memory only (testing)
    FILE = "file"  # Encrypted file storage
    KEYCHAIN = "keychain"  # OS keychain (secure)
    HYBRID = "hybrid"  # Keychain with file fallback


@dataclass
class OAuthCredentials:
    """
    OAuth 2.0 credentials structure.

    Attributes:
        access_token: Current access token
        refresh_token: Token for refreshing access
        token_type: Type of token (Bearer, ApiKey, etc.)
        expires_at: When the access token expires
        scope: OAuth scopes granted
    """

    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_at: Optional[datetime] = None
    scope: Optional[str] = None

    def is_expired(self) -> bool:
        """Check if token is expired."""
        if self.expires_at is None:
            return False
        return datetime.now() >= self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": self.token_type,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "scope": self.scope,
        }

    @classmethod
    def from_api_key(cls, api_key: str) -> "OAuthCredentials":
        """Wrap an API key in OAuth credential format."""
        return cls(
            access_token=api_key,
            token_type="ApiKey",
        )


@dataclass
class StoredCredential:
    """
    A credential stored in the system.

    Wraps any credential type with metadata.

    Attributes:
        credential_type: Type of credential
        credentials: The actual credential data
        service_name: Service this credential is for
        created_at: When credential was stored
        last_used: When credential was last accessed
        metadata: Additional credential metadata
    """

    credential_type: CredentialType
    credentials: OAuthCredentials
    service_name: str = "default"
    created_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = datetime.now()


class CredentialStorage(ABC):
    """
    Abstract interface for credential storage.

    Implementations handle the actual storage mechanism
    (memory, file, keychain, etc.).
    """

    @abstractmethod
    def load(self, service_name: str) -> Optional[StoredCredential]:
        """Load credential for a service."""
        pass

    @abstractmethod
    def save(self, credential: StoredCredential) -> bool:
        """Save a credential."""
        pass

    @abstractmethod
    def clear(self, service_name: str) -> bool:
        """Clear credential for a service."""
        pass

    @abstractmethod
    def exists(self, service_name: str) -> bool:
        """Check if credential exists."""
        pass


class MemoryCredentialStorage(CredentialStorage):
    """
    In-memory credential storage for testing.

    Does not persist credentials across sessions.
    """

    def __init__(self) -> None:
        self._credentials: Dict[str, StoredCredential] = {}

    def load(self, service_name: str) -> Optional[StoredCredential]:
        """Load credential from memory."""
        cred = self._credentials.get(service_name)
        if cred:
            cred.last_used = datetime.now()
        return cred

    def save(self, credential: StoredCredential) -> bool:
        """Save credential to memory."""
        self._credentials[credential.service_name] = credential
        return True

    def clear(self, service_name: str) -> bool:
        """Clear credential from memory."""
        if service_name in self._credentials:
            del self._credentials[service_name]
            return True
        return False

    def exists(self, service_name: str) -> bool:
        """Check if credential exists in memory."""
        return service_name in self._credentials


@dataclass
class HybridStorageConfig:
    """
    Configuration for hybrid credential storage.

    Attributes:
        prefer_keychain: Try keychain first
        file_path: Path for file fallback
        encrypt_file: Whether to encrypt file storage
        service_prefix: Prefix for keychain service names
    """

    prefer_keychain: bool = True
    file_path: Optional[str] = None
    encrypt_file: bool = True
    service_prefix: str = "joshu"


class HybridCredentialStorage(CredentialStorage):
    """
    Hybrid storage that tries keychain first, falls back to file.

    This is a declarative structure - actual keychain/file operations
    would be implemented by concrete backends.

    Attributes:
        config: Hybrid storage configuration
        keychain_available: Whether keychain backend is available
        _memory_fallback: In-memory storage for testing
    """

    def __init__(
        self,
        config: Optional[HybridStorageConfig] = None,
        keychain_available: bool = False,
    ) -> None:
        self.config = config or HybridStorageConfig()
        self.keychain_available = keychain_available
        self._memory_fallback = MemoryCredentialStorage()
        self._storage_type_used: Dict[str, StorageBackend] = {}

    def _get_effective_backend(self, service_name: str) -> StorageBackend:
        """Determine which backend to use."""
        if self.config.prefer_keychain and self.keychain_available:
            return StorageBackend.KEYCHAIN
        if self.config.file_path:
            return StorageBackend.FILE
        return StorageBackend.MEMORY

    def load(self, service_name: str) -> Optional[StoredCredential]:
        """Load credential using hybrid strategy."""
        # For now, use memory fallback
        # Real implementation would try keychain, then file
        backend = self._get_effective_backend(service_name)
        logger.debug(f"Loading credential '{service_name}' from {backend.value}")
        return self._memory_fallback.load(service_name)

    def save(self, credential: StoredCredential) -> bool:
        """Save credential using hybrid strategy."""
        backend = self._get_effective_backend(credential.service_name)
        self._storage_type_used[credential.service_name] = backend
        logger.debug(f"Saving credential '{credential.service_name}' to {backend.value}")
        return self._memory_fallback.save(credential)

    def clear(self, service_name: str) -> bool:
        """Clear credential from storage."""
        return self._memory_fallback.clear(service_name)

    def exists(self, service_name: str) -> bool:
        """Check if credential exists."""
        return self._memory_fallback.exists(service_name)

    def get_storage_type(self, service_name: str) -> Optional[StorageBackend]:
        """Get which storage backend was used for a credential."""
        return self._storage_type_used.get(service_name)


@dataclass
class APIKeyConfig:
    """
    Configuration for API key credential storage.

    Attributes:
        service_name: Name of the LLM service
        key_env_var: Environment variable name for key
        storage_backend: Where to store the key
    """

    service_name: str
    key_env_var: str = "OPENAI_API_KEY"
    storage_backend: StorageBackend = StorageBackend.HYBRID


def create_credential_storage(
    backend: StorageBackend,
    config: Optional[HybridStorageConfig] = None,
) -> CredentialStorage:
    """
    Factory function to create credential storage.

    Args:
        backend: Storage backend to use
        config: Configuration for hybrid storage

    Returns:
        CredentialStorage implementation
    """
    if backend == StorageBackend.MEMORY:
        return MemoryCredentialStorage()
    elif backend == StorageBackend.HYBRID:
        return HybridCredentialStorage(config)
    else:
        # For FILE and KEYCHAIN, use hybrid with appropriate config
        return HybridCredentialStorage(config)
