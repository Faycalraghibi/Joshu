from __future__ import annotations

import subprocess
import logging
from typing import Tuple, Dict, Any, Optional

logger = logging.getLogger(__name__)


def run_command(command: str, timeout: int = 60) -> Tuple[int, str, str]:
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=timeout,
            encoding='utf-8', errors='replace'  # Handle encoding issues
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return -1, "", str(e)


def run_command_with_auto_fix(
    command: str,
    config: Dict[str, Any],
    context_provider: Optional[Any] = None,
    attempt: int = 0,
    timeout: int = 60,
    model: str = "meta-llama/llama-3.1-8b-instruct:free"
) -> Tuple[int, str, str, Optional[str]]:
    """
    Run command with auto-fix retry on failure.
    
    Args:
        command: Command to execute
        config: Configuration dict with auto-fix settings
        context_provider: Optional context provider for conversation history
        attempt: Current attempt number (for recursion tracking)
        timeout: Command timeout in seconds
        model: LLM model to use for fix generation
        
    Returns:
        Tuple of (returncode, stdout, stderr, fixed_command)
        fixed_command is populated if a fix was applied, None otherwise
    """
    # Run the command
    returncode, stdout, stderr = run_command(command, timeout)
    
    # If success, return immediately
    if returncode == 0:
        return returncode, stdout, stderr, None
    
    # Check if auto-fix should be attempted
    from joshu.core.auto_fix import should_attempt_auto_fix, analyze_error_and_generate_fix
    
    if not should_attempt_auto_fix(config, attempt):
        logger.debug(f"Not attempting auto-fix (attempt={attempt}, enabled={config.get('auto_fix_enabled')})")
        return returncode, stdout, stderr, None
    
    # Log the failure and attempt to fix
    logger.info(f"Command failed with exit code {returncode}. Attempting auto-fix (attempt {attempt + 1}/{config.get('auto_fix_max_attempts', 2)})")
    
    # Generate fix using LLM
    fixed_command_obj = analyze_error_and_generate_fix(
        command, stderr, returncode, context_provider, model
    )
    
    if not fixed_command_obj:
        logger.debug("Could not generate auto-fix")
        return returncode, stdout, stderr, None
    
    # Safety check the fixed command
    from joshu.core.safety import assess_command_safety
    
    sandbox = config.get("sandbox_enabled", True)
    safety_report = assess_command_safety(fixed_command_obj.command, sandbox)
    
    if not safety_report.safe:
        logger.warning(f"Auto-fix generated unsafe command: {fixed_command_obj.command}")
        logger.warning(f"Safety reasons: {', '.join(safety_report.reasons)}")
        return returncode, stdout, stderr, None
    
    logger.info(f"Auto-fix suggestion: {fixed_command_obj.command}")
    logger.info(f"Explanation: {fixed_command_obj.explanation}")
    
    # Recursively retry with fixed command
    new_returncode, new_stdout, new_stderr, _ = run_command_with_auto_fix(
        fixed_command_obj.command,
        config,
        context_provider,
        attempt + 1,
        timeout,
        model
    )
    
    # Return the result with the fixed command info
    return new_returncode, new_stdout, new_stderr, fixed_command_obj.command