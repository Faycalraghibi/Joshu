from __future__ import annotations

import shlex
import re
import os
from dataclasses import dataclass
from typing import List, Dict, Optional

from opencli.tools.system_info import get_system_info


# Expanded list of destructive commands and patterns for different OS
UNIX_DESTRUCTIVE_TOKENS = {
    "rm", "rmdir", "erase", ":(){:|:&};:", "mkfs", "dd", "shutdown", 
    "reboot", "halt", "poweroff", "format", "wipe", "shred"
}

WINDOWS_DESTRUCTIVE_TOKENS = {
    "del", "erase", "rmdir", "deltree", "format", "diskpart", "cipher", 
    "takeown", "icacls", "shutdown", "restart", "taskkill"
}

# Common destructive tokens that exist on both platforms
COMMON_DESTRUCTIVE_TOKENS = {
    "mkfs", "dd", "wipe", "shred", "sdelete"
}

# Patterns for dangerous operations (Unix/Linux/macOS)
UNIX_DANGEROUS_PATTERNS: List[Dict[str, str]] = [
    {
        "pattern": r"rm\s+-rf\s+/",
        "reason": "DANGER: This command will delete your entire system",
        "alternative": "rm -i *.tmp  # Delete files interactively"
    },
    {
        "pattern": r"rm\s+-r.*\s+/home",
        "reason": "DANGER: This command could delete important user files",
        "alternative": "rm -i *.tmp  # Delete files interactively in current directory"
    },
    {
        "pattern": r"rm\s+-rf.*\$(HOME|USER)",
        "reason": "DANGER: This command could delete your home directory",
        "alternative": "rm -i *.tmp  # Delete files interactively"
    },
    {
        "pattern": r"rm\s+-(rf|r).*\s+/$",
        "reason": "DANGER: This command will delete your entire system",
        "alternative": "rm -i *.tmp  # Delete files interactively"
    },
    {
        "pattern": r"rm\s+-(rf|r).*\s+/home/.*$",
        "reason": "DANGER: This command could delete important user files",
        "alternative": "rm -i *.tmp  # Delete files interactively in current directory"
    },
    {
        "pattern": r"mkfs\.",
        "reason": "DANGER: This command will format a disk, destroying all data",
        "alternative": "Use disk management tools with proper precautions"
    },
    {
        "pattern": r"dd\s+if=/dev/(zero|random)",
        "reason": "DANGER: This command will overwrite data on disk",
        "alternative": "Use file shredding tools with confirmation"
    },
    {
        "pattern": r":\(\){:|\:&};:",
        "reason": "DANGER: This is a fork bomb that will crash your system",
        "alternative": "Do not run this command - it will crash your system"
    }
]

# Patterns for dangerous operations (Windows)
WINDOWS_DANGEROUS_PATTERNS: List[Dict[str, str]] = [
    {
        "pattern": r"del\s+(/s\s+|/q\s+)*[A-Za-z]:[/\\]",
        "reason": "DANGER: This command will delete all files on a drive",
        "alternative": "del *.tmp  # Delete specific files only"
    },
    {
        "pattern": r"(rd|rmdir)\s+(/s\s+|/q\s+)+[A-Za-z]:[/\\]",
        "reason": "DANGER: This command will delete your entire drive",
        "alternative": "rd /s /q .\\temp  # Delete specific directories only"
    },
    {
        "pattern": r"deltree\s+(/y\s+)*[A-Za-z]:[/\\]",
        "reason": "DANGER: This command will delete an entire drive",
        "alternative": "Use specific file patterns instead of drive-wide operations"
    },
    {
        "pattern": r"format\s+[A-Za-z]:",
        "reason": "DANGER: This command will format a drive, destroying all data",
        "alternative": "Use disk management tools with proper precautions"
    },
    {
        "pattern": r"cipher\s+/w:[A-Za-z]:[/\\]",
        "reason": "DANGER: This command will overwrite free space on a drive",
        "alternative": "Use file shredding tools with confirmation"
    }
]


@dataclass
class SafetyReport:
    safe: bool
    reasons: List[str]
    suggested_alternative: str | None = None
    danger_level: str = "LOW"  # LOW, MEDIUM, HIGH, CRITICAL


def assess_command_safety(command: str, sandbox_mode: bool = False) -> SafetyReport:
    """
    Assess the safety of a command and provide detailed feedback.
    
    Args:
        command: The command to assess
        sandbox_mode: Whether to run in sandbox mode (blocks all destructive commands)
        
    Returns:
        SafetyReport with safety assessment and suggestions
    """
    # Detect the current operating system
    system_info = get_system_info()
    is_windows = "Windows" in system_info
    is_unix = not is_windows  # Covers Linux, macOS, and other Unix-like systems
    
    # Get OS-specific destructive tokens
    if is_windows:
        destructive_tokens = WINDOWS_DESTRUCTIVE_TOKENS | COMMON_DESTRUCTIVE_TOKENS
        dangerous_patterns = WINDOWS_DANGEROUS_PATTERNS
    else:
        destructive_tokens = UNIX_DESTRUCTIVE_TOKENS | COMMON_DESTRUCTIVE_TOKENS
        dangerous_patterns = UNIX_DANGEROUS_PATTERNS
    
    tokens = shlex.split(command) if command.strip() else []
    token_set = set(tokens)
    reasons: List[str] = []
    danger_level = "LOW"
    alternative = None
    
    # Check for sandbox mode - block all destructive commands
    if sandbox_mode:
        if any(t in token_set for t in destructive_tokens):
            reasons.append("Sandbox mode: All destructive commands are blocked.")
            danger_level = "CRITICAL"
            safe = False
        else:
            # For non-destructive commands in sandbox mode, still check other safety rules
            safe = True
    else:
        # Normal mode - start with assumption that command is safe
        safe = True
    
    # Check for destructive tokens
    destructive_tokens_found = token_set & destructive_tokens
    if destructive_tokens_found and not sandbox_mode:
        reasons.append(f"Command includes potentially destructive operation: {', '.join(destructive_tokens_found)}")
        if danger_level == "LOW":
            danger_level = "MEDIUM"
        safe = False
    
    # Check for dangerous patterns
    for pattern_dict in dangerous_patterns:
        if re.search(pattern_dict["pattern"], command, re.IGNORECASE):
            reasons.append(pattern_dict["reason"])
            if alternative is None:
                alternative = pattern_dict["alternative"]
            # Set danger level based on severity
            if "DANGER" in pattern_dict["reason"]:
                if ("entire system" in pattern_dict["reason"] or 
                    "entire drive" in pattern_dict["reason"] or 
                    "destroying all data" in pattern_dict["reason"]):
                    danger_level = "CRITICAL"
                elif danger_level != "CRITICAL":
                    danger_level = "HIGH"
            # In sandbox mode, any dangerous pattern makes command unsafe
            if sandbox_mode:
                safe = False
    
    # Check for sudo usage (Unix/Linux/macOS only)
    if "sudo" in token_set and is_unix:
        reasons.append("Command elevates privileges with sudo.")
        if danger_level == "LOW":
            danger_level = "MEDIUM"
        # In sandbox mode, sudo commands are unsafe
        if sandbox_mode:
            safe = False
    
    # OS-specific checks
    if is_unix:
        # Check for absolute paths in rm commands (Unix/Linux/macOS)
        if "rm" in token_set:
            # Look for paths that start with / but are not in safe directories
            for token in tokens:
                if token.startswith("/") and not token.startswith(("/tmp", "/var/tmp")):
                    # Check if it's targeting system directories
                    if any(sys_dir in token for sys_dir in ["/usr", "/etc", "/var", "/bin", "/sbin", "/lib"]):
                        reasons.append("DANGER: rm command targeting system directories")
                        danger_level = "HIGH"
                        if alternative is None:
                            alternative = "rm -i *.tmp  # Delete files interactively in current directory"
                    elif token == "/":
                        reasons.append("DANGER: rm command targeting root directory")
                        danger_level = "CRITICAL"
                        if alternative is None:
                            alternative = "rm -i *.tmp  # Delete files interactively"
                    else:
                        # General warning for absolute paths
                        if danger_level not in ["CRITICAL", "HIGH"]:
                            danger_level = "MEDIUM"
                            if alternative is None:
                                alternative = "rm -i *.tmp  # Delete files interactively in current directory"
                    # In sandbox mode, rm with absolute paths is unsafe
                    if sandbox_mode:
                        safe = False
        
        # Check for recursive operations on home directory (Unix/Linux/macOS)
        if ("rm" in token_set or "rmdir" in token_set) and any(flag in token_set for flag in ["-r", "-rf", "-R"]):
            home_dir = os.path.expanduser("~")
            for token in tokens:
                if home_dir in token and token != home_dir:
                    reasons.append("DANGER: Recursive operation on home directory subpath")
                    if danger_level not in ["CRITICAL", "HIGH"]:
                        danger_level = "HIGH"
                    if alternative is None:
                        alternative = "Use specific file patterns instead of recursive operations"
                    # In sandbox mode, recursive operations are unsafe
                    if sandbox_mode:
                        safe = False
    elif is_windows:
        # Check for drive-wide operations (Windows)
        drive_operations = token_set & {"del", "rd", "rmdir", "deltree"}
        if drive_operations and any(flag in token_set for flag in ["/s", "/q", "/y"]):
            # Look for drive letters like C:\, D:\, etc.
            for token in tokens:
                if re.match(r"[A-Za-z]:[/\\]", token):
                    reasons.append("DANGER: Command targeting entire drive")
                    danger_level = "CRITICAL"
                    if alternative is None:
                        alternative = "Use specific file patterns instead of drive-wide operations"
                    # In sandbox mode, drive-wide operations are unsafe
                    if sandbox_mode:
                        safe = False
        
        # Check for format operations (Windows)
        if "format" in token_set:
            for token in tokens:
                if re.match(r"[A-Za-z]:", token):
                    reasons.append("DANGER: Format command targeting drive")
                    danger_level = "CRITICAL"
                    if alternative is None:
                        alternative = "Use disk management tools with proper precautions"
                    # In sandbox mode, format operations are unsafe
                    if sandbox_mode:
                        safe = False
    
    # If command is unsafe for other reasons, mark as unsafe
    if len(reasons) > 0 and not sandbox_mode:
        safe = False
        
    if not safe and alternative is None and any(t in token_set for t in ["rm", "del", "rmdir"]):
        if is_windows:
            alternative = "del *.tmp  # Delete specific files only"
        else:
            alternative = "rm -i *.tmp  # Delete files interactively"
    
    return SafetyReport(safe=safe, reasons=reasons, suggested_alternative=alternative, danger_level=danger_level)