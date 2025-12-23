"""
Tests for the Memory Tool (save_memory).
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from joshu.tools.memory import (
    _format_memory_content,
    _parse_memory_facts,
    clear_memory,
    get_memory_path,
    load_memory,
    save_memory_tool,
)


class TestMemoryPath:
    """Tests for memory path handling."""

    def test_get_memory_path_returns_path(self):
        """Memory path should be a valid Path object."""
        path = get_memory_path()
        assert isinstance(path, Path)
        assert path.name == "JOSHU.md"
        assert ".joshu" in str(path)


class TestMemoryParsing:
    """Tests for memory content parsing."""

    def test_parse_empty_content(self):
        """Empty content should return empty list."""
        facts = _parse_memory_facts("")
        assert facts == []

    def test_parse_memory_facts(self):
        """Should parse facts from markdown content."""
        content = """# Joshu Memory

## Agent Memory

- User prefers dark mode
- Project uses Python 3.11
- Important deadline: 2024-12-31

## Other Section

- Should not be included
"""
        facts = _parse_memory_facts(content)
        assert len(facts) == 3
        assert "User prefers dark mode" in facts
        assert "Project uses Python 3.11" in facts
        assert "Important deadline: 2024-12-31" in facts
        assert "Should not be included" not in facts

    def test_format_memory_content(self):
        """Should format facts into valid markdown."""
        facts = ["Fact one", "Fact two"]
        content = _format_memory_content(facts)

        assert "# Joshu Memory" in content
        assert "## Agent Memory" in content
        assert "- Fact one" in content
        assert "- Fact two" in content


class TestSaveMemoryTool:
    """Tests for the save_memory tool."""

    @patch("joshu.tools.memory.save_memory_to_file")
    def test_save_memory_success(self, mock_save):
        """Should save valid facts."""
        mock_save.return_value = {
            "success": True,
            "message": "Saved 2 new facts",
            "total_facts": 2,
            "new_facts": 2,
        }

        result = save_memory_tool(["Fact one", "Fact two"])

        assert result["success"] is True
        mock_save.assert_called_once()

    def test_save_memory_empty_list(self):
        """Should fail with empty list."""
        result = save_memory_tool([])

        assert result["success"] is False
        assert "error" in result

    def test_save_memory_all_empty_strings(self):
        """Should fail if all facts are empty strings."""
        result = save_memory_tool(["", "   ", ""])

        assert result["success"] is False
        assert "empty" in result["error"].lower()

    def test_save_memory_filters_empty(self):
        """Should filter out empty facts and save valid ones."""
        with patch("joshu.tools.memory.save_memory_to_file") as mock_save:
            mock_save.return_value = {"success": True, "new_facts": 1}

            save_memory_tool(["", "Valid fact", "  "])

            # Should only save the valid fact
            call_args = mock_save.call_args[0][0]
            assert "Valid fact" in call_args
            assert "" not in call_args


class TestClearMemory:
    """Tests for clearing memory."""

    @patch("joshu.tools.memory.get_memory_path")
    def test_clear_nonexistent_memory(self, mock_path):
        """Should succeed when no memory file exists."""
        mock_path.return_value = MagicMock(exists=MagicMock(return_value=False))

        result = clear_memory()

        assert result["success"] is True
        assert "No memory" in result["message"]


class TestLoadMemory:
    """Tests for loading memory."""

    @patch("joshu.tools.memory.get_memory_path")
    def test_load_nonexistent_memory(self, mock_path):
        """Should return empty string when no memory file."""
        mock_path.return_value = MagicMock(exists=MagicMock(return_value=False))

        content = load_memory()

        assert content == ""
