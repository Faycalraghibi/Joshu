"""Base test classes and shared utilities for model tests."""

import pytest
from unittest.mock import patch, MagicMock
import os


class ModelTestBase:
    """Base class for model provider tests."""
    
    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Reset environment before each test."""
        # Clear model-related environment variables
        model_vars = [
            "LOCAL_MODEL_URL", "LOCAL_MODEL_IDENTIFIER", "OPENROUTER_API_KEY",
            "VLLM_MODEL", "VLLM_SERVER_URL"
        ]
        
        for var in model_vars:
            if var in os.environ:
                del os.environ[var]
    
    def assert_provider_initialization(self, provider, expected_name, expected_model=None):
        """Assert that a provider is properly initialized."""
        assert provider.name == expected_name
        if expected_model:
            assert provider.model_name == expected_model
    
    def assert_provider_availability(self, provider, should_be_available=True):
        """Assert that a provider's availability state is correct."""
        if should_be_available:
            assert provider.is_available() == True
        else:
            assert provider.is_available() == False
    
    def mock_http_response(self, status_code=200, response_data=None):
        """Create a mock HTTP response."""
        if response_data is None:
            response_data = {"choices": [{"message": {"content": "test"}}]}
            
        mock_response = MagicMock()
        mock_response.status_code = status_code
        mock_response.json.return_value = response_data
        return mock_response