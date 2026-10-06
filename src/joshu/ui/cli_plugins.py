"""
`joshu plugin` and `/plugin`: install, list, update and remove plugins, and
the marketplaces they come from (see joshu.core.plugins).
"""

from __future__ import annotations

import shlex
import shutil
from typing import Callable, Optional

import typer
from rich.console import Console
from rich.markup import escape

plugin_app = typer.Typer(
    help="Install, list, update and remove plugins (Joshu or Claude Code format).",
    no_args_is_help=False,
)
marketplace_app = typer.Typer(help="Add, list, update and remove plugin marketplaces.")
plugin_app.add_typer(marketplace_app, name="marketplace")
console = Console()

USAGE = (
    "Usage: /plugin [list] | install <source | plugin@marketplace> | remove <name> | "
    "update <name> | enable <name> | disable <name> | "
    "marketplace add <owner/repo | git-url | dir> | marketplace list | "
    "marketplace update <name> | marketplace remove <name>"
)


class PluginFailure(Exception):
    """A plugin command failed (the message was already printed)."""


class PluginCommands:
    """The plugin commands, for the CLI and the /plugin slash command."""

    def __init__(
        self,
        console: Console,
        confirm: Callable[[str, bool], bool],
        applies: str = "It applies to new sessions.",
    ) -> None:
        self.console = console
        self.confirm = confirm
        self.applies = applies

    def fail(self, message: str) -> None:
        self.console.print(f"[red]{escape(message)}[/red]")
        raise PluginFailure(message)

    # ------------------------------------------------------------- plugins

    def list(self) -> None:
        from joshu.core.plugins import installed_plugins, list_marketplaces, plugins_dir

        plugins = installed_plugins()
        if not plugins:
            self.console.print(
                "No plugins. Install one with: plugin install <owner/repo, git URL, directory "
                "or plugin@marketplace>"
            )
        for plugin in plugins:
            state = "" if plugin.enabled else "  [yellow](disabled)[/yellow]"
            version = f" {escape(plugin.version)}" if plugin.version else ""
            self.console.print(
                f"[bold]{escape(plugin.name)}[/bold]{version}{state}  {escape(plugin.description)}"
            )
            for line in plugin.contents():
                self.console.print(f"  [dim]{escape(line)}[/dim]")
        markets = list_marketplaces()
        if markets:
            names = ", ".join(m.name for m in markets)
            self.console.print(f"[dim]Marketplaces: {escape(names)}[/dim]")
        if plugins:
            self.console.print(f"[dim]In {plugins_dir()}[/dim]")

    def install(self, source: str, yes: bool = False, force: bool = False) -> None:
        from joshu.core.plugins import PluginError
        from joshu.core.plugins import install as install_plugin
        from joshu.core.plugins import prepare

        try:
            prepared = prepare(source)
        except PluginError as e:
            self.fail(str(e))
        plugin = prepared[0]
        self.console.print(
            f"[bold]{escape(plugin.name)}[/bold] {escape(plugin.version)}  "
            f"{escape(plugin.description)}"
        )
        for line in plugin.contents() or ["(nothing to add)"]:
            self.console.print(f"  {escape(line)}")
        runs_commands = bool(plugin.hooks or plugin.mcp_servers)
        if runs_commands:
            self.console.print(
                "[yellow]Its hooks and MCP servers run commands on this machine.[/yellow]"
            )
        if not yes and not self.confirm("Install it?", not runs_commands):
            shutil.rmtree(prepared[1], ignore_errors=True)
            self.console.print("Not installed.")
            return
        try:
            installed = install_plugin(source, force=force, prepared=prepared)
        except PluginError as e:
            self.fail(str(e))
        self.console.print(
            f"Installed {escape(installed.name)} to {installed.path}. {self.applies}"
        )

    def remove(self, name: str) -> None:
        from joshu.core.plugins import PluginError
        from joshu.core.plugins import remove as remove_plugin

        try:
            remove_plugin(name)
        except PluginError as e:
            self.fail(str(e))
        self.console.print(f"Removed {escape(name)}.")

    def update(self, name: str) -> None:
        from joshu.core.plugins import PluginError
        from joshu.core.plugins import update as update_plugin

        try:
            plugin = update_plugin(name)
        except PluginError as e:
            self.fail(str(e))
        self.console.print(
            f"Updated {escape(plugin.name)} to {escape(plugin.version or 'the latest')}."
        )

    def set_enabled(self, name: str, enabled: bool) -> None:
        from joshu.core.plugins import PluginError, set_enabled

        try:
            set_enabled(name, enabled)
        except PluginError as e:
            self.fail(str(e))
        state = "enabled" if enabled else "disabled"
        self.console.print(f"{escape(name)} {state}. {self.applies}")

    # -------------------------------------------------------- marketplaces

    def marketplace_add(self, source: str) -> None:
        from joshu.core.plugins import PluginError, add_marketplace

        try:
            market = add_marketplace(source)
        except PluginError as e:
            self.fail(str(e))
        self.console.print(f"Added marketplace [bold]{escape(market.name)}[/bold].")
        self._show_market(market)

    def marketplace_list(self) -> None:
        from joshu.core.plugins import list_marketplaces

        markets = list_marketplaces()
        if not markets:
            self.console.print("No marketplaces. Add one with: plugin marketplace add <owner/repo>")
        for market in markets:
            self._show_market(market)

    def marketplace_update(self, name: str) -> None:
        from joshu.core.plugins import PluginError, update_marketplace

        try:
            market = update_marketplace(name)
        except PluginError as e:
            self.fail(str(e))
        self.console.print(f"Updated marketplace {escape(market.name)}.")
        self._show_market(market)

    def marketplace_remove(self, name: str) -> None:
        from joshu.core.plugins import PluginError, remove_marketplace

        try:
            remove_marketplace(name)
        except PluginError as e:
            self.fail(str(e))
        self.console.print(f"Removed marketplace {escape(name)} (its installed plugins stay).")

    def _show_market(self, market) -> None:
        self.console.print(f"[bold]{escape(market.name)}[/bold]  {escape(market.description)}")
        for entry in market.plugins:
            self.console.print(
                f"  {escape(entry['name'])}  [dim]{escape(str(entry.get('description', '')))}[/dim]"
            )
        if market.plugins:
            example = f"{market.plugins[0]['name']}@{market.name}"
            self.console.print(f"[dim]Install with: plugin install {escape(example)}[/dim]")

    # ------------------------------------------------------- slash command

    def run(self, arg: str) -> None:
        """`/plugin <arg>`: the same commands from inside a session."""
        try:
            words = shlex.split(arg)
        except ValueError as e:
            self.console.print(f"[red]{escape(str(e))}[/red]")
            return
        flags = {w for w in words if w.startswith("-")}
        words = [w for w in words if not w.startswith("-")]
        command, rest = (words[0], words[1:]) if words else ("list", [])
        one: Optional[str] = rest[0] if rest else None
        try:
            if command == "list" and not rest:
                self.list()
            elif command in ("install", "add", "i") and one:
                self.install(one, yes="--yes" in flags or "-y" in flags, force="--force" in flags)
            elif command in ("remove", "uninstall", "rm") and one:
                self.remove(one)
            elif command == "update" and one:
                self.update(one)
            elif command in ("enable", "disable") and one:
                self.set_enabled(one, command == "enable")
            elif command in ("marketplace", "market", "marketplaces"):
                sub, target = (
                    (rest[0], rest[1] if len(rest) > 1 else None) if rest else ("list", None)
                )
                if sub == "add" and target:
                    self.marketplace_add(target)
                elif sub == "list":
                    self.marketplace_list()
                elif sub == "update" and target:
                    self.marketplace_update(target)
                elif sub in ("remove", "rm") and target:
                    self.marketplace_remove(target)
                else:
                    self.console.print(USAGE)
            else:
                self.console.print(USAGE)
        except PluginFailure:
            pass


def _cli() -> PluginCommands:
    return PluginCommands(
        console, lambda question, default: typer.confirm(question, default=default)
    )


def _exit_on_failure(action: Callable[[], None]) -> None:
    try:
        action()
    except PluginFailure:
        raise typer.Exit(code=1)


@plugin_app.callback(invoke_without_command=True)
def plugin_main(ctx: typer.Context) -> None:
    """List installed plugins."""
    if ctx.invoked_subcommand is None:
        _cli().list()


@plugin_app.command("list")
def list_plugins() -> None:
    """List installed plugins and what they add."""
    _cli().list()


@plugin_app.command("install")
def install(
    source: str = typer.Argument(
        ..., help="owner/repo, a git URL, a directory, or plugin@marketplace"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Don't ask for confirmation"),
    force: bool = typer.Option(
        False, "--force", help="Replace an installed plugin of the same name"
    ),
) -> None:
    """Install a plugin. Its hooks and MCP servers run commands: install only ones you trust."""
    _exit_on_failure(lambda: _cli().install(source, yes=yes, force=force))


@plugin_app.command("remove")
def remove(name: str = typer.Argument(..., help="Plugin name")) -> None:
    """Uninstall a plugin."""
    _exit_on_failure(lambda: _cli().remove(name))


@plugin_app.command("update")
def update(name: str = typer.Argument(..., help="Plugin name")) -> None:
    """Install a plugin again from where it came from."""
    _exit_on_failure(lambda: _cli().update(name))


@plugin_app.command("enable")
def enable(name: str = typer.Argument(..., help="Plugin name")) -> None:
    """Turn an installed plugin back on."""
    _exit_on_failure(lambda: _cli().set_enabled(name, True))


@plugin_app.command("disable")
def disable(name: str = typer.Argument(..., help="Plugin name")) -> None:
    """Keep a plugin installed but unused."""
    _exit_on_failure(lambda: _cli().set_enabled(name, False))


@marketplace_app.command("add")
def marketplace_add(
    source: str = typer.Argument(..., help="owner/repo, a git URL or a directory"),
) -> None:
    """Add a marketplace (a repository with .claude-plugin/marketplace.json)."""
    _exit_on_failure(lambda: _cli().marketplace_add(source))


@marketplace_app.command("list")
def marketplace_list() -> None:
    """List added marketplaces and their plugins."""
    _cli().marketplace_list()


@marketplace_app.command("update")
def marketplace_update(name: str = typer.Argument(..., help="Marketplace name")) -> None:
    """Fetch a marketplace again."""
    _exit_on_failure(lambda: _cli().marketplace_update(name))


@marketplace_app.command("remove")
def marketplace_remove(name: str = typer.Argument(..., help="Marketplace name")) -> None:
    """Forget a marketplace (installed plugins stay)."""
    _exit_on_failure(lambda: _cli().marketplace_remove(name))
