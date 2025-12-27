"""
Memory Tool for Joshu CLI.

Provides persistent memory for the AI agent via JOSHU.md file.
Facts stored here are loaded as context in subsequent sessions.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from joshu.core.tool_registry import register_tool

logger = logging.getLogger(__name__)

# Memory file location
DEFAULT_MEMORY_DIR = Path.home() / ".joshu"
DEFAULT_MEMORY_FILE = "JOSHU.md"
MEMORY_SECTION_HEADER = "## Agent Memory"

# Project-level system prompt file
PROJECT_SYSTEM_PROMPT_FILE = "joshu.md"


def find_project_root(start_path: Path | None = None) -> Path | None:
    """
    Find the project root by looking for joshu.md.

    Walks up directory tree from start_path looking for joshu.md.

    Args:
        start_path: Directory to start searching from (defaults to cwd)

    Returns:
        Path to project root containing joshu.md, or None if not found
    """
    if start_path is None:
        start_path = Path.cwd()

    current = start_path.resolve()

    # Walk up directory tree
    while current != current.parent:
        candidate = current / PROJECT_SYSTEM_PROMPT_FILE
        if candidate.is_file():
            return current
        current = current.parent

    # Check root directory
    candidate = current / PROJECT_SYSTEM_PROMPT_FILE
    if candidate.is_file():
        return current

    return None


def load_project_system_prompt(start_path: Path | None = None) -> str:
    """
    Load project-level system prompt from joshu.md.

    Searches for joshu.md starting from start_path and walking up
    the directory tree.

    Args:
        start_path: Directory to start searching from (defaults to cwd)

    Returns:
        Content of joshu.md, or empty string if not found
    """
    project_root = find_project_root(start_path)

    if project_root is None:
        logger.debug("No project joshu.md found")
        return ""

    joshu_path = project_root / PROJECT_SYSTEM_PROMPT_FILE

    try:
        content = joshu_path.read_text(encoding="utf-8")
        logger.info(f"Loaded project system prompt from {joshu_path}")
        return content
    except Exception as e:
        logger.error(f"Error loading project system prompt: {e}")
        return ""


def load_combined_context(start_path: Path | None = None) -> str:
    """
    Load combined context from project joshu.md and user memory.

    Project-level rules take precedence and appear first.
    User memory provides session-specific context.

    Args:
        start_path: Directory to start searching for project root

    Returns:
        Combined context string for AI agent
    """
    parts = []

    # 1. Project-level system prompt (highest priority)
    project_prompt = load_project_system_prompt(start_path)
    if project_prompt:
        parts.append("# Project System Prompt")
        parts.append(project_prompt)

    # 2. User-level memory
    user_memory = load_memory()
    if user_memory:
        parts.append("\n# User Memory")
        parts.append(user_memory)

    return "\n".join(parts) if parts else ""


def get_memory_path() -> Path:
    """
    Get the path to the memory file.

    Returns:
        Path to ~/.joshu/JOSHU.md
    """
    return DEFAULT_MEMORY_DIR / DEFAULT_MEMORY_FILE


def ensure_memory_dir() -> Path:
    """
    Ensure the memory directory exists.

    Returns:
        Path to the memory directory
    """
    DEFAULT_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    return DEFAULT_MEMORY_DIR


def load_memory() -> str:
    """
    Load memory content from JOSHU.md for session context.

    Returns:
        String containing the memory file contents, or empty string if not found
    """
    memory_path = get_memory_path()

    if not memory_path.exists():
        logger.debug(f"Memory file not found at {memory_path}")
        return ""

    try:
        content = memory_path.read_text(encoding="utf-8")
        logger.info(f"Loaded memory from {memory_path}")
        return content
    except Exception as e:
        logger.error(f"Error loading memory: {e}")
        return ""


def _parse_memory_facts(content: str) -> List[str]:
    """
    Parse existing facts from memory content.

    Args:
        content: Memory file content

    Returns:
        List of existing facts
    """
    facts = []
    in_memory_section = False

    for line in content.split("\n"):
        stripped = line.strip()

        if stripped == MEMORY_SECTION_HEADER:
            in_memory_section = True
            continue

        if in_memory_section:
            # Stop at next section
            if stripped.startswith("## "):
                break

            # Extract fact from bullet point
            if stripped.startswith("- "):
                fact = stripped[2:].strip()
                if fact:
                    facts.append(fact)

    return facts


def _format_memory_content(facts: List[str]) -> str:
    """
    Format facts into memory file content.

    Args:
        facts: List of facts to format

    Returns:
        Formatted markdown content
    """
    lines = [
        "# Joshu Memory",
        "",
        "This file contains persistent memory for the Joshu AI assistant.",
        "You can edit this file directly to add or remove remembered information.",
        "",
        MEMORY_SECTION_HEADER,
        "",
    ]

    for fact in facts:
        lines.append(f"- {fact}")

    lines.append("")
    lines.append(f"_Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_")
    lines.append("")

    return "\n".join(lines)


def save_memory_to_file(facts: List[str], append: bool = True) -> Dict[str, Any]:
    """
    Save facts to the memory file.

    Args:
        facts: List of facts to save
        append: If True, append to existing facts; if False, replace

    Returns:
        Dictionary with success status and message
    """
    try:
        ensure_memory_dir()
        memory_path = get_memory_path()

        # Load existing facts if appending
        existing_facts = []
        if append and memory_path.exists():
            content = memory_path.read_text(encoding="utf-8")
            existing_facts = _parse_memory_facts(content)

        # Combine facts (avoid duplicates)
        all_facts = existing_facts.copy()
        new_count = 0
        for fact in facts:
            if fact not in all_facts:
                all_facts.append(fact)
                new_count += 1

        # Write to file
        content = _format_memory_content(all_facts)
        memory_path.write_text(content, encoding="utf-8")

        logger.info(f"Saved {new_count} new facts to memory (total: {len(all_facts)})")

        return {
            "success": True,
            "message": f"Saved {new_count} new facts to memory",
            "total_facts": len(all_facts),
            "new_facts": new_count,
            "path": str(memory_path),
        }

    except Exception as e:
        error_msg = f"Failed to save memory: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
        }


def clear_memory() -> Dict[str, Any]:
    """
    Clear all stored memory.

    Returns:
        Dictionary with success status
    """
    try:
        memory_path = get_memory_path()

        if memory_path.exists():
            memory_path.unlink()
            logger.info("Memory cleared")
            return {"success": True, "message": "Memory cleared"}

        return {"success": True, "message": "No memory to clear"}

    except Exception as e:
        error_msg = f"Failed to clear memory: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}


def get_memory_facts() -> List[str]:
    """
    Get all stored facts from memory.

    Returns:
        List of stored facts
    """
    content = load_memory()
    if not content:
        return []
    return _parse_memory_facts(content)


# Register the tool
@register_tool(
    name="save_memory",
    description="""Save important facts for recall in future sessions.

Use this tool to remember:
- User preferences and settings
- Project-specific context
- Key decisions and rationale
- Important names, dates, or identifiers
- Any information the user wants to persist

Facts are stored in ~/.joshu/JOSHU.md and loaded automatically in future sessions.
The user can also edit this file directly.""",
    parameters={
        "type": "object",
        "properties": {
            "facts": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of facts to remember. Each fact should be a clear, concise statement.",
            }
        },
        "required": ["facts"],
    },
    enabled=True,
    requires_approval=False,
)
def save_memory_tool(facts: List[str]) -> Dict[str, Any]:
    """
    Save facts to persistent memory.

    Args:
        facts: List of facts to save

    Returns:
        Dictionary with save status and details
    """
    if not facts:
        return {
            "success": False,
            "error": "No facts provided to save",
        }

    # Filter out empty facts
    valid_facts = [f.strip() for f in facts if f and f.strip()]

    if not valid_facts:
        return {
            "success": False,
            "error": "No valid facts provided (all were empty)",
        }

    return save_memory_to_file(valid_facts, append=True)
