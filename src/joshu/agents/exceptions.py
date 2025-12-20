"""
Custom exceptions for the Agent Definition and Registration System.

This module defines exception classes for agent-related errors including
validation failures, registration errors, and schema conversion issues.
"""

from __future__ import annotations


class AgentError(Exception):
    """Base exception for all agent-related errors."""

    pass


class AgentValidationError(AgentError):
    """
    Raised when agent definition validation fails.

    This occurs when an AgentDefinition has missing required fields,
    invalid field values, or fails other validation constraints.
    """

    pass


class AgentRegistrationError(AgentError):
    """
    Raised when agent registration fails.

    This occurs when attempting to register an agent that already exists
    or when the registry rejects the agent for other reasons.
    """

    pass


class AgentNotFoundError(AgentError):
    """
    Raised when a requested agent is not found in the registry.

    This occurs when attempting to get, invoke, or wrap an agent
    that has not been registered.
    """

    pass


class SchemaConversionError(AgentError):
    """
    Raised when InputConfig to JSON Schema conversion fails.

    This occurs when the InputConfig contains unsupported field types
    or malformed field definitions.
    """

    pass
