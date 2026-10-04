"""
Memory the agent keeps across sessions.

Each memory is a small Markdown file with frontmatter, and each scope has an
index (MEMORY.md, one line per memory) that is added to the system prompt at
the start of every session. The agent reads a memory's full text with the
`memory` tool when it is relevant, and saves, updates or deletes memories as
it learns things worth keeping.

    ~/.joshu/memory/                       user scope: applies in every project
    ~/.joshu/projects/<project>/memory/    project scope: this repository only

    ---
    name: test-command
    description: Tests need SKIP_LLM_TESTS=1 or they call a real model
    type: project
    updated: 2026-10-04
    ---
    Run tests with SKIP_LLM_TESTS=1 ...

Memory lives under JOSHU_HOME, never in the project, and is plain text the
user can read and edit.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

INDEX_FILE = "MEMORY.md"
TYPES = ("user", "feedback", "project", "reference")
SCOPES = ("project", "user")
MAX_INDEX_LINES = 150
MAX_CONTENT_CHARS = 8_000
_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)


class MemoryInputError(Exception):
    """Invalid memory request (bad name, scope or type)."""


@dataclass
class Memory:
    name: str
    description: str
    type: str
    content: str
    scope: str
    path: Path


def project_key(cwd: Optional[Path] = None) -> str:
    """
    Directory name for a project's memory: the repository root's (or cwd's)
    name plus a short hash of its full path. Kept short for Windows path limits.
    """
    import hashlib

    from joshu.core.instructions import find_repo_root

    cwd = (cwd or Path.cwd()).resolve()
    root = find_repo_root(cwd) or cwd
    digest = hashlib.sha256(str(root).lower().encode("utf-8")).hexdigest()[:10]
    name = re.sub(r"[^A-Za-z0-9]+", "-", root.name).strip("-")[:40] or "root"
    return f"{name}-{digest}"


def memory_dir(scope: str, cwd: Optional[Path] = None) -> Path:
    from joshu.core.paths import joshu_home

    if scope == "user":
        return joshu_home() / "memory"
    if scope == "project":
        return joshu_home() / "projects" / project_key(cwd) / "memory"
    raise MemoryInputError(f"scope must be one of {', '.join(SCOPES)}")


def save_memory(
    name: str,
    description: str,
    content: str,
    type: str = "project",
    scope: str = "project",
    cwd: Optional[Path] = None,
) -> Memory:
    """Create or replace a memory and refresh the scope's index."""
    name = name.strip().lower()
    if not _NAME.match(name):
        raise MemoryInputError(
            "name must be a short kebab-case slug (lowercase letters, digits, hyphens)"
        )
    if type not in TYPES:
        raise MemoryInputError(f"type must be one of {', '.join(TYPES)}")
    description = " ".join(description.split())
    content = content.strip()
    # Models often send only one of the two: use it for both
    if not content:
        content = description
    if not description:
        first_line = next((line for line in content.splitlines() if line.strip()), "")
        description = " ".join(first_line.split())[:120]
    if not content:
        raise MemoryInputError("content is required")
    if len(content) > MAX_CONTENT_CHARS:
        raise MemoryInputError(
            f"content is too long ({len(content)} chars, max {MAX_CONTENT_CHARS}); "
            "keep memories short and focused"
        )

    directory = memory_dir(scope, cwd)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.md"
    meta = {
        "name": name,
        "description": description[:200],
        "type": type,
        "updated": date.today().isoformat(),
    }
    frontmatter = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()
    path.write_text(f"---\n{frontmatter}\n---\n{content}\n", encoding="utf-8")
    _write_index(directory)
    return Memory(name, meta["description"], type, content, scope, path)


def delete_memory(name: str, scope: str = "project", cwd: Optional[Path] = None) -> bool:
    directory = memory_dir(scope, cwd)
    path = directory / f"{name.strip().lower()}.md"
    if not _NAME.match(path.stem) or not path.is_file():
        return False
    path.unlink()
    _write_index(directory)
    return True


def read_memory(name: str, scope: str = "project", cwd: Optional[Path] = None) -> Optional[Memory]:
    path = memory_dir(scope, cwd) / f"{name.strip().lower()}.md"
    if not _NAME.match(path.stem) or not path.is_file():
        return None
    return _parse(path, scope)


def list_memories(scope: str, cwd: Optional[Path] = None) -> List[Memory]:
    directory = memory_dir(scope, cwd)
    if not directory.is_dir():
        return []
    memories = []
    for path in sorted(directory.glob("*.md")):
        if path.name == INDEX_FILE:
            continue
        memory = _parse(path, scope)
        if memory is not None:
            memories.append(memory)
    return memories


def memory_prompt(cwd: Optional[Path] = None) -> str:
    """
    System prompt section: how to use memory, plus the memories themselves.

    Short memories are shown in full (until INLINE_BUDGET characters are used),
    so the model sees them without a tool call; the rest are listed by name and
    description for the model to read when relevant.
    """
    budget = INLINE_BUDGET
    sections = []
    for scope, title in (("project", "Project memory"), ("user", "User memory (all projects)")):
        lines = []
        for memory in list_memories(scope, cwd)[:MAX_INDEX_LINES]:
            text = " ".join(memory.content.split())
            if len(text) <= MAX_INLINE_CHARS and len(text) <= budget:
                budget -= len(text)
                lines.append(f"- {memory.name}: {text}")
            else:
                lines.append(f"- {memory.name}: {memory.description} (read for details)")
        if lines:
            sections.append(f"{title}:\n" + "\n".join(lines))
    if not sections:
        return SHORT_MEMORY_GUIDE
    return MEMORY_GUIDE + "\n\n" + "\n\n".join(sections)


# Used while there are no memories yet (keeps every request small)
SHORT_MEMORY_GUIDE = (
    "Memory: no notes saved yet. Use the `memory` tool to save what will matter in future "
    "sessions (when asked to remember something, or a lasting preference, decision or fact "
    "not in the code)."
)

INLINE_BUDGET = 6_000
MAX_INLINE_CHARS = 500

MEMORY_GUIDE = """Memory: notes you keep across sessions with the `memory` tool. What you already know from earlier sessions is listed below; use it when answering. Entries marked "(read for details)" are summaries: read them with memory(action="read") when relevant.
When the user asks you to remember something, save it right away with memory(action="save"); no need to explore first.
Also save a memory when you learn something that will matter in future sessions and isn't already in the code, git history or instruction files:
- type user (scope user): who the user is, their role and preferences
- type feedback: corrections or confirmed approaches to how you should work, with the reason
- type project: goals, decisions and constraints of this project, with the reason; write dates as absolute dates
- type reference: where to find things (URLs, dashboards, tickets)
Don't save what only matters to the current task. Update an existing memory (save with its name) instead of adding a duplicate, and delete memories that turn out to be wrong. If a memory conflicts with what you find in the files, trust the files and update the memory."""


# --------------------------------------------------------------- internal


def _parse(path: Path, scope: str) -> Optional[Memory]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    match = _FRONTMATTER.match(text)
    meta = {}
    body = text
    if match:
        try:
            meta = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError:
            meta = {}
        body = match.group(2)
    return Memory(
        name=path.stem,
        description=" ".join(str(meta.get("description") or "").split()) or path.stem,
        type=str(meta.get("type") or "project"),
        content=body.strip(),
        scope=scope,
        path=path,
    )


def _write_index(directory: Path) -> None:
    memories = [
        m
        for m in (_parse(p, "") for p in sorted(directory.glob("*.md")) if p.name != INDEX_FILE)
        if m
    ]
    lines = [f"- {m.name}: {m.description}" for m in memories]
    (directory / INDEX_FILE).write_text(
        "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8"
    )


def run_memory_tool(
    action: str,
    name: str = "",
    description: str = "",
    content: str = "",
    type: str = "project",
    scope: str = "project",
    cwd: Optional[Path] = None,
) -> Dict[str, object]:
    """What the `memory` tool returns to the model."""
    try:
        if scope not in SCOPES:
            raise MemoryInputError(f"scope must be one of {', '.join(SCOPES)}")
        if action == "save":
            memory = save_memory(name, description, content, type, scope, cwd)
            return {"success": True, "message": f"Saved {scope} memory '{memory.name}'"}
        if action == "read":
            memory = read_memory(name, scope, cwd)
            if memory is None:
                other = "user" if scope == "project" else "project"
                memory = read_memory(name, other, cwd)
            if memory is None:
                return {"success": False, "error": f"No memory named '{name}'"}
            return {
                "success": True,
                "name": memory.name,
                "type": memory.type,
                "scope": memory.scope,
                "content": memory.content,
            }
        if action == "delete":
            if delete_memory(name, scope, cwd):
                return {"success": True, "message": f"Deleted {scope} memory '{name}'"}
            return {"success": False, "error": f"No {scope} memory named '{name}'"}
        raise MemoryInputError("action must be save, read or delete")
    except MemoryInputError as e:
        return {"success": False, "error": str(e)}
