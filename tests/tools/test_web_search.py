"""
Tests for web search functionality.
"""

from unittest.mock import Mock, patch

import pytest

from joshu.tools.web_search import format_search_results, search_web


class TestWebSearch:
    """Test web search functionality."""

    def test_search_web_success(self):
        """Test successful web search."""
        mock_ddgs_instance = Mock()
        mock_ddgs_instance.text.return_value = [
            {
                "title": "Python Tutorial",
                "href": "https://example.com/python",
                "body": "Learn Python programming",
            },
            {
                "title": "Python Documentation",
                "href": "https://docs.python.org",
                "body": "Official Python documentation",
            },
        ]

        with patch("joshu.tools.web_search.DDGS") as mock_ddgs_class:
            mock_ddgs_class.return_value = mock_ddgs_instance
            with patch("joshu.tools.web_search.DDGS_AVAILABLE", True):
                result = search_web("Python programming", max_results=2)

        assert result["success"] is True
        assert result["query"] == "Python programming"
        assert len(result["results"]) == 2
        assert result["results"][0]["title"] == "Python Tutorial"
        assert result["results"][0]["url"] == "https://example.com/python"
        assert result["error"] is None

    def test_search_web_empty_query(self):
        """Test search with empty query."""
        with patch("joshu.tools.web_search.DDGS_AVAILABLE", True):
            result = search_web("")

        assert result["success"] is False
        assert "empty" in result["error"].lower()

    def test_search_web_whitespace_query(self):
        """Test search with whitespace-only query."""
        with patch("joshu.tools.web_search.DDGS_AVAILABLE", True):
            result = search_web("   ")

        assert result["success"] is False
        assert "empty" in result["error"].lower()

    def test_search_web_library_not_available(self):
        """Test behavior when duckduckgo_search library is not installed."""
        with patch("joshu.tools.web_search.DDGS_AVAILABLE", False):
            result = search_web("test query")

        assert result["success"] is False
        assert "not installed" in result["error"]
        assert result["results"] == []

    def test_search_web_network_error(self):
        """Test handling of network errors."""
        mock_ddgs_instance = Mock()
        mock_ddgs_instance.text.side_effect = Exception("Network timeout")

        with patch("joshu.tools.web_search.DDGS") as mock_ddgs_class:
            mock_ddgs_class.return_value = mock_ddgs_instance
            with patch("joshu.tools.web_search.DDGS_AVAILABLE", True):
                result = search_web("test query")

        assert result["success"] is False
        assert "Network timeout" in result["error"]
        assert result["results"] == []

    def test_search_web_max_results(self):
        """Test that max_results parameter is respected."""
        mock_ddgs_instance = Mock()
        mock_ddgs_instance.text.return_value = [
            {"title": f"Result {i}", "href": f"https://example.com/{i}", "body": f"Description {i}"}
            for i in range(3)
        ]

        with patch("joshu.tools.web_search.DDGS") as mock_ddgs_class:
            mock_ddgs_class.return_value = mock_ddgs_instance
            with patch("joshu.tools.web_search.DDGS_AVAILABLE", True):
                result = search_web("test", max_results=3)

        # Verify text was called with max_results=3
        mock_ddgs_instance.text.assert_called_once()
        call_kwargs = mock_ddgs_instance.text.call_args[1]
        assert call_kwargs["max_results"] == 3
        assert len(result["results"]) == 3

    def test_search_web_missing_fields(self):
        """Test handling of results with missing fields."""
        mock_ddgs_instance = Mock()
        mock_ddgs_instance.text.return_value = [
            {
                # Missing title, href, and body
            },
            {
                "title": "Good Result",
                "link": "https://example.com",  # Using 'link' instead of 'href'
                "description": "Using alternate field names",  # Using 'description' instead of 'body'
            },
        ]

        with patch("joshu.tools.web_search.DDGS") as mock_ddgs_class:
            mock_ddgs_class.return_value = mock_ddgs_instance
            with patch("joshu.tools.web_search.DDGS_AVAILABLE", True):
                result = search_web("test")

        assert result["success"] is True
        assert len(result["results"]) == 2

        # First result with missing fields should use defaults
        assert result["results"][0]["title"] == "No title"
        assert result["results"][0]["url"] == ""
        assert result["results"][0]["snippet"] == "No description available"

        # Second result with alternate field names
        assert result["results"][1]["title"] == "Good Result"
        assert result["results"][1]["url"] == "https://example.com"
        assert result["results"][1]["snippet"] == "Using alternate field names"


class TestFormatSearchResults:
    """Test search result formatting."""

    def test_format_success_results(self):
        """Test formatting of successful search results."""
        search_response = {
            "success": True,
            "query": "Python",
            "results": [
                {
                    "title": "Python.org",
                    "url": "https://python.org",
                    "snippet": "Official Python website",
                },
                {
                    "title": "Python Tutorial",
                    "url": "https://example.com/tutorial",
                    "snippet": "Learn Python",
                },
            ],
            "error": None,
        }

        formatted = format_search_results(search_response)

        assert "Search results for: Python" in formatted
        assert "1. Python.org" in formatted
        assert "https://python.org" in formatted
        assert "Official Python website" in formatted
        assert "2. Python Tutorial" in formatted

    def test_format_failed_search(self):
        """Test formatting of failed search."""
        search_response = {
            "success": False,
            "query": "test",
            "results": [],
            "error": "Network error",
        }

        formatted = format_search_results(search_response)

        assert "Search failed" in formatted
        assert "Network error" in formatted

    def test_format_no_results(self):
        """Test formatting when no results found."""
        search_response = {
            "success": True,
            "query": "veryuniquequerywithnoresults",
            "results": [],
            "error": None,
        }

        formatted = format_search_results(search_response)

        assert "No results found" in formatted
        assert "veryuniquequerywithnoresults" in formatted


class TestConfiguration:
    """Test web search configuration integration."""

    def test_config_has_web_search_settings(self):
        """Test that config has web search settings."""
        from joshu.core.config import DEFAULT_CONFIG, JoshuConfig

        assert "web_search_enabled" in DEFAULT_CONFIG
        assert "web_search_max_results" in DEFAULT_CONFIG
        assert "web_search_timeout" in DEFAULT_CONFIG

        config = JoshuConfig()
        assert hasattr(config, "web_search_enabled")
        assert hasattr(config, "web_search_max_results")
        assert hasattr(config, "web_search_timeout")

    def test_config_defaults(self):
        """Test default values for web search config."""
        from joshu.core.config import JoshuConfig

        config = JoshuConfig()
        assert config.web_search_enabled is True
        assert config.web_search_max_results == 5
        assert config.web_search_timeout == 10

    def test_config_from_dict(self):
        """Test loading web search config from dict."""
        from joshu.core.config import JoshuConfig

        config_dict = {
            "web_search_enabled": False,
            "web_search_max_results": 10,
            "web_search_timeout": 20,
        }

        config = JoshuConfig.from_dict(config_dict)
        assert config.web_search_enabled is False
        assert config.web_search_max_results == 10
        assert config.web_search_timeout == 20


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
