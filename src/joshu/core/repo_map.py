"""
A compact map of the project for the system prompt: its files, grouped by
directory, with the top-level definitions in each source file.

Small models spend many turns listing directories and reading files to learn a
project's layout; with the map they can go to the right file at once. It is
built once per session (the system prompt stays the same, so prompt caching
keeps working) and capped at MAX_CHARS, about 1,500 tokens.

`repo_map` setting: auto (default: only when the whole project fits),
always (cut to fit), never.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

MAX_CHARS = 6000
MAX_FILES = 400  # more than this and the map is skipped (auto) or cut (always)
MAX_FILE_BYTES = 300_000  # bigger files are listed without definitions
SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv", "env",
    ".tox", ".nox", ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist", "build",
    ".next", ".idea", ".vscode", "target", "coverage", ".joshu",
}  # fmt: skip
SKIP_SUFFIXES = {
    ".pyc", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".pdf", ".zip", ".gz",
    ".lock", ".woff", ".woff2", ".ttf", ".exe", ".dll", ".so", ".dylib", ".bin",
}  # fmt: skip

# Top-level definitions in languages without a parser here
PATTERNS: Dict[str, List[re.Pattern]] = {
    ".js": [
        re.compile(r"^(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*(\w+)", re.M),
        re.compile(r"^(?:export\s+)?(?:default\s+)?class\s+(\w+)", re.M),
        re.compile(r"^(?:export\s+)?(?:const|let)\s+(\w+)\s*=\s*(?:async\s*)?\(", re.M),
    ],
    ".go": [
        re.compile(r"^func\s+(?:\([^)]*\)\s*)?(\w+)", re.M),
        re.compile(r"^type\s+(\w+)", re.M),
    ],
    ".rs": [re.compile(r"^(?:pub\s+)?(?:fn|struct|enum|trait)\s+(\w+)", re.M)],
    ".java": [
        re.compile(r"^\s{0,4}(?:public\s+)?(?:abstract\s+)?(?:class|interface|enum)\s+(\w+)", re.M)
    ],
}
PATTERNS[".ts"] = PATTERNS[".tsx"] = PATTERNS[".jsx"] = PATTERNS[".mjs"] = PATTERNS[".js"] + [
    re.compile(r"^(?:export\s+)?(?:interface|type)\s+(\w+)", re.M),
]

_cache: Dict[Path, Tuple[float, int, List[str]]] = {}


def project_files(root: Path) -> List[Path]:
    """Files of the project, relative to root: git's view when it is a repository."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            files = [Path(line) for line in result.stdout.splitlines() if line.strip()]
            return sorted(f for f in files if not _skipped(f) and (root / f).is_file())
    except (OSError, subprocess.SubprocessError):
        pass
    files = []
    for directory, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        for name in names:
            path = (Path(directory) / name).relative_to(root)
            if not _skipped(path):
                files.append(path)
        if len(files) > MAX_FILES * 4:
            break
    return sorted(files)


def _skipped(path: Path) -> bool:
    return (
        any(part in SKIP_DIRS for part in path.parts[:-1])
        or path.suffix.lower() in SKIP_SUFFIXES
        or path.name.startswith(".")
    )


def definitions(path: Path) -> List[str]:
    """Top-level names defined in a source file (classes with their methods)."""
    try:
        stat = path.stat()
    except OSError:
        return []
    cached = _cache.get(path)
    if cached and cached[:2] == (stat.st_mtime, stat.st_size):
        return cached[2]
    names: List[str] = []
    if stat.st_size <= MAX_FILE_BYTES:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        if path.suffix == ".py":
            names = _python_definitions(text)
        else:
            for pattern in PATTERNS.get(path.suffix, []):
                names.extend(m.group(1) for m in pattern.finditer(text))
            names = list(dict.fromkeys(names))
    _cache[path] = (stat.st_mtime, stat.st_size, names)
    return names


def _python_definitions(text: str) -> List[str]:
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return []
    names = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.append(node.name)
        elif isinstance(node, ast.ClassDef):
            methods = [
                n.name
                for n in node.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and (not n.name.startswith("_") or n.name == "__init__")
            ]
            names.append(f"{node.name}({', '.join(methods)})" if methods else node.name)
    return names


def build_repo_map(root: Path, mode: str = "auto", max_chars: int = MAX_CHARS) -> Optional[str]:
    """The map as a prompt section, or None (mode never, no files, or too big for auto)."""
    if mode == "never":
        return None
    files = project_files(root)
    if not files or (mode == "auto" and len(files) > MAX_FILES):
        return None
    lines: List[str] = []
    current_dir: Optional[Path] = None
    # Each directory once: its files together, the root first
    for path in sorted(files, key=lambda f: (f.parent.as_posix(), f.name)):
        if path.parent != current_dir:
            current_dir = path.parent
            if str(current_dir) != ".":
                lines.append(f"{current_dir.as_posix()}/")
        indent = "  " if str(path.parent) != "." else ""
        names = definitions(root / path)
        lines.append(f"{indent}{path.name}" + (f": {', '.join(names)}" if names else ""))
    header = "Project map (files and their top-level definitions; read files for details):"
    text = "\n".join(lines)
    if len(text) > max_chars:
        if mode == "auto":
            # Without the definitions, the layout alone
            text = "\n".join(line.split(": ", 1)[0] for line in lines)
            header = "Project map (files):"
        if len(text) > max_chars:
            if mode == "auto":
                return None
            cut = text[:max_chars].rsplit("\n", 1)[0]
            shown = cut.count("\n") + 1
            text = cut + f"\n… {len(lines) - shown} more lines"
    return f"{header}\n{text}"
