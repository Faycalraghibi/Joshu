import unittest
from unittest.mock import patch

from joshu.core.safety import assess_command_safety


class TestSafety(unittest.TestCase):
    @patch("joshu.core.safety.get_system_info")
    def test_safe_commands_unix(self, mock_get_system_info):
        """Test that safe commands are correctly identified on Unix systems."""
        mock_get_system_info.return_value = "Linux"

        report = assess_command_safety("ls -la")
        self.assertTrue(report.safe)
        self.assertEqual(len(report.reasons), 0)
        self.assertIsNone(report.suggested_alternative)

        report = assess_command_safety("pwd")
        self.assertTrue(report.safe)
        self.assertEqual(len(report.reasons), 0)

    @patch("joshu.core.safety.get_system_info")
    def test_safe_commands_windows(self, mock_get_system_info):
        """Test that safe commands are correctly identified on Windows systems."""
        mock_get_system_info.return_value = "Windows"

        report = assess_command_safety("dir")
        self.assertTrue(report.safe)
        self.assertEqual(len(report.reasons), 0)

        report = assess_command_safety("cd")
        self.assertTrue(report.safe)
        self.assertEqual(len(report.reasons), 0)

    @patch("joshu.core.safety.get_system_info")
    def test_destructive_commands_unix(self, mock_get_system_info):
        """Test that destructive commands are flagged on Unix systems."""
        mock_get_system_info.return_value = "Linux"

        report = assess_command_safety("rm file.txt")
        self.assertFalse(report.safe)
        self.assertGreater(len(report.reasons), 0)
        self.assertTrue(any("destructive operation" in reason for reason in report.reasons))

    @patch("joshu.core.safety.get_system_info")
    def test_destructive_commands_windows(self, mock_get_system_info):
        """Test that destructive commands are flagged on Windows systems."""
        mock_get_system_info.return_value = "Windows"

        report = assess_command_safety("del file.txt")
        self.assertFalse(report.safe)
        self.assertGreater(len(report.reasons), 0)
        self.assertTrue(any("destructive operation" in reason for reason in report.reasons))

    @patch("joshu.core.safety.get_system_info")
    def test_dangerous_patterns_unix(self, mock_get_system_info):
        """Test that dangerous patterns are detected on Unix systems."""
        mock_get_system_info.return_value = "Linux"

        # Test root deletion pattern
        report = assess_command_safety("rm -rf /")
        self.assertFalse(report.safe)
        self.assertEqual(report.danger_level, "CRITICAL")
        self.assertTrue(
            any(
                "DANGER: This command will delete your entire system" in reason
                for reason in report.reasons
            )
        )

        # Test home directory deletion pattern
        report = assess_command_safety("rm -r /home")
        self.assertFalse(report.safe)
        self.assertEqual(report.danger_level, "HIGH")
        self.assertTrue(
            any(
                "DANGER: This command could delete important user files" in reason
                for reason in report.reasons
            )
        )

    @patch("joshu.core.safety.get_system_info")
    def test_dangerous_patterns_windows(self, mock_get_system_info):
        """Test that dangerous patterns are detected on Windows systems."""
        mock_get_system_info.return_value = "Windows"

        # Test drive deletion pattern (using forward slashes to avoid shlex issues)
        report = assess_command_safety("del /s /q C:/")
        self.assertFalse(report.safe)
        self.assertEqual(report.danger_level, "CRITICAL")
        self.assertTrue(
            any(
                "DANGER: This command will delete all files on a drive" in reason
                for reason in report.reasons
            )
        )

        # Test format command
        report = assess_command_safety("format C:")
        self.assertFalse(report.safe)
        self.assertEqual(report.danger_level, "CRITICAL")
        self.assertTrue(
            any(
                "DANGER: This command will format a drive, destroying all data" in reason
                for reason in report.reasons
            )
        )

    @patch("joshu.core.safety.get_system_info")
    def test_sudo_commands_unix(self, mock_get_system_info):
        """Test that sudo commands are flagged on Unix systems."""
        mock_get_system_info.return_value = "Linux"

        report = assess_command_safety("sudo rm file.txt")
        self.assertFalse(report.safe)
        self.assertTrue(any("elevates privileges with sudo" in reason for reason in report.reasons))
        self.assertEqual(report.danger_level, "MEDIUM")

    @patch("joshu.core.safety.get_system_info")
    def test_sudo_commands_windows(self, mock_get_system_info):
        """Test that sudo commands are not flagged on Windows systems."""
        mock_get_system_info.return_value = "Windows"

        report = assess_command_safety("sudo del file.txt")
        # On Windows, sudo is not a recognized dangerous command
        # But 'del' alone should still be flagged
        self.assertFalse(report.safe)
        self.assertTrue(any("destructive operation" in reason for reason in report.reasons))
        # Should not have sudo warning on Windows
        self.assertFalse(
            any("elevates privileges with sudo" in reason for reason in report.reasons)
        )

    @patch("joshu.core.safety.get_system_info")
    def test_sandbox_mode_unix(self, mock_get_system_info):
        """Test that sandbox mode blocks all destructive commands on Unix systems."""
        mock_get_system_info.return_value = "Linux"

        report = assess_command_safety("ls -la", sandbox_mode=True)
        self.assertTrue(report.safe)  # Non-destructive command should be safe even in sandbox

        report = assess_command_safety("rm file.txt", sandbox_mode=True)
        self.assertFalse(report.safe)
        self.assertTrue(
            any(
                "Sandbox mode: All destructive commands are blocked" in reason
                for reason in report.reasons
            )
        )
        self.assertEqual(report.danger_level, "CRITICAL")

    @patch("joshu.core.safety.get_system_info")
    def test_sandbox_mode_windows(self, mock_get_system_info):
        """Test that sandbox mode blocks all destructive commands on Windows systems."""
        mock_get_system_info.return_value = "Windows"

        report = assess_command_safety("dir", sandbox_mode=True)
        self.assertTrue(report.safe)  # Non-destructive command should be safe even in sandbox

        report = assess_command_safety("del file.txt", sandbox_mode=True)
        self.assertFalse(report.safe)
        self.assertTrue(
            any(
                "Sandbox mode: All destructive commands are blocked" in reason
                for reason in report.reasons
            )
        )
        self.assertEqual(report.danger_level, "CRITICAL")

    @patch("joshu.core.safety.get_system_info")
    def test_absolute_paths_in_rm_unix(self, mock_get_system_info):
        """Test detection of absolute paths in rm commands on Unix systems."""
        mock_get_system_info.return_value = "Linux"

        report = assess_command_safety("rm -rf /etc/passwd")
        self.assertFalse(report.safe)
        self.assertEqual(report.danger_level, "HIGH")
        self.assertTrue(
            any(
                "DANGER: rm command targeting system directories" in reason
                for reason in report.reasons
            )
        )

    @patch("joshu.core.safety.get_system_info")
    def test_suggested_alternatives_unix(self, mock_get_system_info):
        """Test that suggested alternatives are provided on Unix systems."""
        mock_get_system_info.return_value = "Linux"

        report = assess_command_safety("rm -rf /")
        self.assertIsNotNone(report.suggested_alternative)
        self.assertIsInstance(report.suggested_alternative, str)
        self.assertTrue(
            "Delete files interactively" in report.suggested_alternative
            if report.suggested_alternative
            else (
                False or "rm -i" in report.suggested_alternative
                if report.suggested_alternative
                else False
            )
        )

    @patch("joshu.core.safety.get_system_info")
    def test_suggested_alternatives_windows(self, mock_get_system_info):
        """Test that suggested alternatives are provided on Windows systems."""
        mock_get_system_info.return_value = "Windows"

        report = assess_command_safety("del /s /q C:/")
        self.assertIsNotNone(report.suggested_alternative)
        self.assertIsInstance(report.suggested_alternative, str)
        self.assertTrue(
            "Delete specific files only" in report.suggested_alternative
            if report.suggested_alternative
            else (
                False or "del *.tmp" in report.suggested_alternative
                if report.suggested_alternative
                else False
            )
        )


if __name__ == "__main__":
    unittest.main()
