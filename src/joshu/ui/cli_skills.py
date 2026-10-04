"""`joshu skills`: list, add and remove agent skills."""

from __future__ import annotations

from typing import List, Optional

import typer
from rich.console import Console

skills_app = typer.Typer(help="List, add and remove agent skills.", no_args_is_help=False)
console = Console()


@skills_app.callback(invoke_without_command=True)
def skills_main(ctx: typer.Context) -> None:
    """List the skills Joshu can use here."""
    if ctx.invoked_subcommand is None:
        list_skills()


@skills_app.command("list")
def list_skills() -> None:
    """List the skills Joshu can use here."""
    from joshu.core.skills import discover_skills

    skills = discover_skills()
    if not skills:
        console.print("No skills. Add one with: joshu skills add <owner/repo> --skill <name>")
        return
    for name, skill in sorted(skills.items()):
        scope = skill.scope if skill.model_invocable else f"{skill.scope}, /{name} only"
        console.print(f"[bold]{name}[/bold]  {skill.description}  [dim]\\[{scope}][/dim]")


@skills_app.command("add")
def add(
    source: str = typer.Argument(
        ..., help="owner/repo, a repository URL, or a local directory (as for `npx skills add`)"
    ),
    skill: Optional[List[str]] = typer.Option(
        None, "--skill", "-s", help="Skill to install from the source (repeatable)"
    ),
    global_: bool = typer.Option(
        False, "--global", "-g", help="Install for your user (~/.joshu/skills), not the project"
    ),
    all_skills: bool = typer.Option(False, "--all", help="Install every skill in the source"),
) -> None:
    """Download skills and install them where Joshu finds them."""
    import sys

    from joshu.core.skill_install import (
        AddRequest,
        SkillInstallError,
        describe,
        install_skills,
    )

    request = AddRequest(
        source=source, skills=list(skill or []), global_=global_, all_skills=all_skills
    )
    if "@" in source and not source.startswith(("git@", "http")) and not request.skills:
        request.source, _, name = source.rpartition("@")
        request.skills.append(name)
    pick = None
    if sys.stdin.isatty() and sys.stdout.isatty():
        from joshu.ui.interactive.commands import _pick_skills

        pick = _pick_skills
    console.print(f"Fetching skills from {request.source}...")
    try:
        result = install_skills(request, pick=pick)
    except SkillInstallError as e:
        console.print(f"[red]{e}[/red]", highlight=False)
        raise typer.Exit(1)
    console.print(describe(result, request), highlight=False)
    if result.available:
        raise typer.Exit(1)


@skills_app.command("remove")
def remove(
    name: str = typer.Argument(..., help="Skill to remove"),
    global_: bool = typer.Option(False, "--global", "-g", help="Remove a user skill"),
) -> None:
    """Remove an installed skill."""
    from joshu.core.skill_install import SkillInstallError, remove_skill

    try:
        path = remove_skill(name, global_=global_)
    except SkillInstallError as e:
        console.print(f"[red]{e}[/red]", highlight=False)
        raise typer.Exit(1)
    console.print(f"Removed skill '{name}' ({path})", highlight=False)
