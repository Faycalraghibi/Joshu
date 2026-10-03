"""
Tests for the Memory Tool (save_memory) and Project System Prompt.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from joshu.tools.memory import (
    PROJECT_SYSTEM_PROMPT_FILE,
    _format_memory_content,
    _parse_memory_facts,
    clear_memory,
    find_project_root,
    get_memory_path,
    load_combined_context,
    load_memory,
    load_project_system_prompt,
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


class TestFindProjectRoot:
    """Tests for finding project root by joshu.md."""

    def test_find_project_root_with_joshu_md(self):
        """Should find project root when joshu.md exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            joshu_file = project_root / PROJECT_SYSTEM_PROMPT_FILE
            joshu_file.parent.mkdir(parents=True, exist_ok=True)
            joshu_file.write_text("# Test joshu.md", encoding="utf-8")

            # Test from project root
            result = find_project_root(project_root)
            assert result.resolve() == project_root.resolve()

    def test_find_project_root_from_subdirectory(self):
        """Should find project root when starting from subdirectory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            joshu_file = project_root / PROJECT_SYSTEM_PROMPT_FILE
            joshu_file.parent.mkdir(parents=True, exist_ok=True)
            joshu_file.write_text("# Test joshu.md", encoding="utf-8")

            sub_dir = project_root / "src" / "joshu" / "tools"
            sub_dir.mkdir(parents=True)

            # Test from subdirectory
            result = find_project_root(sub_dir)
            assert result.resolve() == project_root.resolve()

    def test_find_project_root_no_joshu_md(self):
        """Should return None when no joshu.md exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            result = find_project_root(project_root)
            assert result is None

    def test_find_project_root_uses_cwd_by_default(self):
        """Should use current working directory when no path provided."""
        # This test verifies the function uses Path.cwd() when no argument
        with patch("joshu.tools.memory.Path.cwd") as mock_cwd:
            mock_cwd.return_value = Path("/fake/path")
            # The function will try to find joshu.md starting from /fake/path
            # It won't find it, so it returns None
            find_project_root(None)
            # The mock is called during the function execution
            mock_cwd.assert_called()


class TestLoadProjectSystemPrompt:
    """Tests for loading project system prompt from joshu.md."""

    def test_load_project_system_prompt_success(self):
        """Should load content from joshu.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            joshu_content = """# joshu.md — AI Agent System Prompt

## Hard Rules

- DO NOT break things
- ALWAYS test your code
"""
            joshu_file = project_root / PROJECT_SYSTEM_PROMPT_FILE
            joshu_file.parent.mkdir(parents=True, exist_ok=True)
            joshu_file.write_text(joshu_content, encoding="utf-8")

            result = load_project_system_prompt(project_root)

            assert result == joshu_content
            assert "Hard Rules" in result
            assert "DO NOT break things" in result

    def test_load_project_system_prompt_not_found(self):
        """Should return empty string when joshu.md not found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            result = load_project_system_prompt(project_root)

            assert result == ""

    def test_load_project_system_prompt_from_subdirectory(self):
        """Should find and load joshu.md from subdirectory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            joshu_content = "# Project Rules"
            joshu_file = project_root / PROJECT_SYSTEM_PROMPT_FILE
            joshu_file.parent.mkdir(parents=True, exist_ok=True)
            joshu_file.write_text(joshu_content, encoding="utf-8")

            sub_dir = project_root / "deep" / "nested" / "dir"
            sub_dir.mkdir(parents=True)

            result = load_project_system_prompt(sub_dir)

            assert result == joshu_content


class TestLoadCombinedContext:
    """Tests for loading combined project + user context."""

    def test_load_combined_context_project_only(self):
        """Should return project context when only joshu.md exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            joshu_content = "# Project Rules"
            joshu_file = project_root / PROJECT_SYSTEM_PROMPT_FILE
            joshu_file.parent.mkdir(parents=True, exist_ok=True)
            joshu_file.write_text(joshu_content, encoding="utf-8")

            with patch("joshu.tools.memory.load_memory", return_value=""):
                result = load_combined_context(project_root)

            assert "# Project System Prompt" in result
            assert "# Project Rules" in result

    def test_load_combined_context_both(self):
        """Should combine project and user context."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            joshu_content = "# Project Rules"
            joshu_file = project_root / PROJECT_SYSTEM_PROMPT_FILE
            joshu_file.parent.mkdir(parents=True, exist_ok=True)
            joshu_file.write_text(joshu_content, encoding="utf-8")

            user_memory = "# Joshu Memory\n\n## Agent Memory\n\n- User prefers vim"

            with patch("joshu.tools.memory.load_memory", return_value=user_memory):
                result = load_combined_context(project_root)

            assert "# Project System Prompt" in result
            assert "# Project Rules" in result
            assert "# User Memory" in result
            assert "User prefers vim" in result

    def test_load_combined_context_user_only(self):
        """Should return user context when no joshu.md exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            user_memory = "# Joshu Memory\n\n## Agent Memory\n\n- User prefers vim"

            with patch("joshu.tools.memory.load_memory", return_value=user_memory):
                result = load_combined_context(project_root)

            assert "# Project System Prompt" not in result
            assert "# User Memory" in result
            assert "User prefers vim" in result

    def test_load_combined_context_empty(self):
        """Should return empty string when no context available."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            with patch("joshu.tools.memory.load_memory", return_value=""):
                result = load_combined_context(project_root)

            assert result == ""


class TestContextProviderIntegration:
    """Tests for ContextProvider integration with project system prompt."""

    def test_context_provider_loads_project_prompt(self):
        """ContextProvider should load project system prompt on init."""
        with patch("joshu.core.context_provider.load_project_system_prompt") as mock_load:
            mock_load.return_value = "# Test Project Rules"

            from joshu.core.context_provider import ContextProvider

            cp = ContextProvider()

            assert cp.project_system_prompt == "# Test Project Rules"

    def test_context_provider_includes_prompt_in_context(self):
        """get_relevant_context should include project prompt first."""
        with patch("joshu.core.context_provider.load_project_system_prompt") as mock_load:
            mock_load.return_value = "# Test Project Rules"

            from joshu.core.context_provider import ContextProvider

            cp = ContextProvider()
            context = cp.get_relevant_context("test query")

            # First message should be the project system prompt
            assert len(context) > 0
            assert context[0]["role"] == "system"
            assert context[0]["content"] == "# Test Project Rules"

    def test_context_provider_handles_no_project_prompt(self):
        """ContextProvider should work without project prompt."""
        with patch("joshu.core.context_provider.load_project_system_prompt") as mock_load:
            mock_load.return_value = ""

            from joshu.core.context_provider import ContextProvider

            cp = ContextProvider()
            context = cp.get_relevant_context("test query")

            # Should not have project prompt in context
            assert cp.project_system_prompt == ""
            # Context may have other system messages but not project prompt
            for msg in context:
                if msg["role"] == "system":
                    assert "# Test Project Rules" not in msg["content"]
