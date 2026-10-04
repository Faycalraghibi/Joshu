"""
Install skills from the places they are published.

Skill pages usually give an `npx skills add <package> --skill <name>`
command. Joshu accepts the same sources (GitHub `owner/repo`, repository URLs,
and anything else the `skills` tool knows), downloads them into a temporary
directory with that tool, and copies the skills into Joshu's skill
directories:

  project:  <project>/.agents/skills/<name>
  user:     ~/.joshu/skills/<name>   (--global)

Without Node.js, GitHub sources are fetched with `git clone` instead.
"""

from __future__ import annotations

import logging
import re
import shlex
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

from joshu.core.skills import SKILL_FILE, Skill, load_skill

logger = logging.getLogger(__name__)

PROJECT_SKILLS = Path(".agents") / "skills"
FETCH_TIMEOUT = 300
# The `skills` tool installs for this agent into <dir>/.agents/skills
_NPX_AGENT = "codex"
_GITHUB = re.compile(
    r"^(?:https?://github\.com/|git@github\.com:)?"
    r"(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+?)(?:\.git)?"
    r"(?:/tree/(?P<ref>[^/]+)(?:/(?P<path>.+))?)?/?$"
)

Runner = Callable[..., "subprocess.CompletedProcess[str]"]


class SkillInstallError(Exception):
    """A skill source couldn't be fetched or holds no matching skill."""


@dataclass
class AddRequest:
    """What to install: parsed from `npx skills add ...` or Joshu's own syntax."""

    source: str
    skills: List[str] = field(default_factory=list)  # empty: the only one, or ask
    global_: bool = False
    all_skills: bool = False


@dataclass
class InstallResult:
    installed: Dict[str, Path] = field(default_factory=dict)  # name -> directory
    replaced: List[str] = field(default_factory=list)
    available: List[str] = field(default_factory=list)  # when a choice is needed


def parse_add_command(text: str) -> AddRequest:
    """
    Parse what a user typed or pasted:

        npx skills add mattpocock/skills --skill grill-me
        skills add https://github.com/o/r -s a b -g
        mattpocock/skills --skill grill-me
        mattpocock/skills@grill-me
    """
    try:
        tokens = shlex.split(text.strip(), posix=True)
    except ValueError as e:
        raise SkillInstallError(f"Can't read that command: {e}") from e
    # Drop the launcher: npx [--yes|-y] skills (add|a|use)
    while tokens and tokens[0] in ("npx", "--yes", "-y", "pnpx", "bunx", "pnpm", "dlx"):
        tokens.pop(0)
    if tokens and tokens[0] in ("skills", "skills@latest"):
        tokens.pop(0)
    if tokens and tokens[0] in ("add", "a", "install", "use"):
        tokens.pop(0)

    request = AddRequest(source="")
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in ("-s", "--skill", "--skills"):
            index += 1
            while index < len(tokens) and not tokens[index].startswith("-"):
                request.skills.extend(s for s in tokens[index].split(",") if s)
                index += 1
            continue
        if token.startswith("--skill="):
            request.skills.extend(s for s in token.split("=", 1)[1].split(",") if s)
        elif token in ("-g", "--global"):
            request.global_ = True
        elif token == "--all":
            request.all_skills = True
        elif token.startswith("-"):
            pass  # -a/--agent, -y, --copy, ...: Joshu decides those
        elif not request.source:
            request.source = token
        index += 1

    if "*" in request.skills:
        request.skills, request.all_skills = [], True
    if not request.source:
        raise SkillInstallError("Which skill? e.g. /skills add mattpocock/skills --skill grill-me")
    # package@skill (the `skills use` form)
    if "@" in request.source and not request.source.startswith(("git@", "http")):
        request.source, _, name = request.source.rpartition("@")
        if name:
            request.skills.append(name)
    return request


def skills_add_part(command: str) -> Optional[str]:
    """
    The `npx skills add ...` command in `command`, or None. Models often
    prefix it with `cd <dir> &&`; anything else chained with it means no.
    """
    parts = [part.strip() for part in command.strip().split("&&")]
    if any(not part.lower().startswith(("cd ", "pushd ")) for part in parts[:-1]):
        return None
    return parts[-1] if is_skills_add_command(parts[-1]) else None


def is_skills_add_command(command: str) -> bool:
    """True for `npx skills add ...` (or pnpx/bunx/pnpm dlx, or plain `skills add`)."""
    if any(sep in command for sep in (";", "&", "|", ">", "<", "`", "$(", "\n")):
        return False
    try:
        tokens = shlex.split(command.strip(), posix=True)
    except ValueError:
        return False
    while tokens and tokens[0].lower() in ("npx", "npx.cmd", "pnpx", "bunx", "pnpm", "dlx"):
        tokens.pop(0)
        while tokens and tokens[0] in ("--yes", "-y"):
            tokens.pop(0)
    return (
        len(tokens) >= 3
        and tokens[0].split("@")[0] == "skills"
        and tokens[1] in ("add", "a", "install")
    )


def skills_destination(global_: bool, cwd: Optional[Path] = None) -> Path:
    """Where installed skills go: the project's .agents/skills, or ~/.joshu/skills."""
    if global_:
        from joshu.core.paths import joshu_home

        return joshu_home() / "skills"
    from joshu.core.instructions import find_repo_root

    cwd = (cwd or Path.cwd()).resolve()
    return (find_repo_root(cwd) or cwd) / PROJECT_SKILLS


def install_skills(
    request: AddRequest,
    cwd: Optional[Path] = None,
    runner: Optional[Runner] = None,
    pick: Optional[Callable[[List[str]], List[str]]] = None,
) -> InstallResult:
    """
    Fetch `request.source` and copy the requested skills into place.

    When the source holds several skills and none was named (and not
    `all_skills`), `pick` chooses among their names; without it (or when it
    picks none) nothing is installed and `available` lists them.
    """
    with tempfile.TemporaryDirectory(prefix="joshu-skills-") as temp:
        workdir = Path(temp)
        found = _fetch(request.source, workdir, runner or subprocess.run)
        chosen = _choose(found, request)
        if chosen is None and pick is not None:
            names = [name for name in pick(sorted(found)) if name in found]
            chosen = {name: found[name] for name in names} or None
        result = InstallResult()
        if chosen is None:
            result.available = sorted(found)
            return result
        target_root = skills_destination(request.global_, cwd)
        target_root.mkdir(parents=True, exist_ok=True)
        for name, skill in chosen.items():
            target = target_root / name
            if target.exists():
                shutil.rmtree(target)
                result.replaced.append(name)
            shutil.copytree(skill.path, target, ignore=shutil.ignore_patterns(".git"))
            result.installed[name] = target
        return result


def describe(result: InstallResult, request: AddRequest) -> str:
    """What happened, for the user (or the model)."""
    if result.available:
        names = ", ".join(result.available)
        return (
            f"{request.source} has {len(result.available)} skills: {names}. "
            "Name one with --skill <name> (or --all)."
        )
    lines = []
    for name, path in result.installed.items():
        verb = "Updated" if name in result.replaced else "Installed"
        lines.append(f"{verb} skill '{name}' in {path}")
    lines.append(
        "Skills run with the agent's permissions: read their SKILL.md before using them. "
        "/skills lists them; /<name> runs one."
    )
    return "\n".join(lines)


def remove_skill(name: str, global_: bool = False, cwd: Optional[Path] = None) -> Path:
    """Delete an installed skill's directory; returns it."""
    if not re.match(r"^[\w.-]+$", name) or name in (".", ".."):
        raise SkillInstallError(f"Not a skill name: {name}")
    target = skills_destination(global_, cwd) / name
    if not (target / SKILL_FILE).is_file():
        raise SkillInstallError(f"No installed skill '{name}' in {target.parent}")
    shutil.rmtree(target)
    return target


# ------------------------------------------------------------------ fetching


def _fetch(source: str, workdir: Path, runner: Runner) -> Dict[str, Skill]:
    """Download the source into `workdir`; the skills it holds by name."""
    errors: List[str] = []
    npx = shutil.which("npx")
    if npx:
        command = [npx, "--yes", "skills", "add", source, "--skill", "*"]
        command += ["-a", _NPX_AGENT, "--copy", "-y"]
        outcome = _run(runner, command, workdir)
        found = _scan(workdir / PROJECT_SKILLS)
        if found:
            return found
        errors.append(f"npx skills: {outcome}")
    match = _GITHUB.match(source)
    if match and shutil.which("git"):
        clone = workdir / "repo"
        command = ["git", "clone", "--depth", "1"]
        if match.group("ref"):
            command += ["--branch", match.group("ref")]
        url = f"https://github.com/{match.group('owner')}/{match.group('repo')}.git"
        outcome = _run(runner, command + [url, str(clone)], workdir)
        base = clone / match.group("path") if match.group("path") else clone
        found = _scan(base)
        if found:
            return found
        errors.append(f"git clone: {outcome}")
    local = Path(source).expanduser()
    if local.is_dir():
        found = _scan(local)
        if found:
            return found
        errors.append(f"no {SKILL_FILE} under {local}")
    if not errors:
        errors.append("install Node.js (for npx) or git, or give a GitHub owner/repo")
    raise SkillInstallError(f"Couldn't get skills from '{source}': " + "; ".join(errors))


def _run(runner: Runner, command: Sequence[str], cwd: Path) -> str:
    """Run a fetch command; a short description of how it went."""
    try:
        done = runner(
            list(command),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=FETCH_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return str(e)
    if done.returncode == 0:
        return "ok"
    output = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", (done.stderr or "") + (done.stdout or ""))
    lines = [line.strip(" │◇└") for line in output.splitlines() if line.strip(" │◇└")]
    return f"exit {done.returncode}" + (f" ({lines[-1][:200]})" if lines else "")


def _scan(root: Path) -> Dict[str, Skill]:
    """Skills under `root` (any depth), by name; the shallowest wins a name clash."""
    found: Dict[str, Skill] = {}
    if not root.is_dir():
        return found
    files = sorted(root.rglob(SKILL_FILE), key=lambda p: (len(p.parts), str(p)))
    for skill_file in files:
        if ".git" in skill_file.parts or "node_modules" in skill_file.parts:
            continue
        skill = load_skill(skill_file.parent)
        if skill is not None and skill.name not in found:
            found[skill.name] = skill
    return found


def _choose(found: Dict[str, Skill], request: AddRequest) -> Optional[Dict[str, Skill]]:
    if request.all_skills:
        return found
    if request.skills:
        by_dir = {skill.path.name: skill for skill in found.values()}
        chosen: Dict[str, Skill] = {}
        missing = []
        for name in request.skills:
            skill = found.get(name) or by_dir.get(name)
            if skill is None:
                missing.append(name)
            else:
                chosen[skill.name] = skill
        if missing:
            raise SkillInstallError(
                f"No skill named {', '.join(missing)} in {request.source}. "
                f"It has: {', '.join(sorted(found))}"
            )
        return chosen
    if len(found) == 1:
        return found
    return None
