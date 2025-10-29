import unittest
from unittest.mock import patch, MagicMock
from joshu.ui.cli import app
from typer.testing import CliRunner

class TestCLISafety(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
    
    @patch('joshu.ui.cli.translate_to_command')
    @patch('joshu.ui.cli.assess_command_safety')
    def test_dangerous_command_blocked(self, mock_assess_safety, mock_translate):
        """Test that dangerous commands are blocked."""
        # Mock the translation to return a dangerous command
        mock_translation = MagicMock()
        mock_translation.command = "rm -rf /"
        mock_translation.explanation = "Delete everything"
        mock_translate.return_value = mock_translation
        
        # Mock safety assessment to return unsafe
        mock_safety_report = MagicMock()
        mock_safety_report.safe = False
        mock_safety_report.reasons = ["DANGER: This command will delete your entire system"]
        mock_safety_report.suggested_alternative = "rm -i *.tmp"
        mock_safety_report.danger_level = "CRITICAL"
        mock_assess_safety.return_value = mock_safety_report
        
        # Run the command
        result = self.runner.invoke(app, ["run", "delete everything"])
        
        # Check that the command was blocked
        self.assertEqual(result.exit_code, 3)
        self.assertIn("DANGER: This command could cause serious damage", result.stdout)
        self.assertIn("This command will delete your entire system", result.stdout)
    
    @patch('joshu.ui.cli.translate_to_command')
    @patch('joshu.ui.cli.assess_command_safety')
    def test_sandbox_mode_blocks_destructive_commands(self, mock_assess_safety, mock_translate):
        """Test that sandbox mode blocks destructive commands."""
        # Mock the translation to return a destructive command
        mock_translation = MagicMock()
        mock_translation.command = "rm file.txt"
        mock_translation.explanation = "Delete a file"
        mock_translate.return_value = mock_translation
        
        # Mock safety assessment in sandbox mode
        mock_safety_report = MagicMock()
        mock_safety_report.safe = False
        mock_safety_report.reasons = ["Sandbox mode: All destructive commands are blocked."]
        mock_safety_report.suggested_alternative = "rm -i *.tmp"
        mock_safety_report.danger_level = "CRITICAL"
        mock_assess_safety.return_value = mock_safety_report
        
        # Run the command with sandbox mode
        result = self.runner.invoke(app, ["run", "--sandbox", "delete a file"])
        
        # Check that the command was blocked in sandbox mode
        self.assertEqual(result.exit_code, 3)
        self.assertIn("Sandbox mode: All destructive commands are blocked", result.stdout)

if __name__ == '__main__':
    unittest.main()