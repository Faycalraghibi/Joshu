"""
Unit tests for ModelAvailabilityService.

Run with: pytest tests/models/test_availability.py -v
"""

import pytest

from joshu.models.availability import (
    FailureCategory,
    HealthState,
    HealthStatus,
    ModelAvailabilityService,
    ModelSelectionResult,
    get_model_availability_service,
)


class TestHealthState:
    """Test HealthState data structure."""

    def test_default_state(self):
        """Test default state is unknown."""
        state = HealthState(model_name="test_model")
        assert state.status == HealthStatus.UNKNOWN
        assert state.is_available()

    def test_healthy_state_available(self):
        """Test healthy state is available."""
        state = HealthState(model_name="test", status=HealthStatus.HEALTHY)
        assert state.is_available()

    def test_transient_state_unavailable(self):
        """Test transient failure is unavailable."""
        state = HealthState(
            model_name="test",
            status=HealthStatus.UNHEALTHY_TRANSIENT,
        )
        assert not state.is_available()

    def test_terminal_state_unavailable(self):
        """Test terminal failure is unavailable."""
        state = HealthState(
            model_name="test",
            status=HealthStatus.UNHEALTHY_TERMINAL,
        )
        assert not state.is_available()

    def test_can_retry_new_turn(self):
        """Test retry allowed on new turn."""
        state = HealthState(
            model_name="test",
            status=HealthStatus.UNHEALTHY_TRANSIENT,
            turn_id="turn_1",
            retry_attempted_this_turn=True,
        )
        # New turn - should allow retry
        assert state.can_retry_this_turn("turn_2")

    def test_cannot_retry_same_turn(self):
        """Test retry blocked if already attempted this turn."""
        state = HealthState(
            model_name="test",
            status=HealthStatus.UNHEALTHY_TRANSIENT,
            turn_id="turn_1",
            retry_attempted_this_turn=True,
        )
        assert not state.can_retry_this_turn("turn_1")

    def test_terminal_cannot_retry(self):
        """Test terminal failures cannot be retried."""
        state = HealthState(
            model_name="test",
            status=HealthStatus.UNHEALTHY_TERMINAL,
        )
        assert not state.can_retry_this_turn("any_turn")

    def test_to_dict(self):
        """Test serialization."""
        state = HealthState(
            model_name="gpt-4o",
            status=HealthStatus.HEALTHY,
            failure_count=0,
        )
        data = state.to_dict()
        assert data["model_name"] == "gpt-4o"
        assert data["status"] == "healthy"


class TestModelSelectionResult:
    """Test ModelSelectionResult data structure."""

    def test_successful_selection(self):
        """Test result with selected model."""
        result = ModelSelectionResult(
            selected_model="gpt-4o",
            selection_reason="Selected 'gpt-4o' (healthy)",
        )
        assert not result.all_unavailable
        assert result.selected_model == "gpt-4o"

    def test_all_unavailable(self):
        """Test result when no models available."""
        result = ModelSelectionResult(
            selected_model=None,
            all_unavailable=True,
            skipped_models={"model_a": "rate limited", "model_b": "auth failed"},
        )
        assert result.all_unavailable
        assert len(result.skipped_models) == 2


class TestModelAvailabilityService:
    """Test ModelAvailabilityService functionality."""

    @pytest.fixture
    def service(self):
        """Create fresh service instance."""
        svc = ModelAvailabilityService()
        svc.clear()
        return svc

    def test_mark_healthy(self, service):
        """Test marking model as healthy."""
        service.mark_healthy("gpt-4o")
        state = service.get_health_state("gpt-4o")
        assert state.status == HealthStatus.HEALTHY
        assert state.is_available()

    def test_mark_transient_failure(self, service):
        """Test marking model with transient failure."""
        service.mark_transient_failure("gpt-4o", "Rate limit exceeded")
        state = service.get_health_state("gpt-4o")
        assert state.status == HealthStatus.UNHEALTHY_TRANSIENT
        assert state.failure_reason == "Rate limit exceeded"
        assert not state.is_available()

    def test_mark_terminal_failure(self, service):
        """Test marking model with terminal failure."""
        service.mark_terminal_failure("gpt-4o", "Invalid API key")
        state = service.get_health_state("gpt-4o")
        assert state.status == HealthStatus.UNHEALTHY_TERMINAL
        assert not state.is_available()

    def test_mark_not_found(self, service):
        """Test marking model as not found."""
        service.mark_not_found("unknown-model")
        state = service.get_health_state("unknown-model")
        assert state.failure_category == FailureCategory.NOT_FOUND


class TestFailureClassification:
    """Test error classification logic."""

    @pytest.fixture
    def service(self):
        return ModelAvailabilityService()

    def test_classify_rate_limit(self, service):
        """Test rate limit classified as transient."""
        category = service.classify_error(
            "RateLimitError",
            "Rate limit exceeded",
            status_code=429,
        )
        assert category == FailureCategory.TRANSIENT

    def test_classify_auth_error(self, service):
        """Test auth error classified as terminal."""
        category = service.classify_error(
            "AuthError",
            "Invalid API key",
            status_code=401,
        )
        assert category == FailureCategory.TERMINAL

    def test_classify_not_found(self, service):
        """Test model not found classified correctly."""
        category = service.classify_error(
            "NotFoundError",
            "Model not found: xyz",
            status_code=404,
        )
        assert category == FailureCategory.NOT_FOUND

    def test_classify_capacity(self, service):
        """Test capacity error classified as transient."""
        category = service.classify_error(
            "ServiceError",
            "Insufficient capacity",
            status_code=503,
        )
        assert category == FailureCategory.TRANSIENT

    def test_classify_timeout(self, service):
        """Test timeout classified as transient."""
        category = service.classify_error(
            "TimeoutError",
            "Connection timeout",
        )
        assert category == FailureCategory.TRANSIENT


class TestModelSelection:
    """Test model selection logic."""

    @pytest.fixture
    def service(self):
        svc = ModelAvailabilityService()
        svc.clear()
        return svc

    def test_select_healthy_model(self, service):
        """Test selecting a healthy model."""
        service.mark_healthy("gpt-4o")
        result = service.select_model(["gpt-4o"], "turn_1")

        assert result.selected_model == "gpt-4o"
        assert not result.all_unavailable

    def test_select_first_healthy(self, service):
        """Test selecting first healthy model in order."""
        service.mark_transient_failure("model_a", "rate limit", "turn_1")
        service.record_retry_attempt("model_a", "turn_1")  # Already retried
        service.mark_healthy("model_b")
        service.mark_healthy("model_c")

        result = service.select_model(["model_a", "model_b", "model_c"], "turn_1")

        assert result.selected_model == "model_b"
        assert "model_a" in result.skipped_models

    def test_select_fallback_on_terminal(self, service):
        """Test fallback when primary is terminal."""
        service.mark_terminal_failure("primary", "auth failed")
        service.mark_healthy("fallback")

        result = service.select_model(["primary", "fallback"], "turn_1")

        assert result.selected_model == "fallback"
        assert "primary" in result.skipped_models

    def test_retry_transient_new_turn(self, service):
        """Test retry allowed on new turn."""
        service.mark_transient_failure("model_a", "rate limit", "turn_1")
        service.record_retry_attempt("model_a", "turn_1")

        # New turn - should allow retry
        result = service.select_model(["model_a"], "turn_2")

        assert result.selected_model == "model_a"

    def test_all_unavailable(self, service):
        """Test result when all models unavailable."""
        service.mark_terminal_failure("model_a", "auth")
        service.mark_terminal_failure("model_b", "auth")

        result = service.select_model(["model_a", "model_b"], "turn_1")

        assert result.all_unavailable
        assert result.selected_model is None
        assert len(result.skipped_models) == 2

    def test_empty_candidates(self, service):
        """Test empty candidate list."""
        result = service.select_model([], "turn_1")
        assert result.all_unavailable

    def test_unknown_model_available(self, service):
        """Test unknown models are considered available."""
        # Never seen this model before
        result = service.select_model(["new_model"], "turn_1")
        assert result.selected_model == "new_model"


class TestTurnStateReset:
    """Test turn state reset functionality."""

    @pytest.fixture
    def service(self):
        svc = ModelAvailabilityService()
        svc.clear()
        return svc

    def test_reset_clears_retry_flags(self, service):
        """Test reset clears retry flags."""
        service.mark_transient_failure("model_a", "error", "turn_1")
        service.record_retry_attempt("model_a", "turn_1")

        state = service.get_health_state("model_a")
        assert state.retry_attempted_this_turn

        service.reset_turn_state("turn_2")

        assert not state.retry_attempted_this_turn


class TestGetAvailableModels:
    """Test available model filtering."""

    @pytest.fixture
    def service(self):
        svc = ModelAvailabilityService()
        svc.clear()
        return svc

    def test_filter_available(self, service):
        """Test filtering to available models."""
        service.mark_healthy("model_a")
        service.mark_terminal_failure("model_b", "auth")
        service.mark_healthy("model_c")

        available = service.get_available_models(["model_a", "model_b", "model_c"])

        assert available == ["model_a", "model_c"]


class TestGlobalService:
    """Test global service accessor."""

    def test_get_singleton(self):
        """Test singleton access."""
        svc1 = get_model_availability_service()
        svc2 = get_model_availability_service()
        assert svc1 is svc2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
