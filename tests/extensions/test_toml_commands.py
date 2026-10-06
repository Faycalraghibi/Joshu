"""
Tests for extension CLI commands and TOML command parsing.
"""

import tempfile
from pathlib import Path

from joshu.extensions.commands import (
    TOMLCommand,
    discover_toml_commands,
)


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
