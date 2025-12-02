"""
Tests for CLI search command integration.
"""

from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from joshu.ui.cli import app


class TestCLISearchCommand:
    """Test the joshu search CLI command."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_search_command_success(self):
        """Test successful search command execution."""
        # Mock the handle_search_command function
        with patch("joshu.ui.cli.handle_search_command") as mock_handler:
            self.runner.invoke(app, ["search", "Python programming"])

            # Should call the handler with the query
            mock_handler.assert_called_once_with("Python programming", None)

    def test_search_command_with_max_results(self):
        """Test search command with --max-results flag."""
        with patch("joshu.ui.cli.handle_search_command") as mock_handler:
            self.runner.invoke(app, ["search", "Python", "--max-results", "10"])

            # Should call handler with max_results=10
            mock_handler.assert_called_once_with("Python", 10)

    def test_search_command_without_query(self):
        """Test search command without providing a query."""
        result = self.runner.invoke(app, ["search"])

        # Should fail because query is required
        assert result.exit_code != 0

    def test_search_command_multiword_query(self):
        """Test search with multi-word query."""
        with patch("joshu.ui.cli.handle_search_command") as mock_handler:
            self.runner.invoke(app, ["search", "Python machine learning best practices"])

            # Should join all words into single query
            mock_handler.assert_called_once_with("Python machine learning best practices", None)


class TestSearchHandler:
    """Test the search handler functionality."""

    def test_handle_search_disabled(self):
        """Test search when web_search is disabled in config."""
        from joshu.ui.cli_handlers.search_handler import handle_search_command

        with patch("joshu.ui.cli_handlers.search_handler.get_config_manager") as mock_config:
            mock_config_inst = Mock()
            mock_config_inst.get.return_value = False  # web_search_enabled = False
            mock_config.return_value = mock_config_inst

            with patch("joshu.ui.cli_handlers.search_handler.console") as mock_console:
                handle_search_command("test query")

                # Should print disabled message
                assert any(
                    "disabled" in str(call).lower() for call in mock_console.print.call_args_list
                )

    def test_handle_search_library_not_available(self):
        """Test search when duckduckgo_search library is not available."""
        from joshu.ui.cli_handlers.search_handler import handle_search_command

        with patch("joshu.ui.cli_handlers.search_handler.get_config_manager") as mock_config:
            mock_config_inst = Mock()
            mock_config_inst.get.side_effect = lambda key, default: {
                "web_search_enabled": True
            }.get(key, default)
            mock_config.return_value = mock_config_inst

            with patch("joshu.ui.cli_handlers.search_handler.DDGS_AVAILABLE", False):
                with patch("joshu.ui.cli_handlers.search_handler.console") as mock_console:
                    handle_search_command("test query")

                    # Should print library not installed message
                    assert any(
                        "not installed" in str(call).lower()
                        for call in mock_console.print.call_args_list
                    )

    def test_handle_search_success(self):
        """Test successful search execution."""
        from joshu.ui.cli_handlers.search_handler import handle_search_command

        mock_results = {
            "success": True,
            "query": "test query",
            "results": [
                {
                    "title": "Test Result",
                    "url": "https://example.com",
                    "snippet": "This is a test result",
                }
            ],
        }

        with patch("joshu.ui.cli_handlers.search_handler.get_config_manager") as mock_config:
            mock_config_inst = Mock()
            mock_config_inst.get.side_effect = lambda key, default: {
                "web_search_enabled": True,
                "web_search_max_results": 5,
                "web_search_timeout": 10,
            }.get(key, default)
            mock_config.return_value = mock_config_inst

            with patch("joshu.ui.cli_handlers.search_handler.DDGS_AVAILABLE", True):
                with patch("joshu.ui.cli_handlers.search_handler.search_web") as mock_search:
                    mock_search.return_value = mock_results

                    with patch("joshu.ui.cli_handlers.search_handler.console") as mock_console:
                        handle_search_command("test query", max_results=5)

                        # Should call search_web
                        mock_search.assert_called_once_with("test query", max_results=5, timeout=10)

                        # Should print results
                        print_calls = [str(call) for call in mock_console.print.call_args_list]
                        results_printed = any("result" in call.lower() for call in print_calls)
                        assert results_printed

    def test_handle_search_no_results(self):
        """Test search with no results found."""
        from joshu.ui.cli_handlers.search_handler import handle_search_command

        mock_results = {"success": True, "query": "veryuniquequerywithnoresults", "results": []}

        with patch("joshu.ui.cli_handlers.search_handler.get_config_manager") as mock_config:
            mock_config_inst = Mock()
            mock_config_inst.get.side_effect = lambda key, default: {
                "web_search_enabled": True,
                "web_search_max_results": 5,
                "web_search_timeout": 10,
            }.get(key, default)
            mock_config.return_value = mock_config_inst

            with patch("joshu.ui.cli_handlers.search_handler.DDGS_AVAILABLE", True):
                with patch("joshu.ui.cli_handlers.search_handler.search_web") as mock_search:
                    mock_search.return_value = mock_results

                    with patch("joshu.ui.cli_handlers.search_handler.console") as mock_console:
                        handle_search_command("veryuniquequerywithnoresults")

                        # Should print no results message
                        print_calls = [str(call) for call in mock_console.print.call_args_list]
                        no_results = any("no results" in call.lower() for call in print_calls)
                        assert no_results

    def test_handle_search_failure(self):
        """Test search failure handling."""
        from joshu.ui.cli_handlers.search_handler import handle_search_command

        mock_results = {
            "success": False,
            "query": "test query",
            "results": [],
            "error": "Network timeout",
        }

        with patch("joshu.ui.cli_handlers.search_handler.get_config_manager") as mock_config:
            mock_config_inst = Mock()
            mock_config_inst.get.side_effect = lambda key, default: {
                "web_search_enabled": True,
                "web_search_max_results": 5,
                "web_search_timeout": 10,
            }.get(key, default)
            mock_config.return_value = mock_config_inst

            with patch("joshu.ui.cli_handlers.search_handler.DDGS_AVAILABLE", True):
                with patch("joshu.ui.cli_handlers.search_handler.search_web") as mock_search:
                    mock_search.return_value = mock_results

                    with patch("joshu.ui.cli_handlers.search_handler.console") as mock_console:
                        handle_search_command("test query")

                        # Should print error message
                        print_calls = [str(call) for call in mock_console.print.call_args_list]
                        error_shown = any("network timeout" in call.lower() for call in print_calls)
                        assert error_shown


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
