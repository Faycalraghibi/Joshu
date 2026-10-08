"""`joshu jobs`, `joshu run --background` and /background, /jobs (see joshu.core.jobs)."""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.markup import escape

jobs_app = typer.Typer(
    help="Background jobs: list, show, apply and stop them.", no_args_is_help=False
)
console = Console()

USAGE = (
    "Usage: /jobs [show <id> | apply <id> | approve <id> | deny <id> | stop <id> | log <id>]"
    "   /background <request>"
)


class JobCommands:
    """The job commands, for the CLI and the slash commands."""

    def __init__(self, console: Console) -> None:
        self.console = console

    def start(
        self,
        prompt: str,
        cwd: Path,
        permission_mode: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> bool:
        from joshu.core.jobs import JobError, start

        if not prompt.strip():
            self.console.print("Give the request to run in the background.")
            return False
        try:
            job = start(prompt, cwd, permission_mode or "accept_edits", model, provider)
        except JobError as e:
            self.console.print(f"[red]{escape(str(e))}[/red]")
            return False
        self.console.print(
            f"Started job [bold]{job.id}[/bold] in its own worktree ({escape(job.permission_mode)} "
            f"mode). It keeps running after you close the terminal.\n"
            f"[dim]joshu jobs show {job.id}   joshu jobs apply {job.id}   joshu jobs stop {job.id}[/dim]"
        )
        return True

    def list(self) -> None:
        from joshu.core.jobs import list_jobs

        jobs = list_jobs()
        if not jobs:
            self.console.print('No jobs. Start one with: joshu run --background "<request>"')
            return
        for job in jobs:
            state = job.status + (", applied" if job.applied else "")
            if job.pending:
                state = "waiting for you"
            changed = f"{len(job.files)} files" if job.files else "no changes"
            prompt = " ".join(job.prompt.split())
            prompt = prompt if len(prompt) <= 60 else prompt[:57] + "..."
            self.console.print(
                f"[bold]{job.id}[/bold]  {escape(state):18} {job.created_at[5:16].replace('T', ' ')}  "
                f"{changed:10}  {escape(prompt)}"
            )
            if job.pending:
                self.console.print(
                    f"   [yellow]asks to run {escape(job.pending['tool'])}: "
                    f"{escape(job.pending['summary'])}[/yellow]  "
                    f"[dim]joshu jobs approve {job.id} | deny {job.id}[/dim]"
                )

    def show(self, job_id: str) -> bool:
        from joshu.core.jobs import JobError, load, log_tail

        try:
            job = load(job_id)
        except JobError as e:
            self.console.print(f"[red]{escape(str(e))}[/red]")
            return False
        self.console.print(f"[bold]Job {job.id}[/bold]  {job.status}  started {job.created_at}")
        self.console.print(f"[dim]{escape(job.prompt)}[/dim]")
        if job.result:
            self.console.print(escape(job.result))
        if job.error:
            self.console.print(f"[red]{escape(job.error)}[/red]")
        if job.stat:
            self.console.print(escape(job.stat))
            hint = (
                "applied" if job.applied else f"on branch {job.branch}: joshu jobs apply {job.id}"
            )
            self.console.print(f"[dim]{escape(hint)}[/dim]")
        if job.session_id:
            self.console.print(f"[dim]Timeline: joshu trace {job.session_id}[/dim]")
        if job.status in ("running", "failed", "lost"):
            tail = log_tail(job, 15)
            if tail:
                self.console.print(f"[dim]{escape(tail)}[/dim]")
        return True

    def apply(self, job_id: str) -> bool:
        from joshu.core.jobs import JobError, apply

        try:
            job = apply(job_id)
        except JobError as e:
            self.console.print(f"[red]{escape(str(e))}[/red]")
            return False
        self.console.print(f"Applied job {job.id} to the working tree (not committed):")
        self.console.print(escape(job.stat))
        return True

    def decide(self, job_id: str, allow: bool) -> bool:
        from joshu.core.jobs import JobError, decide

        try:
            job = decide(job_id, allow)
        except JobError as e:
            self.console.print(f"[red]{escape(str(e))}[/red]")
            return False
        verb = "Approved" if allow else "Denied"
        self.console.print(f"{verb}: {escape(job.pending['summary'] if job.pending else '')}")
        return True

    def stop(self, job_id: str) -> bool:
        from joshu.core.jobs import JobError, stop

        try:
            job = stop(job_id)
        except JobError as e:
            self.console.print(f"[red]{escape(str(e))}[/red]")
            return False
        self.console.print(f"Stopped job {job.id}.")
        return True

    def log(self, job_id: str) -> bool:
        from joshu.core.jobs import JobError, load, log_tail

        try:
            job = load(job_id)
        except JobError as e:
            self.console.print(f"[red]{escape(str(e))}[/red]")
            return False
        self.console.print(escape(log_tail(job, 200)) or "(no output)")
        return True

    def run(self, arg: str) -> None:
        """/jobs <arg>"""
        try:
            words = shlex.split(arg)
        except ValueError:
            words = arg.split()
        if not words:
            self.list()
            return
        action, target = words[0], words[1] if len(words) > 1 else None
        handlers = {
            "show": self.show,
            "apply": self.apply,
            "stop": self.stop,
            "log": self.log,
            "approve": lambda target: self.decide(target, True),
            "deny": lambda target: self.decide(target, False),
        }
        if action in handlers and target:
            handlers[action](target)
        elif action == "list":
            self.list()
        else:
            self.console.print(USAGE)


def _exit(ok: bool) -> None:
    if not ok:
        raise typer.Exit(code=1)


@jobs_app.callback(invoke_without_command=True)
def jobs_main(ctx: typer.Context) -> None:
    """List background jobs, newest first."""
    if ctx.invoked_subcommand is None:
        JobCommands(console).list()


@jobs_app.command("list")
def list_jobs() -> None:
    """List background jobs, newest first."""
    JobCommands(console).list()


@jobs_app.command("show")
def show(job_id: str = typer.Argument(..., help="Job id (or a prefix)")) -> None:
    """A job's answer, changed files, and log while it runs or after it failed."""
    _exit(JobCommands(console).show(job_id))


@jobs_app.command("apply")
def apply(job_id: str = typer.Argument(..., help="Job id (or a prefix)")) -> None:
    """Put a finished job's work into the working tree (uncommitted)."""
    _exit(JobCommands(console).apply(job_id))


@jobs_app.command("approve")
def approve(job_id: str = typer.Argument(..., help="Job id (or a prefix)")) -> None:
    """Let a waiting job run the call it asks for."""
    _exit(JobCommands(console).decide(job_id, True))


@jobs_app.command("deny")
def deny(job_id: str = typer.Argument(..., help="Job id (or a prefix)")) -> None:
    """Refuse the call a waiting job asks for (it continues without it)."""
    _exit(JobCommands(console).decide(job_id, False))


@jobs_app.command("stop")
def stop(job_id: str = typer.Argument(..., help="Job id (or a prefix)")) -> None:
    """End a running job (its worktree and branch are removed)."""
    _exit(JobCommands(console).stop(job_id))


@jobs_app.command("log")
def log(job_id: str = typer.Argument(..., help="Job id (or a prefix)")) -> None:
    """The job process's output."""
    _exit(JobCommands(console).log(job_id))
