"""
User-defined sub-agents the main agent can delegate to with the `task` tool.

Definitions live in `.joshu/agents/` in the project and `~/.joshu/agents/`
(project files win on a name clash). Markdown is the simple format:

    .joshu/agents/reviewer.md
    ---
    description: Reviews a change for bugs and risky patterns
    tools: read_file, glob, search_file_content    # optional; default read-only set
    model: openai/gpt-4.1                          # optional; default: the main model
    max_turns: 15                                  # optional
    ---
    You are a careful code reviewer. ...           # the sub-agent's system prompt

YAML/JSON agent definitions (joshu.agents format) are also accepted.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

AGENTS_SUBDIR = Path(".joshu") / "agents"
_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
_FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.S)
# Model names in joshu.agents definitions that mean "use the main agent's model"
_INHERIT_MODELS = {"", "inherit", "default"}


@dataclass
class SubagentSpec:
    """A named sub-agent: its instructions, tools and limits."""

    name: str
    description: str
    system_prompt: str
    tools: Optional[List[str]] = None  # None: the default read-only tools
    model: Optional[str] = None  # None: the main agent's model
    max_turns: Optional[int] = None
    path: Optional[Path] = None


def agent_dirs(cwd: Optional[Path] = None) -> List[Path]:
    """Directories searched for sub-agent definitions, lowest priority first."""
    from joshu.core.plugins import plugin_dirs
    from joshu.core.sessions import joshu_home

    cwd = cwd or Path.cwd()
    return [*plugin_dirs("agents"), joshu_home() / "agents", cwd / AGENTS_SUBDIR]


def discover_subagents(cwd: Optional[Path] = None) -> Dict[str, SubagentSpec]:
    """All sub-agent definitions by name; project definitions override user ones."""
    specs: Dict[str, SubagentSpec] = {}
    for directory in agent_dirs(cwd):
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            for spec in load_subagents(path):
                specs[spec.name] = spec
    return specs


def load_subagents(path: Path) -> List[SubagentSpec]:
    """Parse one definition file; an empty list for other or invalid files."""
    if not path.is_file():
        return []
    if path.suffix == ".md":
        spec = _load_markdown(path)
        return [spec] if spec else []
    if path.suffix in (".yaml", ".yml", ".json"):
        return _load_definitions(path)
    return []


def _load_markdown(path: Path) -> Optional[SubagentSpec]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning(f"Could not read agent {path}: {e}")
        return None

    fields: Dict[str, str] = {}
    match = _FRONT_MATTER.match(text)
    if match:
        for line in match.group(1).splitlines():
            key, sep, value = line.partition(":")
            if sep:
                fields[key.strip()] = value.split(" #")[0].strip().strip("\"'")
        text = text[match.end() :]

    name = fields.get("name") or path.stem
    if not _NAME_PATTERN.match(name):
        logger.warning(f"Skipping agent {path}: invalid name '{name}'")
        return None
    if not text.strip():
        logger.warning(f"Skipping agent {path}: empty system prompt")
        return None

    from joshu.core.claude_compat import MODEL_ALIASES, joshu_tool

    tools = None
    if fields.get("tools"):
        # Claude Code names (Read, Bash, ...) work too
        tools = [joshu_tool(t) for t in re.split(r"[,\s]+", fields["tools"]) if t.strip()]
    model = fields.get("model") or None
    if model and model.lower() in MODEL_ALIASES:
        model = None  # a Claude Code alias (sonnet, opus, ...): the main model

    max_turns = None
    if fields.get("max_turns", "").isdigit():
        max_turns = int(fields["max_turns"]) or None

    return SubagentSpec(
        name=name,
        description=fields.get("description") or f"The {name} sub-agent",
        system_prompt=text.strip(),
        tools=tools,
        model=model,
        max_turns=max_turns,
        path=path,
    )


def _load_definitions(path: Path) -> List[SubagentSpec]:
    from joshu.agents.loader import load_agents_from_path

    try:
        definitions = load_agents_from_path(path)
    except Exception as e:
        logger.warning(f"Could not load agent definitions from {path}: {e}")
        return []

    specs = []
    for definition in definitions:
        if not definition.enabled:
            continue
        model = definition.model_config.model_name.strip()
        specs.append(
            SubagentSpec(
                name=definition.name,
                description=definition.description,
                system_prompt=definition.prompt_config.system_prompt,
                tools=list(definition.tool_config.allowed_tools) or None,
                model=None if model.lower() in _INHERIT_MODELS else model,
                max_turns=definition.run_config.max_turns,
                path=path,
            )
        )
    return specs
