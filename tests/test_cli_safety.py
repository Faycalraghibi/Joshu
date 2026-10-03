import unittest
from unittest.mock import patch

from typer.testing import CliRunner

from joshu.ui.cli import app


class TestCLISafety(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    @patch("joshu.ui.cli.translate_to_command")
    @patch("joshu.core.safety.assess_command_safety")
    def test_dangerous_command_blocked(self, mock_assess_safety, mock_translate):
        """Test that dangerous commands are blocked."""
        from joshu.core.translate import Translation

        mock_translation = Translation(
            command="rm -rf /", explanation="Delete everything", needs_execution=True
        )
        mock_translate.return_value = mock_translation
        from joshu.core.safety import SafetyReport

        mock_safety_report = SafetyReport(
            safe=False,
            reasons=["DANGER: This command will delete your entire system"],
            suggested_alternative="rm -i *.tmp",
            danger_level="CRITICAL",
        )
        mock_assess_safety.return_value = mock_safety_report

        # Run the command
        result = self.runner.invoke(app, ["run", "--legacy", "delete everything"])

        # Check that the command was blocked
        assert result.exit_code == 3
        assert (
            "DANGER: This command could cause serious damage" in result.stdout
            or "danger" in result.stdout.lower()
        )
        assert (
            "This command will delete your entire system" in result.stdout
            or "delete" in result.stdout.lower()
        )

    @patch("joshu.ui.cli.translate_to_command")
    @patch("joshu.core.safety.assess_command_safety")
    def test_sandbox_mode_blocks_destructive_commands(self, mock_assess_safety, mock_translate):
        """Test that sandbox mode blocks destructive commands."""
        from joshu.core.translate import Translation

        mock_translation = Translation(
            command="rm file.txt", explanation="Delete a file", needs_execution=True
        )
        mock_translate.return_value = mock_translation
        from joshu.core.safety import SafetyReport

        mock_safety_report = SafetyReport(
            safe=False,
            reasons=["Sandbox mode: All destructive commands are blocked."],
            suggested_alternative="rm -i *.tmp",
            danger_level="CRITICAL",
        )
        mock_assess_safety.return_value = mock_safety_report

        result = self.runner.invoke(app, ["run", "--legacy", "--sandbox", "delete a file"])

        assert result.exit_code == 3
        assert (
            "Sandbox mode: All destructive commands are blocked" in result.stdout
            or "sandbox" in result.stdout.lower()
        )


if __name__ == "__main__":
    unittest.main()
