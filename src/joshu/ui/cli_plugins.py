"""`joshu plugin`: install, list, update and remove plugins (see joshu.core.plugins)."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.markup import escape

plugin_app = typer.Typer(help="Install, list, update and remove plugins.", no_args_is_help=False)
console = Console()


def _fail(message: str) -> None:
    console.print(f"[red]{escape(message)}[/red]")
    raise typer.Exit(code=1)


@plugin_app.callback(invoke_without_command=True)
def plugin_main(ctx: typer.Context) -> None:
    """List installed plugins."""
    if ctx.invoked_subcommand is None:
        list_plugins()


@plugin_app.command("list")
def list_plugins() -> None:
    """List installed plugins and what they add."""
    from joshu.core.plugins import installed_plugins, plugins_dir

    plugins = installed_plugins()
    if not plugins:
        console.print("No plugins. Install one with: joshu plugin install <git-url or directory>")
        return
    for plugin in plugins:
        state = "" if plugin.enabled else "  [yellow](disabled)[/yellow]"
        version = f" {escape(plugin.version)}" if plugin.version else ""
        console.print(
            f"[bold]{escape(plugin.name)}[/bold]{version}{state}  {escape(plugin.description)}"
        )
        for line in plugin.contents():
            console.print(f"  [dim]{escape(line)}[/dim]")
    console.print(f"[dim]In {plugins_dir()}[/dim]")


@plugin_app.command("install")
def install(
    source: str = typer.Argument(..., help="A git URL or a local directory with joshu-plugin.yaml"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Don't ask for confirmation"),
    force: bool = typer.Option(
        False, "--force", help="Replace an installed plugin of the same name"
    ),
) -> None:
    """Install a plugin. Its hooks and MCP servers run commands: install only ones you trust."""
    from joshu.core.plugins import PluginError
    from joshu.core.plugins import install as install_plugin
    from joshu.core.plugins import prepare

    try:
        prepared = prepare(source)
    except PluginError as e:
        _fail(str(e))
    plugin = prepared[0]
    console.print(
        f"[bold]{escape(plugin.name)}[/bold] {escape(plugin.version)}  {escape(plugin.description)}"
    )
    for line in plugin.contents() or ["(nothing to add)"]:
        console.print(f"  {escape(line)}")
    runs_commands = bool(plugin.hooks or plugin.mcp_servers)
    if runs_commands:
        console.print("[yellow]Its hooks and MCP servers run commands on this machine.[/yellow]")
    if not yes and not typer.confirm("Install it?", default=not runs_commands):
        import shutil

        shutil.rmtree(prepared[1], ignore_errors=True)
        console.print("Not installed.")
        return
    try:
        installed = install_plugin(source, force=force, prepared=prepared)
    except PluginError as e:
        _fail(str(e))
    console.print(
        f"Installed {escape(installed.name)} to {installed.path}. It applies to new sessions."
    )


@plugin_app.command("remove")
def remove(name: str = typer.Argument(..., help="Plugin name")) -> None:
    """Uninstall a plugin."""
    from joshu.core.plugins import PluginError
    from joshu.core.plugins import remove as remove_plugin

    try:
        remove_plugin(name)
    except PluginError as e:
        _fail(str(e))
    console.print(f"Removed {escape(name)}.")


@plugin_app.command("update")
def update(name: str = typer.Argument(..., help="Plugin name")) -> None:
    """Install a plugin again from where it came from."""
    from joshu.core.plugins import PluginError
    from joshu.core.plugins import update as update_plugin

    try:
        plugin = update_plugin(name)
    except PluginError as e:
        _fail(str(e))
    console.print(f"Updated {escape(plugin.name)} to {escape(plugin.version or 'the latest')}.")


@plugin_app.command("enable")
def enable(name: str = typer.Argument(..., help="Plugin name")) -> None:
    """Turn an installed plugin back on."""
    _set(name, True)


@plugin_app.command("disable")
def disable(name: str = typer.Argument(..., help="Plugin name")) -> None:
    """Keep a plugin installed but unused."""
    _set(name, False)


def _set(name: str, enabled: bool) -> None:
    from joshu.core.plugins import PluginError, set_enabled

    try:
        set_enabled(name, enabled)
    except PluginError as e:
        _fail(str(e))
    console.print(
        f"{escape(name)} {'enabled' if enabled else 'disabled'}. It applies to new sessions."
    )
