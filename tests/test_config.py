import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from joshu.core.config import ConfigManager, JoshuConfig, get_config_manager
from joshu.ui.cli import app


class TestConfig(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.test_config_path = Path(self.test_dir) / "config.yaml"

        # Capture stdout/stderr for testing
        self.stdout = io.StringIO()
        self.stderr = io.StringIO()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.test_dir)

    def test_config_creation(self):
        """Test creating JoshuConfig with default values."""
        config = JoshuConfig()
        self.assertEqual(config.model, "llama-3-8b")
        self.assertEqual(config.safety_mode, True)
        self.assertEqual(config.auto_execute, False)
        self.assertEqual(config.max_tokens, 4096)
        self.assertEqual(config.temperature, 0.1)

    def test_config_from_dict(self):
        """Test creating JoshuConfig from dictionary."""
        config_dict = {
            "model": "llama-3-70b",
            "safety_mode": False,
            "auto_execute": True,
            "max_tokens": 2048,
            "temperature": 0.5,
        }
        config = JoshuConfig.from_dict(config_dict)
        self.assertEqual(config.model, "llama-3-70b")
        self.assertEqual(config.safety_mode, False)
        self.assertEqual(config.auto_execute, True)
        self.assertEqual(config.max_tokens, 2048)
        self.assertEqual(config.temperature, 0.5)

    def test_config_with_missing_keys(self):
        """Test creating JoshuConfig with missing keys uses defaults."""
        config_dict = {
            "model": "test-model"
            # Missing other keys should use defaults
        }
        config = JoshuConfig.from_dict(config_dict)
        self.assertEqual(config.model, "test-model")
        # Other values should be defaults
        self.assertEqual(config.safety_mode, True)
        self.assertEqual(config.auto_execute, False)

    def test_config_to_dict(self):
        """Test converting JoshuConfig to dictionary."""
        config = JoshuConfig(model="test-model", auto_execute=True)
        config_dict = config.to_dict()
        self.assertEqual(config_dict["model"], "test-model")
        self.assertEqual(config_dict["auto_execute"], True)
        self.assertEqual(config_dict["safety_mode"], True)

    def test_config_manager_creation(self):
        """Test creating ConfigManager."""
        config_manager = ConfigManager(str(self.test_config_path))
        self.assertEqual(config_manager.config_path, self.test_config_path)
        # Should have default config
        self.assertEqual(config_manager.config.model, "llama-3-8b")

    def test_config_manager_save_and_load(self):
        """Test saving and loading configuration."""
        # Create config manager and modify config
        config_manager = ConfigManager(str(self.test_config_path))
        config_manager.config.model = "test-model"
        config_manager.config.auto_execute = True

        # Save config
        self.assertTrue(config_manager.save_config())

        # Verify file was created
        self.assertTrue(self.test_config_path.exists())

        # Create new config manager to load config
        new_config_manager = ConfigManager(str(self.test_config_path))
        self.assertEqual(new_config_manager.config.model, "test-model")
        self.assertEqual(new_config_manager.config.auto_execute, True)

    def test_config_manager_get_set(self):
        """Test getting and setting configuration values."""
        config_manager = ConfigManager(str(self.test_config_path))

        # Test get
        self.assertEqual(config_manager.get("model"), "llama-3-8b")
        self.assertEqual(config_manager.get("nonexistent", "default"), "default")

        # Test set
        self.assertTrue(config_manager.set("model", "new-model"))
        self.assertEqual(config_manager.get("model"), "new-model")

        # Test setting invalid key
        self.assertFalse(config_manager.set("nonexistent", "value"))

    def test_config_manager_reset_to_defaults(self):
        """Test resetting configuration to defaults."""
        config_manager = ConfigManager(str(self.test_config_path))
        config_manager.config.model = "test-model"
        config_manager.config.auto_execute = True

        # Reset to defaults
        config_manager.reset_to_defaults()

        # Should be back to defaults
        self.assertEqual(config_manager.config.model, "llama-3-8b")
        self.assertEqual(config_manager.config.auto_execute, False)

    def test_get_config_manager_singleton(self):
        """Test that get_config_manager returns singleton instance."""
        config_manager1 = get_config_manager()
        config_manager2 = get_config_manager()
        self.assertIs(config_manager1, config_manager2)

    # CLI Command Tests
    def test_config_list_command(self):
        """Test the config --list command."""
        # Capture output
        with patch("sys.stdout", self.stdout), patch("sys.stderr", self.stderr):
            try:
                app(["config", "--list"], standalone_mode=False)
            except SystemExit:
                pass  # Typer raises SystemExit, which is expected

        output = self.stdout.getvalue()
        # Check that output contains expected configuration keys
        self.assertIn("Current Configuration:", output)
        self.assertIn("model:", output)
        self.assertIn("safety_mode:", output)
        self.assertIn("auto_execute:", output)

    def test_config_get_command(self):
        """Test the config --get command."""
        # Capture output
        with patch("sys.stdout", self.stdout), patch("sys.stderr", self.stderr):
            try:
                app(["config", "--get", "model"], standalone_mode=False)
            except SystemExit:
                pass  # Typer raises SystemExit, which is expected

        output = self.stdout.getvalue()
        # Check that output contains the model value
        self.assertIn("model:", output)

    def test_config_get_nonexistent_key(self):
        """Test the config --get command with nonexistent key."""
        # Capture output
        with patch("sys.stdout", self.stdout), patch("sys.stderr", self.stderr):
            try:
                app(["config", "--get", "nonexistent"], standalone_mode=False)
            except SystemExit:
                pass  # Typer raises SystemExit, which is expected

        output = self.stdout.getvalue()
        # Check that output contains warning about nonexistent key
        self.assertIn("Configuration key 'nonexistent' not found", output)

    def test_config_set_command(self):
        """Test the config --set command."""
        # Capture output
        with patch("sys.stdout", self.stdout), patch("sys.stderr", self.stderr):
            try:
                app(["config", "--set", "temperature=0.5"], standalone_mode=False)
            except SystemExit:
                pass  # Typer raises SystemExit, which is expected

        output = self.stdout.getvalue()
        # Check that output confirms the setting
        self.assertIn("Set temperature = 0.5", output)

        # Verify the value was actually set by getting it
        stdout_get = io.StringIO()
        with patch("sys.stdout", stdout_get), patch("sys.stderr", self.stderr):
            try:
                app(["config", "--get", "temperature"], standalone_mode=False)
            except SystemExit:
                pass  # Typer raises SystemExit, which is expected

        output_get = stdout_get.getvalue()
        self.assertIn("temperature: 0.5", output_get)

    def test_config_set_invalid_format(self):
        """Test the config --set command with invalid format."""
        # Capture output
        with patch("sys.stdout", self.stdout), patch("sys.stderr", self.stderr):
            try:
                app(["config", "--set", "invalidformat"], standalone_mode=False)
            except SystemExit as e:
                self.assertEqual(e.code, 1)  # Should exit with code 1
                pass  # Typer raises SystemExit, which is expected

        output = self.stdout.getvalue()  # Error message goes to stdout, not stderr
        # Check that output contains error message
        self.assertIn("Invalid format", output)

    def test_config_reset_command(self):
        """Test the config --reset command."""
        # First set a value
        with patch("sys.stdout", io.StringIO()), patch("sys.stderr", io.StringIO()):
            try:
                app(["config", "--set", "temperature=0.8"], standalone_mode=False)
            except SystemExit:
                pass  # Typer raises SystemExit, which is expected

        # Then reset
        with patch("sys.stdout", self.stdout), patch("sys.stderr", self.stderr):
            try:
                app(["config", "--reset"], standalone_mode=False)
            except SystemExit:
                pass  # Typer raises SystemExit, which is expected

        output = self.stdout.getvalue()
        # Check that output confirms reset
        self.assertIn("Configuration reset to defaults", output)

        # Verify the value was reset by getting it
        stdout_get = io.StringIO()
        with patch("sys.stdout", stdout_get), patch("sys.stderr", self.stderr):
            try:
                app(["config", "--get", "temperature"], standalone_mode=False)
            except SystemExit:
                pass  # Typer raises SystemExit, which is expected

        output_get = stdout_get.getvalue()
        self.assertIn("temperature: 0.1", output_get)  # Default value

    def test_config_edit_command_success(self):
        """Test the config --edit command when editor is available."""
        # Mock subprocess.run to simulate successful editor launch
        with (
            patch("subprocess.run") as mock_run,
            patch("sys.stdout", self.stdout),
            patch("sys.stderr", self.stderr),
        ):
            mock_run.return_value = MagicMock(returncode=0)
            try:
                app(["config", "--edit"], standalone_mode=False)
            except SystemExit:
                pass  # Typer raises SystemExit, which is expected

        output = self.stdout.getvalue()
        # Check that output confirms edit
        self.assertIn("Configuration file edited and reloaded", output)

    def test_config_edit_command_failure(self):
        """Test the config --edit command when editor is not available."""
        # Mock subprocess.run to simulate editor failure
        with (
            patch("subprocess.run") as mock_run,
            patch("sys.stdout", self.stdout),
            patch("sys.stderr", self.stderr),
        ):
            mock_run.side_effect = Exception("Editor not found")
            try:
                app(["config", "--edit"], standalone_mode=False)
            except SystemExit:
                pass  # Typer raises SystemExit, which is expected

        output = self.stdout.getvalue()
        # Check that output shows error and manual edit suggestion
        self.assertIn("Failed to open editor", output)
        self.assertIn("You can manually edit", output)

    def test_config_no_options(self):
        """Test the config command with no options."""
        # Capture output
        with patch("sys.stdout", self.stdout), patch("sys.stderr", self.stderr):
            try:
                app(["config"], standalone_mode=False)
            except SystemExit:
                pass  # Typer raises SystemExit, which is expected

        output = self.stdout.getvalue()
        # Check that output shows help message
        self.assertIn("Joshu Configuration Manager", output)
        self.assertIn("Use --help for more information", output)

    def test_config_set_boolean_values(self):
        """Test the config --set command with boolean values."""
        test_cases = [
            ("true", True),
            ("True", True),
            ("false", False),
            ("False", False),
        ]

        for input_val, expected in test_cases:
            with self.subTest(input_val=input_val):
                # Capture output
                stdout = io.StringIO()
                with patch("sys.stdout", stdout), patch("sys.stderr", self.stderr):
                    try:
                        app(["config", "--set", f"safety_mode={input_val}"], standalone_mode=False)
                    except SystemExit:
                        pass  # Typer raises SystemExit, which is expected

                output = stdout.getvalue()
                # Check that output confirms the setting
                self.assertIn(f"Set safety_mode = {expected}", output)

                # Verify the value was actually set by getting it
                stdout_get = io.StringIO()
                with patch("sys.stdout", stdout_get), patch("sys.stderr", self.stderr):
                    try:
                        app(["config", "--get", "safety_mode"], standalone_mode=False)
                    except SystemExit:
                        pass  # Typer raises SystemExit, which is expected

                output_get = stdout_get.getvalue()
                self.assertIn(f"safety_mode: {expected}", output_get)

    def test_config_set_numeric_values(self):
        """Test the config --set command with numeric values."""
        test_cases = [
            ("4096", 4096),  # integer
            ("0.8", 0.8),  # float
        ]

        for input_val, expected in test_cases:
            with self.subTest(input_val=input_val):
                # Capture output
                stdout = io.StringIO()
                with patch("sys.stdout", stdout), patch("sys.stderr", self.stderr):
                    try:
                        app(["config", "--set", f"max_tokens={input_val}"], standalone_mode=False)
                    except SystemExit:
                        pass  # Typer raises SystemExit, which is expected

                output = stdout.getvalue()
                # Check that output confirms the setting
                self.assertIn(f"Set max_tokens = {expected}", output)

                # Verify the value was actually set by getting it
                stdout_get = io.StringIO()
                with patch("sys.stdout", stdout_get), patch("sys.stderr", self.stderr):
                    try:
                        app(["config", "--get", "max_tokens"], standalone_mode=False)
                    except SystemExit:
                        pass  # Typer raises SystemExit, which is expected

                output_get = stdout_get.getvalue()
                self.assertIn(f"max_tokens: {expected}", output_get)

    def test_config_set_invalid_key(self):
        """Test the config --set command with invalid key."""
        # Capture output
        with patch("sys.stdout", self.stdout), patch("sys.stderr", self.stderr):
            try:
                app(["config", "--set", "invalid_key=true"], standalone_mode=False)
            except SystemExit as e:
                self.assertEqual(e.code, 1)  # Should exit with code 1
                pass  # Typer raises SystemExit, which is expected

        output = self.stdout.getvalue()
        # Check that output contains error message
        self.assertIn("Invalid configuration key: invalid_key", output)


if __name__ == "__main__":
    unittest.main()
