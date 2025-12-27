"""
Tests for extension CLI commands and TOML command parsing.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from joshu.commands.extensions import (
    extension_disable,
    extension_enable,
    extension_list,
    extension_new,
)
from joshu.commands.types import ErrorActionReturn, MessageActionReturn
from joshu.extensions.commands import (
    TOMLCommand,
    discover_toml_commands,
)


class TestExtensionNew:
    """Tests for extension_new command."""

    def test_create_basic_extension(self):
        """Should create a basic extension."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = extension_new("test-ext", output_dir=tmpdir)

            assert isinstance(result, MessageActionReturn)
            assert "Created extension" in result.message

            # Verify files created
            ext_path = Path(tmpdir) / "test-ext"
            assert ext_path.exists()
            assert (ext_path / "joshu-extension.json").exists()
            assert (ext_path / "JOSHU.md").exists()
            assert (ext_path / "commands").is_dir()

    def test_create_fails_if_exists(self):
        """Should fail if directory exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create existing directory
            ext_path = Path(tmpdir) / "existing"
            ext_path.mkdir()

            result = extension_new("existing", output_dir=tmpdir)

            assert isinstance(result, ErrorActionReturn)
            assert "already exists" in result.error_message


class TestExtensionList:
    """Tests for extension_list command."""

    @patch("joshu.commands.extensions.get_extension_registry")
    def test_list_empty(self, mock_get_registry):
        """Should handle no extensions."""
        mock_registry = MagicMock()
        mock_registry.list_extensions.return_value = []
        mock_get_registry.return_value = mock_registry

        result = extension_list()

        assert isinstance(result, MessageActionReturn)
        assert "No extensions" in result.message

    @patch("joshu.commands.extensions.get_extension_registry")
    def test_list_with_extensions(self, mock_get_registry):
        """Should list installed extensions."""
        # Create a fully mocked path to avoid PosixPath read-only attribute issues
        mock_path = MagicMock()
        mock_path.is_symlink.return_value = False
        mock_path.__str__ = MagicMock(return_value="/some/path")

        mock_ext = MagicMock()
        mock_ext.name = "test-ext"
        mock_ext.version = "1.0.0"
        mock_ext.is_active = True
        mock_ext.path = mock_path
        mock_ext.loaded_tools = {"tool1": lambda: None}
        mock_ext.loaded_commands = {}

        mock_registry = MagicMock()
        mock_registry.list_extensions.return_value = [mock_ext]
        mock_registry.get_status.return_value = {"test-ext": {}}
        mock_get_registry.return_value = mock_registry

        result = extension_list()

        assert isinstance(result, MessageActionReturn)
        assert "test-ext" in result.message


class TestExtensionEnableDisable:
    """Tests for enable/disable commands."""

    @patch("joshu.commands.extensions.get_extension_registry")
    def test_enable_success(self, mock_get_registry):
        """Should enable extension."""
        mock_registry = MagicMock()
        mock_registry.enable.return_value = True
        mock_get_registry.return_value = mock_registry

        result = extension_enable("test-ext")

        assert isinstance(result, MessageActionReturn)
        assert "Enabled" in result.message

    @patch("joshu.commands.extensions.get_extension_registry")
    def test_disable_success(self, mock_get_registry):
        """Should disable extension."""
        mock_registry = MagicMock()
        mock_registry.disable.return_value = True
        mock_get_registry.return_value = mock_registry

        result = extension_disable("test-ext")

        assert isinstance(result, MessageActionReturn)
        assert "Disabled" in result.message


class TestTOMLCommand:
    """Tests for TOML command parsing."""

    def test_substitute_placeholders(self):
        """Should substitute placeholders in prompt."""
        cmd = TOMLCommand(
            name="test",
            prompt="Hello {{name}}, deploy to {{env}}",
        )

        result = cmd.substitute({"name": "World", "env": "production"})

        assert result == "Hello World, deploy to production"

    def test_substitute_missing_placeholder(self):
        """Should keep placeholder if value missing."""
        cmd = TOMLCommand(
            name="test",
            prompt="Hello {{name}}",
        )

        result = cmd.substitute({})

        assert result == "Hello {{name}}"

    def test_build_prompt_with_args(self):
        """Should build prompt with args substitution."""
        cmd = TOMLCommand(
            name="test",
            prompt="Processing: {{args}}",
        )

        result = cmd.build_prompt(args="file.txt")

        assert result == "Processing: file.txt"


class TestTOMLCommandDiscovery:
    """Tests for TOML command discovery."""

    def test_discover_from_empty_dir(self):
        """Should return empty list for non-existent commands dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            commands = discover_toml_commands(Path(tmpdir), "test-ext")
            assert commands == []

    def test_discover_toml_files(self):
        """Should discover TOML files in commands directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create commands directory
            commands_dir = Path(tmpdir) / "commands"
            commands_dir.mkdir()

            # Create a TOML file
            toml_file = commands_dir / "deploy.toml"
            toml_file.write_text(
                """
[command]
description = "Deploy application"
prompt = "Deploy to {{env}}"
shell = "git push origin main"
"""
            )

            commands = discover_toml_commands(Path(tmpdir), "test-ext")

            assert len(commands) == 1
            assert commands[0].name == "deploy"
            assert commands[0].description == "Deploy application"
