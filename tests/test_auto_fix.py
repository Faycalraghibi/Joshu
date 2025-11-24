"""
Comprehensive tests for auto-fix functionality.
Tests error analysis, fix generation, safety integration, and retry limits.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from joshu.core.auto_fix import (
    analyze_error_and_generate_fix,
    should_attempt_auto_fix,
    _parse_fix_response,
    FixedCommand
)
from joshu.tools.shell import run_command_with_auto_fix
from joshu.core.storage import JsonFileStorage
from joshu.core.context_provider import ContextProvider


class TestAutoFixBasics:
    """Test basic auto-fix functionality."""
    
    def test_should_attempt_auto_fix_enabled(self):
        """Test that auto-fix is attempted when enabled."""
        config = {"auto_fix_enabled": True, "auto_fix_max_attempts": 2}
        assert should_attempt_auto_fix(config, 0) == True
        assert should_attempt_auto_fix(config, 1) == True
        assert should_attempt_auto_fix(config, 2) == False  # Exceeded max
    
    def test_should_attempt_auto_fix_disabled(self):
        """Test that auto-fix is not attempted when disabled."""
        config = {"auto_fix_enabled": False, "auto_fix_max_attempts": 2}
        assert should_attempt_auto_fix(config, 0) == False
    
    def test_should_attempt_auto_fix_max_attempts(self):
        """Test that max attempts limit is respected."""
        config = {"auto_fix_enabled": True, "auto_fix_max_attempts": 1}
        assert should_attempt_auto_fix(config, 0) == True
        assert should_attempt_auto_fix(config, 1) == False


class TestFixResponseParsing:
    """Test parsing of LLM fix responses."""
    
    def test_parse_valid_json_response(self):
        """Test parsing a valid JSON response."""
        response = '{"command": "ls -la", "explanation": "Fixed typo: sl -> ls"}'
        result = _parse_fix_response(response, "sl -la")
        
        assert result is not None
        assert result.command == "ls -la"
        assert result.explanation == "Fixed typo: sl -> ls"
        assert 0.0 <= result.confidence <= 1.0
    
    def test_parse_json_with_markdown(self):
        """Test parsing JSON wrapped in markdown code blocks."""
        response = '```json\n{"command": "ls -la", "explanation": "Fixed typo"}\n```'
        result = _parse_fix_response(response, "sl -la")
        
        assert result is not None
        assert result.command == "ls -la"
    
    def test_parse_rejects_same_command(self):
        """Test that parsing rejects if fix is same as original."""
        response = '{"command": "sl -la", "explanation": "No change needed"}'
        result = _parse_fix_response(response, "sl -la")
        
        assert result is None
    
    def test_parse_invalid_json(self):
        """Test handling of invalid JSON."""
        response = 'This is not JSON at all'
        result = _parse_fix_response(response, "some command")
        
        assert result is None
    
    def test_confidence_scoring(self):
        """Test that confidence is scored based on explanation quality."""
        # Short explanation = lower confidence
        response1 = '{"command": "ls", "explanation": "Fix"}'
        result1 = _parse_fix_response(response1, "sl")
        
        # Detailed explanation = higher confidence
        response2 = '{"command": "ls", "explanation": "Fixed the typo by changing sl to ls"}'
        result2 = _parse_fix_response(response2, "sl")
        
        assert result1 is not None and result2 is not None
        assert result2.confidence >= result1.confidence


class TestAutoFixIntegration:
    """Test auto-fix integration with command execution."""
    
    @patch('joshu.tools.shell.run_command')
    @patch('joshu.core.auto_fix.analyze_error_and_generate_fix')
    def test_successful_command_no_autofix(self, mock_analyze, mock_run):
        """Test that successful commands don't trigger auto-fix."""
        mock_run.return_value = (0, "output", "")
        
        config = {"auto_fix_enabled": True, "auto_fix_max_attempts": 2}
        code, out, err, fixed = run_command_with_auto_fix("ls", config)
        
        assert code == 0
        assert fixed is None
        mock_analyze.assert_not_called()
    
    @patch('joshu.tools.shell.run_command')
    @patch('joshu.core.auto_fix.analyze_error_and_generate_fix')
    @patch('joshu.core.safety.assess_command_safety')
    def test_failed_command_triggers_autofix(self, mock_safety, mock_analyze, mock_run):
        """Test that failed commands trigger auto-fix."""
        # First call fails, second succeeds
        mock_run.side_effect = [
            (1, "", "command not found: sl"),
            (0, "files listed", "")
        ]
        
        mock_analyze.return_value = FixedCommand(
            command="ls",
            explanation="Fixed typo: sl -> ls",
            confidence=0.9
        )
        
        mock_safety.return_value = Mock(safe=True)
        
        config = {"auto_fix_enabled": True, "auto_fix_max_attempts": 2, "sandbox_enabled": False}
        code, out, err, fixed = run_command_with_auto_fix("sl", config, attempt=0)
        
        assert code == 0
        assert fixed == "ls"
        mock_analyze.assert_called_once()
    
    @patch('joshu.tools.shell.run_command')
    @patch('joshu.core.auto_fix.analyze_error_and_generate_fix')
    def test_autofix_disabled_not_attempted(self, mock_analyze, mock_run):
        """Test that auto-fix is not attempted when disabled."""
        mock_run.return_value = (1, "", "error")
        
        config = {"auto_fix_enabled": False, "auto_fix_max_attempts": 2}
        code, out, err, fixed = run_command_with_auto_fix("bad_cmd", config)
        
        assert code == 1
        assert fixed is None
        mock_analyze.assert_not_called()
    
    @patch('joshu.tools.shell.run_command')
    @patch('joshu.core.auto_fix.analyze_error_and_generate_fix')
    @patch('joshu.core.safety.assess_command_safety')
    def test_unsafe_fix_rejected(self, mock_safety, mock_analyze, mock_run):
        """Test that unsafe auto-fixes are rejected."""
        mock_run.return_value = (1, "", "error")
        
        mock_analyze.return_value = FixedCommand(
            command="rm -rf /",
            explanation="Dangerous fix",
            confidence=0.9
        )
        
        mock_safety.return_value = Mock(safe=False, reasons=["Dangerous command"])
        
        config = {"auto_fix_enabled": True, "auto_fix_max_attempts": 2, "sandbox_enabled": False}
        code, out, err, fixed = run_command_with_auto_fix("some_cmd", config)
        
        assert code == 1
        assert fixed is None
    
    @patch('joshu.tools.shell.run_command')
    @patch('joshu.core.auto_fix.analyze_error_and_generate_fix')
    def test_max_attempts_limit(self, mock_analyze, mock_run):
        """Test that max attempts limit prevents infinite loops."""
        # All commands fail
        mock_run.return_value = (1, "", "error")
        
        mock_analyze.return_value = FixedCommand(
            command="still_bad",
            explanation="Another attempt",
            confidence=0.5
        )
        
        config = {"auto_fix_enabled": True, "auto_fix_max_attempts": 2, "sandbox_enabled": False}
        
        with patch('joshu.core.safety.assess_command_safety', return_value=Mock(safe=True)):
            code, out, err, fixed = run_command_with_auto_fix("bad_cmd", config, attempt=0)
        
        # Should have stopped after max attempts
        assert mock_analyze.call_count <= 2
    
    @patch('joshu.tools.shell.run_command')
    @patch('joshu.core.auto_fix.analyze_error_and_generate_fix')
    def test_no_fix_generated(self, mock_analyze, mock_run):
        """Test handling when LLM cannot generate a fix."""
        mock_run.return_value = (1, "", "error")
        mock_analyze.return_value = None  # No fix generated
        
        config = {"auto_fix_enabled": True, "auto_fix_max_attempts": 2}
        code, out, err, fixed = run_command_with_auto_fix("bad_cmd", config)
        
        assert code == 1
        assert fixed is None


class TestAutoFixWithContext:
    """Test auto-fix with context provider integration."""
    
    @patch('joshu.core.auto_fix.chat_completion')  # Patch where it's imported, not where it's defined
    def test_analyze_error_with_context(self, mock_chat):
        """Test that error analysis uses context when available."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = JsonFileStorage(Path(tmpdir) / 'test.json')
            context_provider = ContextProvider(storage_backend=storage)
            
            # Add some conversation history
            context_provider.add_to_history("user", "I want to list files")
            context_provider.add_to_history("assistant", "Use ls command")
            
            mock_chat.return_value = '{"command": "ls -la", "explanation": "Fixed typo"}'
            
            result = analyze_error_and_generate_fix(
                "sl -la",
                "command not found: sl",
                127,
                context_provider
            )
            
            # Verify chat_completion was called with context
            assert mock_chat.called
            call_args = mock_chat.call_args
            messages = call_args[1]['messages']
            assert len(messages) > 0  # Should include context



@pytest.mark.integration
class TestAutoFixEndToEnd:
    """End-to-end integration tests for auto-fix."""
    
    def test_real_typo_fix(self):
        """Test a real typo fix scenario (requires actual LLM)."""
        # This would be a real integration test
        # Skip in CI/CD, run manually for verification
        pytest.skip("Requires real LLM connection")
    
    def test_real_safety_check(self):
        """Test that safety checks work in real scenario."""
        pytest.skip("Requires real LLM connection")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
