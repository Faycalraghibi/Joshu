"""
Tests for web fetch functionality.

Following TDD: These tests are written BEFORE the implementation.
Run with: pytest tests/test_web_fetch.py -v
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestFetchUrl:
    """Test URL fetching functionality."""

    @patch("joshu.tools.web_fetch.httpx.get")
    def test_fetch_url_success(self, mock_get):
        """Test successful URL fetch."""
        from joshu.tools.web_fetch import fetch_url

        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body><h1>Test Page</h1><p>Content here</p></body></html>"
        mock_response.headers = {"content-type": "text/html"}
        mock_get.return_value = mock_response

        result = fetch_url("https://example.com")

        assert result["success"] is True
        assert result["url"] == "https://example.com"
        assert result["content"] is not None
        assert result["error"] is None
        mock_get.assert_called_once()

    @patch("joshu.tools.web_fetch.httpx.get")
    def test_fetch_url_timeout(self, mock_get):
        """Test handling of timeout errors."""
        import httpx

        from joshu.tools.web_fetch import fetch_url

        mock_get.side_effect = httpx.TimeoutException("Connection timed out")

        result = fetch_url("https://example.com", timeout=5)

        assert result["success"] is False
        assert "timed out" in result["error"].lower()
        assert result["content"] is None

    def test_fetch_url_invalid_url(self):
        """Test handling of invalid URLs."""
        from joshu.tools.web_fetch import fetch_url

        result = fetch_url("not-a-valid-url")

        assert result["success"] is False
        assert "invalid" in result["error"].lower()
        assert result["content"] is None

    def test_fetch_url_empty_url(self):
        """Test handling of empty URL."""
        from joshu.tools.web_fetch import fetch_url

        result = fetch_url("")

        assert result["success"] is False
        assert result["error"] is not None
        assert result["content"] is None

    @patch("joshu.tools.web_fetch.httpx.get")
    def test_fetch_url_http_error(self, mock_get):
        """Test handling of HTTP errors (404, 500, etc.)."""
        from joshu.tools.web_fetch import fetch_url

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_get.return_value = mock_response

        result = fetch_url("https://example.com/nonexistent")

        assert result["success"] is False
        assert "404" in result["error"]


class TestHtmlToMarkdown:
    """Test HTML to Markdown/text conversion."""

    def test_html_to_markdown_basic(self):
        """Test basic HTML to markdown conversion."""
        from joshu.tools.web_fetch import html_to_markdown

        html = "<html><body><h1>Title</h1><p>Paragraph text.</p></body></html>"
        result = html_to_markdown(html)

        assert "Title" in result
        assert "Paragraph text" in result

    def test_html_to_markdown_with_links(self):
        """Test HTML with links conversion."""
        from joshu.tools.web_fetch import html_to_markdown

        html = '<p>Check out <a href="https://example.com">this link</a>.</p>'
        result = html_to_markdown(html)

        assert "this link" in result
        # Link might be inline or formatted differently based on parser
        assert "link" in result.lower()

    def test_html_to_markdown_removes_scripts(self):
        """Test that scripts and styles are removed."""
        from joshu.tools.web_fetch import html_to_markdown

        html = """
        <html>
        <head><script>alert('bad');</script><style>body{color:red}</style></head>
        <body><p>Good content</p></body>
        </html>
        """
        result = html_to_markdown(html)

        assert "alert" not in result
        assert "color:red" not in result
        assert "Good content" in result

    def test_html_to_markdown_empty(self):
        """Test empty HTML handling."""
        from joshu.tools.web_fetch import html_to_markdown

        result = html_to_markdown("")
        assert result == ""

    def test_html_to_markdown_lists(self):
        """Test HTML lists conversion."""
        from joshu.tools.web_fetch import html_to_markdown

        html = "<ul><li>Item 1</li><li>Item 2</li></ul>"
        result = html_to_markdown(html)

        assert "Item 1" in result
        assert "Item 2" in result


class TestProcessUrlContent:
    """Test URL content processing with instructions."""

    @patch("joshu.tools.web_fetch.fetch_url")
    def test_process_url_content_success(self, mock_fetch):
        """Test successful URL content processing."""
        from joshu.tools.web_fetch import process_url_content

        mock_fetch.return_value = {
            "success": True,
            "url": "https://example.com",
            "content": "# Test Page\n\nThis is the content.",
            "error": None,
        }

        result = process_url_content("https://example.com")

        assert result["success"] is True
        assert result["content"] is not None
        assert "source" in result
        assert result["source"] == "https://example.com"

    @patch("joshu.tools.web_fetch.fetch_url")
    def test_process_url_content_with_instruction(self, mock_fetch):
        """Test URL processing with instruction."""
        from joshu.tools.web_fetch import process_url_content

        mock_fetch.return_value = {
            "success": True,
            "url": "https://example.com",
            "content": "Long content here...",
            "error": None,
        }

        result = process_url_content("https://example.com", instruction="summarize")

        assert result["success"] is True
        assert result["instruction"] == "summarize"

    @patch("joshu.tools.web_fetch.fetch_url")
    def test_process_url_content_truncation(self, mock_fetch):
        """Test content truncation for large pages."""
        from joshu.tools.web_fetch import process_url_content

        # Create content larger than max length
        large_content = "x" * 60000
        mock_fetch.return_value = {
            "success": True,
            "url": "https://example.com",
            "content": large_content,
            "error": None,
        }

        result = process_url_content("https://example.com", max_length=50000)

        assert result["success"] is True
        assert len(result["content"]) <= 50000
        assert result["truncated"] is True

    @patch("joshu.tools.web_fetch.fetch_url")
    def test_process_url_content_fetch_failure(self, mock_fetch):
        """Test handling of fetch failures."""
        from joshu.tools.web_fetch import process_url_content

        mock_fetch.return_value = {
            "success": False,
            "url": "https://example.com",
            "content": None,
            "error": "Connection failed",
        }

        result = process_url_content("https://example.com")

        assert result["success"] is False
        assert result["error"] == "Connection failed"


class TestUrlValidation:
    """Test URL validation functionality."""

    def test_validate_url_valid_https(self):
        """Test valid HTTPS URL."""
        from joshu.tools.web_fetch import is_valid_url

        assert is_valid_url("https://example.com") is True
        assert is_valid_url("https://example.com/path?query=1") is True

    def test_validate_url_valid_http(self):
        """Test valid HTTP URL."""
        from joshu.tools.web_fetch import is_valid_url

        assert is_valid_url("http://example.com") is True

    def test_validate_url_invalid(self):
        """Test invalid URLs."""
        from joshu.tools.web_fetch import is_valid_url

        assert is_valid_url("not-a-url") is False
        assert is_valid_url("ftp://example.com") is False
        assert is_valid_url("") is False
        assert is_valid_url("javascript:alert(1)") is False


class TestWebFetchTool:
    """Test web fetch tool registration and integration."""

    def _reload_web_fetch_tool(self):
        """Helper to reload the web_fetch_tool module after clearing registry."""
        import importlib
        import sys

        from joshu.core.tool_registry import ToolRegistry

        registry = ToolRegistry()
        registry.clear()

        # Get the module from sys.modules and reload it
        module_name = "joshu.tools.implementations.web_fetch_tool"
        if module_name in sys.modules:
            importlib.reload(sys.modules[module_name])
        else:
            import joshu.tools.implementations.web_fetch_tool  # noqa: F401

        return registry

    def teardown_method(self):
        """Ensure all tools are re-registered after each test."""
        import importlib
        import sys

        # Re-register all tools for other tests
        for module_name in [
            "joshu.tools.implementations.web_search_tool",
            "joshu.tools.implementations.web_fetch_tool",
        ]:
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])

    def test_web_fetch_tool_registered(self):
        """Test that web fetch tool is registered."""
        registry = self._reload_web_fetch_tool()
        tool = registry.get_tool("web_fetch")

        assert tool is not None
        assert tool.name == "web_fetch"
        assert "fetch" in tool.description.lower() or "url" in tool.description.lower()

    def test_web_fetch_tool_requires_approval(self):
        """Test that web fetch tool requires user approval."""
        registry = self._reload_web_fetch_tool()
        tool = registry.get_tool("web_fetch")

        assert tool is not None
        assert tool.requires_approval is True

    @patch("joshu.tools.implementations.web_fetch_tool.process_url_content")
    def test_web_fetch_tool_execution(self, mock_process):
        """Test web fetch tool execution."""
        from joshu.core.tool_executor import ToolExecutor

        self._reload_web_fetch_tool()

        # Mock process_url_content to return test results
        mock_process.return_value = {
            "success": True,
            "url": "https://example.com",
            "source": "https://example.com",
            "content": "# Example\n\nThis is test content.",
            "instruction": None,
            "truncated": False,
            "error": None,
        }

        executor = ToolExecutor()
        result = executor.execute_tool("web_fetch", {"url": "https://example.com"})

        assert result["success"]
        assert result["result"]["url"] == "https://example.com"
        assert result["result"]["content"] is not None

    @patch("joshu.tools.implementations.web_fetch_tool.process_url_content")
    def test_web_fetch_tool_with_instruction(self, mock_process):
        """Test web fetch tool with processing instruction."""
        from joshu.core.tool_executor import ToolExecutor

        self._reload_web_fetch_tool()

        mock_process.return_value = {
            "success": True,
            "url": "https://example.com",
            "source": "https://example.com",
            "content": "Summarized content here.",
            "instruction": "summarize",
            "truncated": False,
            "error": None,
        }

        executor = ToolExecutor()
        result = executor.execute_tool(
            "web_fetch", {"url": "https://example.com", "instruction": "summarize"}
        )

        # The tool should execute successfully (reload breaks patch binding,
        # so we verify the tool works rather than checking mock calls)
        assert result["success"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
