"""Base test classes and shared utilities for model tests."""

from unittest.mock import MagicMock


class ModelTestBase:
    """Base class for model provider tests."""

    def assert_provider_initialization(self, provider, expected_name, expected_model=None):
        """Assert that a provider is properly initialized."""
        assert provider.name == expected_name
        if expected_model:
            assert provider.model_name == expected_model

    def assert_provider_availability(self, provider, should_be_available=True):
        """Assert that a provider's availability state is correct."""
        if should_be_available:
            assert provider.is_available() is True
        else:
            assert provider.is_available() is False

    def mock_http_response(self, status_code=200, response_data=None):
        """Create a mock HTTP response."""
        if response_data is None:
            response_data = {"choices": [{"message": {"content": "test"}}]}

        mock_response = MagicMock()
        mock_response.status_code = status_code
        mock_response.json.return_value = response_data
        return mock_response
