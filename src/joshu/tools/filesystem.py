from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class FileInfo:
    """Represents file information for directory analysis."""

    name: str
    path: str
    size: int
    is_directory: bool
    extension: str = ""
    permissions: str = ""


def list_python_files(root: str) -> List[str]:
    """List all Python files in the given directory and subdirectories."""
    return [str(p) for p in Path(root).rglob("*.py")]


def get_directory_structure(root: str, max_depth: int = 3) -> Dict[str, Union[str, Dict]]:
    """
    Get directory structure as a nested dictionary.

    Args:
        root: Root directory path
        max_depth: Maximum depth to traverse (default: 3)

    Returns:
        Dictionary representing directory structure
    """

    def _build_tree(path: Path, depth: int = 0) -> Dict[str, Union[str, Dict]]:
        if depth > max_depth:
            return {}

        result = {}
        try:
            if path.is_dir():
                for item in path.iterdir():
                    if item.is_dir():
                        result[item.name] = _build_tree(item, depth + 1)
                    else:
                        result[item.name] = "file"
            else:
                result[path.name] = "file"
        except PermissionError:
            result["(permission denied)"] = "error"
        except Exception as e:
            logger.warning(f"Error reading {path}: {e}")
            result[f"(error: {str(e)[:20]}...)"] = "error"

        return result

    root_path = Path(root)
    return {root_path.name: _build_tree(root_path)}


def find_files_by_extension(root: str, extension: str) -> List[str]:
    """
    Find all files with a specific extension.

    Args:
        root: Root directory path
        extension: File extension to search for (e.g., '.conf', '.log')

    Returns:
        List of file paths matching the extension
    """
    if not extension.startswith("."):
        extension = "." + extension

    return [str(p) for p in Path(root).rglob(f"*{extension}")]


def get_file_info(file_path: str) -> Optional[FileInfo]:
    """
    Get detailed information about a file.

    Args:
        file_path: Path to the file

    Returns:
        FileInfo object or None if file doesn't exist
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return None

        stat = path.stat()

        # Get file permissions (Unix-style)
        try:
            permissions = oct(stat.st_mode)[-3:]
        except Exception:
            permissions = "N/A"

        return FileInfo(
            name=path.name,
            path=str(path),
            size=stat.st_size,
            is_directory=path.is_dir(),
            extension=path.suffix if not path.is_dir() else "",
            permissions=permissions,
        )
    except Exception as e:
        logger.warning(f"Error getting file info for {file_path}: {e}")
        return None


def list_directory_contents(directory: str, show_hidden: bool = False) -> List[FileInfo]:
    """
    List contents of a directory with detailed information.

    Args:
        directory: Directory path to list
        show_hidden: Whether to show hidden files (default: False)

    Returns:
        List of FileInfo objects
    """
    try:
        path = Path(directory)
        if not path.is_dir():
            raise ValueError(f"{directory} is not a directory")

        files = []
        for item in path.iterdir():
            # Skip hidden files unless explicitly requested
            if not show_hidden and item.name.startswith("."):
                continue

            file_info = get_file_info(str(item))
            if file_info:
                files.append(file_info)

        # Sort: directories first, then by name
        files.sort(key=lambda x: (not x.is_directory, x.name.lower()))
        return files
    except Exception as e:
        logger.error(f"Error listing directory contents: {e}")
        return []


def find_large_files(root: str, min_size_mb: int = 10) -> List[FileInfo]:
    """
    Find files larger than the specified size.

    Args:
        root: Root directory to search
        min_size_mb: Minimum file size in MB (default: 10)

    Returns:
        List of large files sorted by size (descending)
    """
    min_size_bytes = min_size_mb * 1024 * 1024
    large_files = []

    try:
        for file_path in Path(root).rglob("*"):
            if file_path.is_file():
                try:
                    size = file_path.stat().st_size
                    if size >= min_size_bytes:
                        file_info = get_file_info(str(file_path))
                        if file_info:
                            large_files.append(file_info)
                except (PermissionError, OSError):
                    # Skip files we can't access
                    continue

        # Sort by size descending
        large_files.sort(key=lambda x: x.size, reverse=True)
        return large_files
    except Exception as e:
        logger.error(f"Error finding large files: {e}")
        return []


def format_directory_listing(files: List[FileInfo], detailed: bool = False) -> str:
    """
    Format a list of files for display.

    Args:
        files: List of FileInfo objects
        detailed: Whether to show detailed information

    Returns:
        Formatted string representation
    """
    if not files:
        return "No files found."

    if detailed:
        lines = []
        for file_info in files:
            if file_info.is_directory:
                lines.append(f"d {file_info.permissions:>4} {file_info.name}/")
            else:
                size_str = _format_file_size(file_info.size)
                lines.append(f"f {file_info.permissions:>4} {size_str:>8} {file_info.name}")
        return "\n".join(lines)
    else:
        # Simple listing
        items = []
        for file_info in files:
            if file_info.is_directory:
                items.append(f"{file_info.name}/")
            else:
                items.append(file_info.name)
        return "\n".join(items)


def _format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format."""
    if size_bytes == 0:
        return "0B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)

    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1

    return f"{size:.1f}{size_names[i]}"


def create_backup(source_dir: str, backup_dir: str) -> bool:
    """
    Create a backup of a directory.

    Args:
        source_dir: Directory to backup
        backup_dir: Backup destination

    Returns:
        True if successful, False otherwise
    """
    try:
        source_path = Path(source_dir)
        backup_path = Path(backup_dir)

        if not source_path.exists():
            logger.error(f"Source directory {source_dir} does not exist")
            return False

        if not source_path.is_dir():
            logger.error(f"Source {source_dir} is not a directory")
            return False

        # Create backup directory if it doesn't exist
        backup_path.mkdir(parents=True, exist_ok=True)

        # Copy directory structure and files
        import shutil

        shutil.copytree(source_dir, str(backup_path / source_path.name), dirs_exist_ok=True)

        return True
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        return False
