from __future__ import annotations

import re
import json
import logging
import platform
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict

from opencli.models.openrouter import translate_command_with_openrouter
from opencli.models.inference import get_model

logger = logging.getLogger(__name__)

@dataclass
class Translation:
    command: str
    explanation: str


COMMON_PATTERNS: List[Tuple[re.Pattern[str], str, str]] = [
    (
        re.compile(r"list\s+all\s+python\s+files\s+modified\s+(today|in\s+the\s+last\s+day)\b", re.I),
        'find . -name "*.py" -mtime -1',
        "List Python files modified in the last 24 hours using find and mtime.",
    ),
    (
        re.compile(r"show\s+disk\s+usage(\s+of\s+current\s+directory)?\b", re.I),
        "du -sh .",
        "Summarize disk usage of the current directory in human-readable form.",
    ),
    (
        re.compile(r"find\s+large\s+files\s+over\s+(\d+)\s*mb\b", re.I),
        "find . -type f -size +{size}M -exec ls -lh {} \\;",
        "Find files larger than the given size and list details.",
    ),
    (
        re.compile(r"find\s+all\s+python\s+files\b", re.I),
        'find . -name "*.py"',
        "Find all Python files recursively from the current directory.",
    ),
]


def get_system_info() -> str:
    """Get information about the current system for command generation."""
    system = platform.system()
    if system == "Windows":
        return "Windows"
    elif system == "Darwin":
        return "macOS"
    elif system == "Linux":
        return "Linux"
    else:
        return f"Unix-like ({system})"


def translate_to_command(prompt: str) -> Optional[Translation]:
    text = prompt.strip()
    
    # First try pattern matching
    for pattern, template, explanation in COMMON_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        command = template
        if "{size}" in template and m.groups():
            size = m.group(1)
            command = template.format(size=size)
        
        # Adapt command for Windows if needed
        if platform.system() == "Windows":
            command = adapt_command_for_windows(command)
            
        return Translation(command=command, explanation=explanation)
    
    # If pattern matching fails, try LLM-based translation
    return translate_with_llm(prompt)


def adapt_command_for_windows(command: str) -> str:
    """Adapt Unix commands for Windows."""
    # Common Unix to Windows command mappings
    if command.startswith("ls"):
        return command.replace("ls", "dir")
    elif command.startswith("du -sh"):
        return "dir"  # Simple replacement for disk usage
    elif command.startswith("find . -name"):
        # Convert find command to Windows equivalent
        if "*.py" in command:
            return "dir /s *.py"
    elif command.startswith("pwd"):
        return "cd"
    elif command.startswith("cat"):
        return command.replace("cat", "type")
    elif command.startswith("type "):
        # Already a Windows command
        return command
    
    # Return original command if no adaptation is needed
    return command


def translate_with_llm(prompt: str) -> Optional[Translation]:
    """Translate natural language to command using LLM."""
    try:
        # Try OpenRouter first
        translation = translate_with_openrouter(prompt)
        if translation:
            command = translation["command"]
            # Adapt command for Windows if needed
            if platform.system() == "Windows":
                command = adapt_command_for_windows(command)
            return Translation(command=command, explanation=translation["explanation"])
            
        # Fallback to local model
        translation = translate_with_local_model(prompt)
        if translation:
            command = translation.command
            # Adapt command for Windows if needed
            if platform.system() == "Windows":
                command = adapt_command_for_windows(command)
            return Translation(command=command, explanation=translation.explanation)
            
    except Exception as e:
        logger.warning(f"LLM translation failed: {e}")
    
    return None


def translate_with_openrouter(prompt: str) -> Optional[Dict[str, str]]:
    """Translate using OpenRouter API."""
    return translate_command_with_openrouter(prompt)


def translate_with_local_model(prompt: str) -> Optional[Translation]:
    """Translate using local model."""
    system_info = get_system_info()
    system_prompt = f"""You are a CLI assistant that translates natural language to shell commands.
The user is on a {system_info} system. Generate appropriate commands for this platform.
Respond ONLY with a JSON object containing "command" and "explanation" fields.
Example response:
{{"command": "dir", "explanation": "List all files and directories in the current directory"}}

User request:"""
    
    full_prompt = f"{system_prompt}\n{prompt}"
    
    try:
        model = get_model("default")
        response = model.generate(full_prompt)
        
        if not response:
            return None
            
        logger.info(f"Local model response: {response}")
            
        # Try to parse JSON response
        # Handle case where response might have extra text around JSON
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]  # Remove ```json
        if response.startswith("```"):
            response = response[3:]  # Remove ```
        if response.endswith("```"):
            response = response[:-3]  # Remove ```
        
        logger.info(f"Cleaned response: {response}")
        
        # Handle echo model response
        if response.startswith("Echo:"):
            # This is the echo model, try to generate a reasonable response
            return generate_echo_response(prompt, system_info)
        
        data = json.loads(response)
        command = data.get("command", "").strip()
        explanation = data.get("explanation", "").strip()
        
        if command and explanation:
            return Translation(command=command, explanation=explanation)
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"Local model translation failed: {e}")
        # Try to generate a reasonable response as fallback
        return generate_echo_response(prompt, get_system_info())
    
    return None


def generate_echo_response(prompt: str, system_info: str) -> Optional[Translation]:
    """Generate a reasonable response when the model fails."""
    prompt_lower = prompt.lower()
    
    # Simple pattern matching for echo model fallback
    if "display" in prompt_lower and ("readme" in prompt_lower or "file" in prompt_lower):
        if system_info == "Windows":
            return Translation(command="type readme.md", explanation="Display the content of readme.md file")
        else:
            return Translation(command="cat readme.md", explanation="Display the content of readme.md file")
    elif "show" in prompt_lower and "content" in prompt_lower and "readme" in prompt_lower:
        if system_info == "Windows":
            return Translation(command="type README.md", explanation="Display the content of README.md file")
        else:
            return Translation(command="cat README.md", explanation="Display the content of README.md file")
    elif "list" in prompt_lower and "files" in prompt_lower:
        if system_info == "Windows":
            return Translation(command="dir", explanation="List all files in current directory")
        else:
            return Translation(command="ls -la", explanation="List all files in current directory")
    elif "current" in prompt_lower and "directory" in prompt_lower:
        if system_info == "Windows":
            return Translation(command="cd", explanation="Show current directory")
        else:
            return Translation(command="pwd", explanation="Show current directory")
    
    return None