"""
Skills: packaged instructions the agent loads only when a task needs them.

A skill is a directory with a SKILL.md file:

    .joshu/skills/release-notes/
        SKILL.md          # frontmatter (name, description) + instructions
        template.md       # optional supporting files

    ---
    name: release-notes
    description: Write release notes from the git log. Use when asked for a changelog or release notes.
    ---
    1. Run `git log --oneline <last tag>..HEAD` ...

Only each skill's name and description go into the system prompt. When a task
matches, the agent calls the `skill` tool to read the full instructions (and
any supporting file), so many skills cost little context until used.

Skills are found in, from highest priority:
  .joshu/skills/ and .agents/skills/ in the project (repository root or the
  working directory), then ~/.joshu/skills/.
A project skill replaces a user skill with the same name.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

SKILL_FILE = "SKILL.md"
PROJECT_DIRS = (Path(".joshu") / "skills", Path(".agents") / "skills")
MAX_FILE_CHARS = 60_000
_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)
_NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}$")


class SkillError(Exception):
    """A skill or skill file can't be loaded."""


@dataclass
class Skill:
    name: str
    description: str
    path: Path  # the skill's directory
    scope: str  # "project" or "user"

    def instructions(self) -> str:
        """The body of SKILL.md (without frontmatter)."""
        text = (self.path / SKILL_FILE).read_text(encoding="utf-8")
        match = _FRONTMATTER.match(text)
        return (match.group(2) if match else text).strip()

    def files(self) -> List[str]:
        """Supporting files, relative to the skill directory."""
        return sorted(
            p.relative_to(self.path).as_posix()
            for p in self.path.rglob("*")
            if p.is_file() and p.name != SKILL_FILE
        )[:200]

    def read_file(self, relative: str) -> str:
        """A supporting file's text; refuses paths outside the skill directory."""
        root = self.path.resolve()
        target = (root / relative).resolve()
        if root != target and root not in target.parents:
            raise SkillError(f"'{relative}' is outside the skill directory")
        if not target.is_file():
            raise SkillError(f"No file '{relative}' in skill '{self.name}'")
        text = target.read_text(encoding="utf-8", errors="replace")
        if len(text) > MAX_FILE_CHARS:
            text = text[:MAX_FILE_CHARS] + "\n[... truncated]"
        return text


def skill_dirs(cwd: Optional[Path] = None) -> List[tuple]:
    """(directory, scope) pairs searched for skills, highest priority first."""
    from joshu.core.instructions import find_repo_root
    from joshu.core.paths import joshu_home

    cwd = (cwd or Path.cwd()).resolve()
    roots = [cwd]
    repo = find_repo_root(cwd)
    if repo is not None and repo != cwd:
        roots.append(repo)
    dirs = [(root / d, "project") for root in roots for d in PROJECT_DIRS]
    dirs.append((joshu_home() / "skills", "user"))
    return dirs


def discover_skills(cwd: Optional[Path] = None) -> Dict[str, Skill]:
    """Available skills by name (project skills win over user skills)."""
    found: Dict[str, Skill] = {}
    for directory, scope in skill_dirs(cwd):
        if not directory.is_dir():
            continue
        for skill_file in sorted(directory.glob(f"*/{SKILL_FILE}")):
            skill = load_skill(skill_file.parent, scope)
            if skill is not None and skill.name not in found:
                found[skill.name] = skill
    return found


def load_skill(path: Path, scope: str = "project") -> Optional[Skill]:
    """Read a skill directory's frontmatter; None (with a warning) if invalid."""
    try:
        text = (path / SKILL_FILE).read_text(encoding="utf-8")
    except OSError as e:
        logger.warning(f"Could not read skill {path}: {e}")
        return None
    meta: Dict[str, Any] = {}
    match = _FRONTMATTER.match(text)
    if match:
        try:
            meta = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError as e:
            logger.warning(f"Invalid frontmatter in {path / SKILL_FILE}: {e}")
            return None
    name = str(meta.get("name") or path.name).strip()
    description = " ".join(str(meta.get("description") or "").split())
    if not _NAME.match(name):
        logger.warning(f"Skipping skill with invalid name '{name}' ({path})")
        return None
    if not description:
        logger.warning(f"Skipping skill '{name}': it needs a description ({path})")
        return None
    return Skill(name=name, description=description[:1024], path=path, scope=scope)


def skills_prompt(skills: Dict[str, Skill]) -> str:
    """The system prompt section listing skills, or "" when there are none."""
    if not skills:
        return ""
    lines = [
        "Skills: packaged instructions for specific kinds of tasks. When a task "
        "matches a skill's description, your first step is to call the `skill` tool "
        "with its name; then follow the instructions it returns.",
    ]
    lines += [f"- {s.name}: {s.description}" for s in skills.values()]
    return "\n".join(lines)


SKILL_TOOL_DESCRIPTION = (
    "Load a skill's instructions (see the Skills list in the system prompt). "
    "Pass `file` to read one of the skill's supporting files instead."
)


def run_skill_tool(skills: Dict[str, Skill], name: str, file: Optional[str] = None) -> str:
    """What the `skill` tool returns to the model."""
    skill = skills.get(name)
    if skill is None:
        available = ", ".join(sorted(skills)) or "none"
        return f"Error: no skill named '{name}'. Available skills: {available}."
    try:
        if file:
            text = skill.read_file(file)
            return f"File '{file}' of skill '{skill.name}':\n\n{text}"
        return skill_instructions(skill)
    except (OSError, SkillError) as e:
        return f"Error: {e}"


def skill_instructions(skill: Skill) -> str:
    """A skill's instructions, with where it lives and its supporting files."""
    body = skill.instructions()
    lines = [
        f"Skill '{skill.name}' (directory: {skill.path.resolve()}). "
        "Follow these instructions; scripts and files they mention are in that directory.",
        "",
        body,
    ]
    files = skill.files()
    if files:
        lines += [
            "",
            "Supporting files (read with the skill tool and `file`): " + ", ".join(files),
        ]
    return "\n".join(lines)
