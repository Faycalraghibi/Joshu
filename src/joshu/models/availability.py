"""
Model Availability Service for health tracking and model selection.

This module provides declarative health tracking for AI models,
enabling intelligent model selection based on current availability
and failure history.

Key principles:
- ZERO execution logic - tracks state, does not make model calls
- Declarative health states (terminal, transient, healthy)
- Failure classification for informed selection
- Turn-based retry mechanisms
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FailureCategory(Enum):
    """Classification of model failure types."""

    TERMINAL = "terminal"  # Permanent failure (e.g., model removed, auth invalid)
    TRANSIENT = "transient"  # Temporary failure (e.g., rate limit, capacity)
    NOT_FOUND = "not_found"  # Model doesn't exist
    HEALTHY = "healthy"  # No failure


class HealthStatus(Enum):
    """Current health status of a model."""

    HEALTHY = "healthy"
    UNHEALTHY_TRANSIENT = "unhealthy_transient"  # Temporary issue, may retry
    UNHEALTHY_TERMINAL = "unhealthy_terminal"  # Permanent issue, skip
    UNKNOWN = "unknown"  # Not yet determined


@dataclass
class HealthState:
    """
    Health state record for a model.

    Tracks the current health status, failure history, and retry state
    for a specific model.

    Attributes:
        model_name: Identifier for the model
        status: Current health status
        failure_category: Classification of the last failure
        failure_reason: Human-readable failure description
        last_failure_time: When the last failure occurred
        failure_count: Number of consecutive failures
        retry_attempted_this_turn: Whether retry was attempted in current turn
        turn_id: Current turn identifier for retry tracking
    """

    model_name: str
    status: HealthStatus = HealthStatus.UNKNOWN
    failure_category: FailureCategory = FailureCategory.HEALTHY
    failure_reason: Optional[str] = None
    last_failure_time: Optional[datetime] = None
    failure_count: int = 0
    retry_attempted_this_turn: bool = False
    turn_id: Optional[str] = None

    def is_available(self) -> bool:
        """Check if model is currently available for use."""
        return self.status in (HealthStatus.HEALTHY, HealthStatus.UNKNOWN)

    def can_retry_this_turn(self, current_turn_id: str) -> bool:
        """
        Check if model can be retried in the current turn.

        Implements "retry once per turn" policy for transient failures.
        """
        if self.status == HealthStatus.UNHEALTHY_TERMINAL:
            return False

        if self.status == HealthStatus.UNHEALTHY_TRANSIENT:
            # Allow retry if this is a new turn
            if self.turn_id != current_turn_id:
                return True
            # Or if we haven't retried this turn yet
            return not self.retry_attempted_this_turn

        return True

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "model_name": self.model_name,
            "status": self.status.value,
            "failure_category": self.failure_category.value,
            "failure_reason": self.failure_reason,
            "failure_count": self.failure_count,
            "retry_attempted_this_turn": self.retry_attempted_this_turn,
        }


@dataclass
class ModelSelectionResult:
    """
    Result of a model selection operation.

    Contains the selected model (if any) and metadata about
    the selection process including which models were skipped.

    Attributes:
        selected_model: The model chosen for use (None if all unavailable)
        skipped_models: Models that were skipped and why
        all_unavailable: True if no models could be selected
        selection_reason: Explanation of the selection
    """

    selected_model: Optional[str] = None
    skipped_models: Dict[str, str] = field(default_factory=dict)
    all_unavailable: bool = False
    selection_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "selected_model": self.selected_model,
            "skipped_models": self.skipped_models,
            "all_unavailable": self.all_unavailable,
            "selection_reason": self.selection_reason,
        }


class ModelAvailabilityService:
    """
    Service for tracking model health and selecting available models.

    This service maintains health state for models and provides
    intelligent model selection based on current availability.

    Key behaviors:
    - Tracks health states per model
    - Classifies failures as terminal or transient
    - Implements "retry once per turn" policy
    - Selects from candidates based on health

    Note: This service does NOT execute model calls.
    It only tracks state and produces selection results.

    Example:
        >>> service = ModelAvailabilityService()
        >>> service.mark_healthy("gpt-4o")
        >>> service.mark_transient_failure("gpt-4o-mini", "Rate limit exceeded")
        >>> result = service.select_model(["gpt-4o-mini", "gpt-4o"], "turn_1")
        >>> result.selected_model
        'gpt-4o'
    """

    def __init__(self) -> None:
        """Initialize the availability service."""
        self._health_states: Dict[str, HealthState] = {}
        self._current_turn_id: Optional[str] = None

    def get_health_state(self, model_name: str) -> HealthState:
        """
        Get the health state for a model.

        Creates a new state with UNKNOWN status if not tracked.

        Args:
            model_name: Model identifier

        Returns:
            HealthState for the model
        """
        if model_name not in self._health_states:
            self._health_states[model_name] = HealthState(model_name=model_name)
        return self._health_states[model_name]

    def mark_healthy(self, model_name: str) -> None:
        """
        Mark a model as healthy/available.

        Resets failure state and marks model as ready for use.

        Args:
            model_name: Model identifier
        """
        state = self.get_health_state(model_name)
        state.status = HealthStatus.HEALTHY
        state.failure_category = FailureCategory.HEALTHY
        state.failure_reason = None
        state.failure_count = 0
        state.retry_attempted_this_turn = False
        logger.debug(f"Model '{model_name}' marked as healthy")

    def mark_transient_failure(
        self,
        model_name: str,
        reason: str,
        turn_id: Optional[str] = None,
    ) -> None:
        """
        Mark a model as temporarily unavailable.

        Transient failures may be retried once per turn.

        Args:
            model_name: Model identifier
            reason: Human-readable failure reason
            turn_id: Current turn identifier for retry tracking
        """
        state = self.get_health_state(model_name)
        state.status = HealthStatus.UNHEALTHY_TRANSIENT
        state.failure_category = FailureCategory.TRANSIENT
        state.failure_reason = reason
        state.last_failure_time = datetime.now()
        state.failure_count += 1

        if turn_id:
            state.turn_id = turn_id

        logger.info(f"Model '{model_name}' marked as transiently unavailable: {reason}")

    def mark_terminal_failure(self, model_name: str, reason: str) -> None:
        """
        Mark a model as permanently unavailable.

        Terminal failures persist until explicitly cleared.

        Args:
            model_name: Model identifier
            reason: Human-readable failure reason
        """
        state = self.get_health_state(model_name)
        state.status = HealthStatus.UNHEALTHY_TERMINAL
        state.failure_category = FailureCategory.TERMINAL
        state.failure_reason = reason
        state.last_failure_time = datetime.now()
        state.failure_count += 1
        logger.warning(f"Model '{model_name}' marked as terminally unavailable: {reason}")

    def mark_not_found(self, model_name: str) -> None:
        """
        Mark a model as not found.

        Treated as terminal since model doesn't exist.

        Args:
            model_name: Model identifier
        """
        state = self.get_health_state(model_name)
        state.status = HealthStatus.UNHEALTHY_TERMINAL
        state.failure_category = FailureCategory.NOT_FOUND
        state.failure_reason = "Model not found"
        state.last_failure_time = datetime.now()
        logger.warning(f"Model '{model_name}' not found")

    def record_retry_attempt(self, model_name: str, turn_id: str) -> None:
        """
        Record that a retry was attempted for a model in this turn.

        Args:
            model_name: Model identifier
            turn_id: Current turn identifier
        """
        state = self.get_health_state(model_name)
        state.retry_attempted_this_turn = True
        state.turn_id = turn_id

    def reset_turn_state(self, turn_id: str) -> None:
        """
        Reset retry state for a new turn.

        Called at the start of each conversation turn.

        Args:
            turn_id: New turn identifier
        """
        self._current_turn_id = turn_id
        for state in self._health_states.values():
            if state.turn_id != turn_id:
                state.retry_attempted_this_turn = False
                state.turn_id = turn_id
        logger.debug(f"Reset turn state for turn: {turn_id}")

    def classify_error(
        self,
        error_type: str,
        error_message: str,
        status_code: Optional[int] = None,
    ) -> FailureCategory:
        """
        Classify an error into a failure category.

        This is a pure function that determines failure type
        based on error characteristics.

        Args:
            error_type: Type/class of the error
            error_message: Error message text
            status_code: Optional HTTP status code

        Returns:
            FailureCategory classification
        """
        error_lower = error_message.lower()

        # Terminal failures
        if status_code == 401 or "authentication" in error_lower:
            return FailureCategory.TERMINAL
        if status_code == 403 or "forbidden" in error_lower:
            return FailureCategory.TERMINAL
        if "invalid api key" in error_lower:
            return FailureCategory.TERMINAL
        if "model not found" in error_lower or "does not exist" in error_lower:
            return FailureCategory.NOT_FOUND

        # Transient failures
        if status_code == 429 or "rate limit" in error_lower:
            return FailureCategory.TRANSIENT
        if status_code == 503 or "capacity" in error_lower:
            return FailureCategory.TRANSIENT
        if status_code == 500 or "internal error" in error_lower:
            return FailureCategory.TRANSIENT
        if "timeout" in error_lower or "connection" in error_lower:
            return FailureCategory.TRANSIENT
        if "quota" in error_lower:
            return FailureCategory.TRANSIENT

        # Default to transient for unknown errors
        return FailureCategory.TRANSIENT

    def select_model(
        self,
        candidates: List[str],
        turn_id: str,
    ) -> ModelSelectionResult:
        """
        Select an available model from candidates.

        Iterates through candidates in order, selecting the first
        one that is healthy or eligible for retry.

        Args:
            candidates: Ordered list of model names to consider
            turn_id: Current turn identifier for retry tracking

        Returns:
            ModelSelectionResult with selected model and skip reasons
        """
        if not candidates:
            return ModelSelectionResult(
                selected_model=None,
                all_unavailable=True,
                selection_reason="No candidate models provided",
            )

        skipped: Dict[str, str] = {}

        for model_name in candidates:
            state = self.get_health_state(model_name)

            # Check if model is available
            if state.is_available():
                return ModelSelectionResult(
                    selected_model=model_name,
                    skipped_models=skipped,
                    selection_reason=f"Selected '{model_name}' (healthy)",
                )

            # Check if eligible for retry this turn
            if state.can_retry_this_turn(turn_id):
                self.record_retry_attempt(model_name, turn_id)
                return ModelSelectionResult(
                    selected_model=model_name,
                    skipped_models=skipped,
                    selection_reason=f"Selected '{model_name}' for retry (transient failure)",
                )

            # Skip this model
            skip_reason = state.failure_reason or f"Status: {state.status.value}"
            skipped[model_name] = skip_reason
            logger.debug(f"Skipping model '{model_name}': {skip_reason}")

        # All models unavailable
        return ModelSelectionResult(
            selected_model=None,
            skipped_models=skipped,
            all_unavailable=True,
            selection_reason="All candidate models unavailable",
        )

    def get_available_models(self, candidates: List[str]) -> List[str]:
        """
        Filter candidates to only available models.

        Args:
            candidates: List of model names to filter

        Returns:
            List of available model names
        """
        return [name for name in candidates if self.get_health_state(name).is_available()]

    def get_all_health_states(self) -> Dict[str, HealthState]:
        """Get all tracked health states."""
        return dict(self._health_states)

    def clear(self) -> None:
        """Clear all health state tracking."""
        self._health_states.clear()
        self._current_turn_id = None
        logger.debug("Cleared all health state tracking")


# Singleton instance
_service: Optional[ModelAvailabilityService] = None


def get_model_availability_service() -> ModelAvailabilityService:
    """
    Get the global model availability service instance.

    Returns:
        ModelAvailabilityService singleton
    """
    global _service
    if _service is None:
        _service = ModelAvailabilityService()
    return _service
