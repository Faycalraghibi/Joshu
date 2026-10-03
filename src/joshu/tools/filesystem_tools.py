"""
File System Tools for Joshu CLI.

Provides controlled file system interaction within a workspace root.
These tools enable the agent to navigate, read, create, and modify files.
"""

from __future__ import annotations

import fnmatch
import logging
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from difflib import unified_diff
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from joshu.core.tool_registry import register_tool

logger = logging.getLogger(__name__)

# Default workspace root (can be overridden)
_workspace_root: Optional[Path] = None


def set_workspace_root(root: Union[str, Path]) -> None:
    """Set the workspace root for file operations."""
    global _workspace_root
    _workspace_root = Path(root).resolve()
    logger.info(f"Workspace root set to: {_workspace_root}")


def get_workspace_root() -> Path:
    """Get the current workspace root."""
    if _workspace_root is None:
        return Path.cwd()
    return _workspace_root


def resolve_path(path: str) -> Path:
    """
    Resolve a path relative to workspace root.

    Args:
        path: Path string (relative or absolute)

    Returns:
        Resolved absolute path within workspace

    Raises:
        ValueError: If path is outside workspace root
    """
    workspace = get_workspace_root()
    resolved = (workspace / path).resolve()

    # Security: ensure path is within workspace
    try:
        resolved.relative_to(workspace)
    except ValueError:
        raise ValueError(f"Path '{path}' is outside workspace root")

    return resolved


def is_gitignored(path: Path) -> bool:
    """
    Check if a path should be ignored based on .gitignore rules.

    Args:
        path: Path to check

    Returns:
        True if the path should be ignored
    """
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", str(path)],
            capture_output=True,
            cwd=get_workspace_root(),
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def generate_diff(original: str, modified: str, filename: str) -> str:
    """
    Generate a unified diff between original and modified content.

    Args:
        original: Original file content
        modified: Modified file content
        filename: Name of the file for diff header

    Returns:
        Unified diff string
    """
    original_lines = original.splitlines(keepends=True)
    modified_lines = modified.splitlines(keepends=True)

    diff = unified_diff(
        original_lines,
        modified_lines,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
    )

    return "".join(diff)


@dataclass
class FileEntry:
    """Represents a file or directory entry."""

    name: str
    path: str
    is_directory: bool
    size: int = 0
    modified_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "is_directory": self.is_directory,
            "size": self.size,
            "modified_at": self.modified_at,
        }


# =============================================================================
# LIST DIRECTORY TOOL
# =============================================================================


@register_tool(
    name="list_directory",
    description="""List files and subdirectories within a specified path.

Use this tool to:
- Explore directory structure
- Find files in a location
- View directory contents

The tool respects .gitignore rules by default and can filter using glob patterns.""",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory path to list (relative to workspace root)",
            },
            "ignore_patterns": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Glob patterns to ignore (e.g., ['*.pyc', '__pycache__'])",
            },
            "respect_gitignore": {
                "type": "boolean",
                "description": "Whether to respect .gitignore rules (default: true)",
            },
            "show_hidden": {
                "type": "boolean",
                "description": "Whether to show hidden files (default: false)",
            },
        },
        "required": ["path"],
    },
    enabled=True,
    requires_approval=False,
)
def list_directory_tool(
    path: str,
    ignore_patterns: Optional[List[str]] = None,
    respect_gitignore: bool = True,
    show_hidden: bool = False,
) -> Dict[str, Any]:
    """
    List contents of a directory.

    Args:
        path: Directory path relative to workspace
        ignore_patterns: Glob patterns to ignore
        respect_gitignore: Whether to respect .gitignore
        show_hidden: Whether to show hidden files

    Returns:
        Dictionary with directory contents
    """
    try:
        resolved = resolve_path(path)

        if not resolved.exists():
            return {"success": False, "error": f"Directory not found: {path}"}

        if not resolved.is_dir():
            return {"success": False, "error": f"Not a directory: {path}"}

        entries = []
        ignore_patterns = ignore_patterns or []

        for item in sorted(resolved.iterdir()):
            # Skip hidden files unless requested
            if not show_hidden and item.name.startswith("."):
                continue

            # Check ignore patterns
            if any(fnmatch.fnmatch(item.name, pattern) for pattern in ignore_patterns):
                continue

            # Check gitignore
            if respect_gitignore and is_gitignored(item):
                continue

            stat = item.stat()
            entry = FileEntry(
                name=item.name,
                path=str(item.relative_to(get_workspace_root())),
                is_directory=item.is_dir(),
                size=stat.st_size if item.is_file() else 0,
                modified_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
            )
            entries.append(entry.to_dict())

        return {
            "success": True,
            "path": path,
            "entries": entries,
            "total_entries": len(entries),
        }

    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Error listing directory: {e}")
        return {"success": False, "error": f"Failed to list directory: {str(e)}"}


# =============================================================================
# READ FILE TOOL
# =============================================================================


@register_tool(
    name="read_file",
    description="""Read content from a file.

Use this tool to:
- Read source code files
- Read configuration files
- Read documentation
- Read specific line ranges from large files

Supports text files and returns content as string.
For binary files, returns base64-encoded content.""",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path to read (relative to workspace root)",
            },
            "start_line": {
                "type": "integer",
                "description": "Starting line number (1-indexed, optional)",
            },
            "end_line": {
                "type": "integer",
                "description": "Ending line number (1-indexed, inclusive, optional)",
            },
            "encoding": {
                "type": "string",
                "description": "File encoding (default: utf-8)",
            },
        },
        "required": ["path"],
    },
    enabled=True,
    requires_approval=False,
)
def read_file_tool(
    path: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
    encoding: str = "utf-8",
) -> Dict[str, Any]:
    """
    Read content from a file.

    Args:
        path: File path relative to workspace
        start_line: Starting line (1-indexed)
        end_line: Ending line (1-indexed, inclusive)
        encoding: File encoding

    Returns:
        Dictionary with file content
    """
    try:
        resolved = resolve_path(path)

        if not resolved.exists():
            return {"success": False, "error": f"File not found: {path}"}

        if not resolved.is_file():
            return {"success": False, "error": f"Not a file: {path}"}

        # Try to read as text
        try:
            content = resolved.read_text(encoding=encoding)
        except UnicodeDecodeError:
            # Binary file - return base64
            import base64

            binary_content = resolved.read_bytes()
            return {
                "success": True,
                "path": path,
                "content": base64.b64encode(binary_content).decode("ascii"),
                "is_binary": True,
                "size": len(binary_content),
            }

        # Handle line range
        lines = content.splitlines()
        total_lines = len(lines)

        if start_line is not None or end_line is not None:
            start = (start_line or 1) - 1  # Convert to 0-indexed
            end = end_line or total_lines

            if start < 0 or start >= total_lines:
                return {"success": False, "error": f"Invalid start_line: {start_line}"}

            content = "\n".join(lines[start:end])
            return {
                "success": True,
                "path": path,
                "content": content,
                "is_binary": False,
                "start_line": start + 1,
                "end_line": min(end, total_lines),
                "total_lines": total_lines,
            }

        return {
            "success": True,
            "path": path,
            "content": content,
            "is_binary": False,
            "total_lines": total_lines,
        }

    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        return {"success": False, "error": f"Failed to read file: {str(e)}"}


# =============================================================================
# WRITE FILE TOOL
# =============================================================================


@register_tool(
    name="write_file",
    description="""Write content to a file, creating or overwriting it.

Use this tool to:
- Create new files
- Overwrite existing files with new content
- Save generated code or configuration

Creates parent directories if they don't exist.
REQUIRES USER CONFIRMATION - a diff will be shown for existing files.""",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path to write (relative to workspace root)",
            },
            "content": {
                "type": "string",
                "description": "Content to write to the file",
            },
            "encoding": {
                "type": "string",
                "description": "File encoding (default: utf-8)",
            },
        },
        "required": ["path", "content"],
    },
    enabled=True,
    requires_approval=True,  # Requires user confirmation
)
def write_file_tool(
    path: str,
    content: str,
    encoding: str = "utf-8",
) -> Dict[str, Any]:
    """
    Write content to a file.

    Args:
        path: File path relative to workspace
        content: Content to write
        encoding: File encoding

    Returns:
        Dictionary with write status and diff (if applicable)
    """
    try:
        resolved = resolve_path(path)

        # Check if file exists and generate diff
        diff = None
        is_new = not resolved.exists()

        if not is_new:
            try:
                original = resolved.read_text(encoding=encoding)
                diff = generate_diff(original, content, resolved.name)
            except Exception:
                pass

        # Create parent directories
        resolved.parent.mkdir(parents=True, exist_ok=True)

        # Write the file
        resolved.write_text(content, encoding=encoding)

        result = {
            "success": True,
            "path": path,
            "is_new": is_new,
            "bytes_written": len(content.encode(encoding)),
            "message": f"{'Created' if is_new else 'Updated'} file: {path}",
        }

        if diff:
            result["diff"] = diff

        logger.info(f"Wrote file: {resolved}")
        return result

    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Error writing file: {e}")
        return {"success": False, "error": f"Failed to write file: {str(e)}"}


# =============================================================================
# GLOB (FIND FILES) TOOL
# =============================================================================


@register_tool(
    name="glob",
    description="""Find files matching glob patterns.

Use this tool to:
- Find all files of a certain type (e.g., '*.py', '*.js')
- Search for files by name pattern
- Find files in specific directories

Results are sorted by modification time (newest first).""",
    parameters={
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Glob pattern to match (e.g., '**/*.py')",
            },
            "path": {
                "type": "string",
                "description": "Directory to search in (default: workspace root)",
            },
            "case_sensitive": {
                "type": "boolean",
                "description": "Whether to use case-sensitive matching (default: true)",
            },
            "respect_gitignore": {
                "type": "boolean",
                "description": "Whether to respect .gitignore rules (default: true)",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 100)",
            },
        },
        "required": ["pattern"],
    },
    enabled=True,
    requires_approval=False,
)
def glob_tool(
    pattern: str,
    path: str = ".",
    case_sensitive: bool = True,
    respect_gitignore: bool = True,
    max_results: int = 100,
) -> Dict[str, Any]:
    """
    Find files matching a glob pattern.

    Args:
        pattern: Glob pattern to match
        path: Directory to search in
        case_sensitive: Case sensitivity
        respect_gitignore: Whether to respect .gitignore
        max_results: Maximum results to return

    Returns:
        Dictionary with matching files
    """
    try:
        resolved = resolve_path(path)

        if not resolved.exists():
            return {"success": False, "error": f"Directory not found: {path}"}

        matches = []
        for match in resolved.glob(pattern):
            if respect_gitignore and is_gitignored(match):
                continue

            if not match.is_file():
                continue

            stat = match.stat()
            matches.append(
                {
                    "path": str(match.relative_to(get_workspace_root())),
                    "size": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )

        # Sort by modification time (newest first)
        matches.sort(key=lambda x: x["modified_at"], reverse=True)

        # Limit results
        truncated = len(matches) > max_results
        matches = matches[:max_results]

        return {
            "success": True,
            "pattern": pattern,
            "path": path,
            "matches": matches,
            "total_matches": len(matches),
            "truncated": truncated,
        }

    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Error globbing files: {e}")
        return {"success": False, "error": f"Failed to find files: {str(e)}"}


# =============================================================================
# SEARCH FILE CONTENT TOOL
# =============================================================================


@register_tool(
    name="search_file_content",
    description="""Search for a pattern (regex) within file contents.

Use this tool to:
- Find code by content
- Search for function/class definitions
- Find usages of variables or imports
- Search across multiple files

Uses git grep when available for performance.""",
    parameters={
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Regex pattern to search for",
            },
            "path": {
                "type": "string",
                "description": "Directory or file to search in (default: workspace root)",
            },
            "file_pattern": {
                "type": "string",
                "description": "Glob pattern to filter files (e.g., '*.py')",
            },
            "case_sensitive": {
                "type": "boolean",
                "description": "Whether to use case-sensitive search (default: true)",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results (default: 50)",
            },
        },
        "required": ["pattern"],
    },
    enabled=True,
    requires_approval=False,
)
def search_file_content_tool(
    pattern: str,
    path: str = ".",
    file_pattern: Optional[str] = None,
    case_sensitive: bool = True,
    max_results: int = 50,
) -> Dict[str, Any]:
    """
    Search for pattern in file contents.

    Args:
        pattern: Regex pattern to search for
        path: Directory or file to search
        file_pattern: Glob pattern to filter files
        case_sensitive: Case sensitivity
        max_results: Maximum results

    Returns:
        Dictionary with search results
    """
    try:
        resolved = resolve_path(path)

        if not resolved.exists():
            return {"success": False, "error": f"Path not found: {path}"}

        # Try git grep first (faster)
        try:
            cmd = ["git", "grep", "-n", "--no-color"]
            if not case_sensitive:
                cmd.append("-i")
            if file_pattern:
                cmd.extend(["--", file_pattern])
            cmd.append(pattern)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=resolved if resolved.is_dir() else resolved.parent,
            )

            if result.returncode == 0:
                matches = []
                for line in result.stdout.splitlines()[:max_results]:
                    parts = line.split(":", 2)
                    if len(parts) >= 3:
                        matches.append(
                            {
                                "file": parts[0],
                                "line_number": int(parts[1]),
                                "content": parts[2].strip(),
                            }
                        )
                return {
                    "success": True,
                    "pattern": pattern,
                    "matches": matches,
                    "total_matches": len(matches),
                    "method": "git grep",
                }
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

        # Fallback to Python regex search
        flags = 0 if case_sensitive else re.IGNORECASE
        regex = re.compile(pattern, flags)

        matches = []
        files_to_search = []

        if resolved.is_file():
            files_to_search = [resolved]
        else:
            glob_pattern = file_pattern or "**/*"
            files_to_search = list(resolved.glob(glob_pattern))

        for file_path in files_to_search:
            if not file_path.is_file():
                continue

            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                for i, line in enumerate(content.splitlines(), 1):
                    if regex.search(line):
                        matches.append(
                            {
                                "file": str(file_path.relative_to(get_workspace_root())),
                                "line_number": i,
                                "content": line.strip()[:200],  # Truncate long lines
                            }
                        )

                        if len(matches) >= max_results:
                            break
            except Exception:
                continue

            if len(matches) >= max_results:
                break

        return {
            "success": True,
            "pattern": pattern,
            "matches": matches,
            "total_matches": len(matches),
            "method": "regex",
        }

    except ValueError as e:
        return {"success": False, "error": str(e)}
    except re.error as e:
        return {"success": False, "error": f"Invalid regex pattern: {str(e)}"}
    except Exception as e:
        logger.error(f"Error searching files: {e}")
        return {"success": False, "error": f"Failed to search files: {str(e)}"}


# =============================================================================
# REPLACE (EDIT) TOOL
# =============================================================================


def _with_line_endings(text: str, eol: str) -> str:
    return text.replace("\r\n", "\n").replace("\n", eol)


def _closest_match(content: str, old_string: str, max_lines: int = 20000) -> Dict[str, Any]:
    """
    Where the file has text most like `old_string`, so the model can copy the
    real text instead of guessing again.
    """
    from difflib import SequenceMatcher

    lines = content.replace("\r\n", "\n").split("\n")
    wanted = old_string.replace("\r\n", "\n").strip("\n").split("\n")
    if not any(line.strip() for line in wanted) or len(lines) > max_lines:
        return {}

    size = len(wanted)
    wanted_stripped = [line.strip() for line in wanted]
    first = wanted_stripped[0]
    best_ratio, best_start = 0.0, -1
    for start in range(0, max(1, len(lines) - size + 1)):
        window = lines[start : start + size]
        stripped = [line.strip() for line in window]
        if stripped == wanted_stripped:
            snippet = "\n".join(window)
            return {
                "hint": f"Lines {start + 1}-{start + size} match except for indentation or "
                "whitespace. Use the exact text below as old_string.",
                "closest_match": snippet,
            }
        # Cheap filter before the expensive comparison
        if first and size > 1 and SequenceMatcher(None, first, stripped[0]).quick_ratio() < 0.5:
            continue
        ratio = SequenceMatcher(None, "\n".join(wanted_stripped), "\n".join(stripped)).ratio()
        if ratio > best_ratio:
            best_ratio, best_start = ratio, start

    if best_start < 0 or best_ratio < 0.6:
        return {}
    snippet = "\n".join(lines[best_start : best_start + size])
    return {
        "hint": f"The most similar text is at lines {best_start + 1}-{best_start + size} "
        f"({best_ratio:.0%} similar). If that is what you meant, use it as old_string.",
        "closest_match": snippet,
    }


@register_tool(
    name="replace",
    description="""Replace text within a file.

Use this tool to:
- Make targeted code changes
- Update configuration values
- Fix typos or errors
- Refactor code

Requires the old text to match exactly (with context).
REQUIRES USER CONFIRMATION - a diff will be shown before changes are applied.

For best results, include surrounding context in old_string to ensure unique matching.""",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path (relative to workspace root)",
            },
            "old_string": {
                "type": "string",
                "description": "Exact text to replace (include context for uniqueness)",
            },
            "new_string": {
                "type": "string",
                "description": "Replacement text",
            },
            "all_occurrences": {
                "type": "boolean",
                "description": "Replace all occurrences (default: false, replace first only)",
            },
        },
        "required": ["path", "old_string", "new_string"],
    },
    enabled=True,
    requires_approval=True,  # Requires user confirmation
)
def replace_tool(
    path: str,
    old_string: str,
    new_string: str,
    all_occurrences: bool = False,
) -> Dict[str, Any]:
    """
    Replace text within a file.

    Args:
        path: File path relative to workspace
        old_string: Text to replace
        new_string: Replacement text
        all_occurrences: Whether to replace all occurrences

    Returns:
        Dictionary with replacement status and diff
    """
    try:
        resolved = resolve_path(path)

        if not resolved.exists():
            return {"success": False, "error": f"File not found: {path}"}

        if not resolved.is_file():
            return {"success": False, "error": f"Not a file: {path}"}

        # Read as-is: keep the file's line endings (CRLF or LF) unchanged
        content = resolved.read_bytes().decode("utf-8")
        if "\r\n" in content:
            old_string = _with_line_endings(old_string, "\r\n")
            new_string = _with_line_endings(new_string, "\r\n")

        # Check if old_string exists
        if old_string not in content:
            return {
                "success": False,
                "error": "old_string not found in file. It must match the file exactly, "
                "including indentation and whitespace. Read the file again and copy the "
                "text from it.",
                **_closest_match(content, old_string),
            }

        # Count occurrences
        occurrences = content.count(old_string)

        if occurrences > 1 and not all_occurrences:
            return {
                "success": False,
                "error": f"Multiple occurrences found ({occurrences}). Include more context for unique match or set all_occurrences=true.",
                "occurrences": occurrences,
            }

        # Perform replacement
        if all_occurrences:
            new_content = content.replace(old_string, new_string)
        else:
            new_content = content.replace(old_string, new_string, 1)

        # Generate diff
        diff = generate_diff(
            content.replace("\r\n", "\n"), new_content.replace("\r\n", "\n"), resolved.name
        )

        # Write the file (bytes: no newline translation)
        resolved.write_bytes(new_content.encode("utf-8"))

        replaced_count = occurrences if all_occurrences else 1

        logger.info(f"Replaced {replaced_count} occurrence(s) in {resolved}")

        return {
            "success": True,
            "path": path,
            "replacements": replaced_count,
            "diff": diff,
            "message": f"Replaced {replaced_count} occurrence(s)",
        }

    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Error replacing in file: {e}")
        return {"success": False, "error": f"Failed to replace in file: {str(e)}"}
