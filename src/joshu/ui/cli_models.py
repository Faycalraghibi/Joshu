"""CLI commands for providers and models: joshu providers, joshu models, joshu use."""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

console = Console()

providers_app = typer.Typer(help="List, add and remove model providers.")
models_app = typer.Typer(help="List the models a provider serves; add named models.")


def _config():
    from joshu.core.config import get_config_manager

    return get_config_manager()


def _providers():
    from joshu.core.providers import ProviderError, get_providers

    try:
        return get_providers(_config().get("providers") or {})
    except ProviderError as e:
        console.print(f"[red]Invalid provider configuration: {e}[/red]")
        raise typer.Exit(code=2)


# --------------------------------------------------------------- providers


@providers_app.callback(invoke_without_command=True)
def providers_list(ctx: typer.Context) -> None:
    """List model providers and whether each one is ready to use."""
    if ctx.invoked_subcommand is not None:
        return
    from joshu.core.providers import DEFAULT_PROVIDER

    active = _config().get("provider") or DEFAULT_PROVIDER
    table = Table(title="Model providers")
    table.add_column("Provider")
    table.add_column("API key")
    table.add_column("Base URL")
    table.add_column("Default model")
    for name, p in _providers().items():
        label = f"[bold]{name}[/bold] (active)" if name == active else name
        if not p.requires_key:
            key = "[dim]not needed[/dim]"
        else:
            source = p.api_key_env or "api_key in config"
            status = "[green]set[/green]" if p.is_configured() else "[dim]missing[/dim]"
            key = f"{status} ({source})"
        table.add_row(label, key, p.base_url, p.default_model or "-")
    console.print(table)
    console.print(
        "[dim]See a provider's models: joshu models --provider <name>   "
        "Switch: joshu use <model> --provider <name>   "
        "Add one: joshu providers add <name> --base-url <url>[/dim]"
    )


@providers_app.command("add")
def providers_add(
    name: str = typer.Argument(..., help="Name to refer to the provider by."),
    base_url: str = typer.Option(..., "--base-url", help="OpenAI-compatible base URL (…/v1)."),
    api_key_env: Optional[str] = typer.Option(
        None, "--api-key-env", help="Environment variable holding the API key."
    ),
    model: Optional[str] = typer.Option(None, "--model", help="Default model for the provider."),
) -> None:
    """Add a provider (or override a built-in one's settings) in your user config."""
    from joshu.core.providers import ProviderError, get_providers

    fields = {"base_url": base_url}
    if api_key_env:
        fields["api_key_env"] = api_key_env
    if model:
        fields["default_model"] = model

    config = _config()
    custom = dict(config.get("providers") or {})
    custom[name] = {**(custom.get(name) or {}), **fields}
    try:
        get_providers(custom)
    except ProviderError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=2)

    config.set("providers", custom)
    config.save_config()
    console.print(f"Added provider {name} ({base_url}).")
    console.print(f"[dim]List its models: joshu models --provider {name}[/dim]")


@providers_app.command("remove")
def providers_remove(name: str = typer.Argument(..., help="Provider to remove.")) -> None:
    """Remove a provider you added (or your overrides of a built-in one)."""
    config = _config()
    custom = dict(config.get("providers") or {})
    if name not in custom:
        console.print(f"[yellow]{name} isn't in your config.[/yellow]")
        raise typer.Exit(code=1)
    del custom[name]
    config.set("providers", custom)
    config.save_config()
    console.print(f"Removed provider {name}.")


# ------------------------------------------------------------------ models


@models_app.callback(invoke_without_command=True)
def models_list(
    ctx: typer.Context,
    provider: Optional[str] = typer.Option(
        None, "--provider", "-p", help="Provider to list (default: the configured one)."
    ),
    search: Optional[str] = typer.Option(None, "--search", "-s", help="Only ids containing this."),
    tools: bool = typer.Option(False, "--tools", help="Only models known to support tools."),
    free: bool = typer.Option(False, "--free", help="Only free models (where known)."),
    show_all: bool = typer.Option(False, "--all", help="Show every match, not just 40."),
) -> None:
    """List the models a provider serves (live from its /models endpoint)."""
    if ctx.invoked_subcommand is not None:
        return
    from joshu.core.model_catalog import (
        CatalogError,
        filter_models,
        list_models,
        named_models,
    )
    from joshu.core.providers import DEFAULT_PROVIDER

    config = _config()
    name = provider or config.get("provider") or DEFAULT_PROVIDER
    providers = _providers()
    if name not in providers:
        console.print(f"[red]Unknown provider '{name}'.[/red] See joshu providers.")
        raise typer.Exit(code=2)

    try:
        models = filter_models(list_models(providers[name]), search, tools, free)
    except CatalogError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)

    current = config.get("model") if name == (config.get("provider") or DEFAULT_PROVIDER) else None
    shown = models if show_all else models[:40]
    table = Table(
        title=f"{name}: {len(models)} models" + (" (filtered)" if search or tools or free else "")
    )
    table.add_column("Model")
    table.add_column("Context", justify="right")
    table.add_column("Tools")
    table.add_column("Free")
    for m in shown:
        label = f"[bold]{m.id}[/bold] (current)" if m.id == current else m.id
        table.add_row(
            label,
            f"{m.context_length:,}" if m.context_length else "-",
            {True: "yes", False: "no", None: "?"}[m.tools],
            {True: "yes", False: "no", None: "?"}[m.free],
        )
    console.print(table)
    if len(shown) < len(models):
        console.print(
            f"[dim]{len(models) - len(shown)} more; narrow with --search or use --all[/dim]"
        )

    named = named_models(config.get("models"))
    if named:
        console.print("\n[bold]Named models[/bold]")
        for n in named.values():
            window = f", context {n.context_window:,}" if n.context_window else ""
            console.print(f"  {n.name}: {n.provider} / {n.model}{window}")
    console.print(f"[dim]Switch: joshu use <model> --provider {name}[/dim]")


@models_app.command("add")
def models_add(
    name: str = typer.Argument(..., help="Short name for the model, e.g. fast."),
    model: str = typer.Argument(..., help="Model id at the provider."),
    provider: Optional[str] = typer.Option(
        None, "--provider", "-p", help="Provider serving it (default: the configured one)."
    ),
    context_window: Optional[int] = typer.Option(
        None, "--context-window", help="The model's context size in tokens."
    ),
    check: bool = typer.Option(
        False, "--check", help="Send one small request to make sure the model works."
    ),
) -> None:
    """Save a named model; use it with --model <name>, joshu use <name> or /model <name>."""
    from joshu.core.providers import DEFAULT_PROVIDER

    config = _config()
    provider = provider or config.get("provider") or DEFAULT_PROVIDER
    if provider not in _providers():
        console.print(f"[red]Unknown provider '{provider}'.[/red] See joshu providers.")
        raise typer.Exit(code=2)
    _warn_if_missing(provider, model)
    if check and not _check(provider, model):
        raise typer.Exit(code=1)

    entry = {"provider": provider, "model": model}
    if context_window:
        entry["context_window"] = context_window
    named = dict(config.get("models") or {})
    named[name] = entry
    config.set("models", named)
    config.save_config()
    console.print(f"Saved {name}: {provider} / {model}")


@models_app.command("remove")
def models_remove(name: str = typer.Argument(..., help="Named model to remove.")) -> None:
    """Remove a named model."""
    config = _config()
    named = dict(config.get("models") or {})
    if name not in named:
        console.print(f"[yellow]No named model '{name}'.[/yellow]")
        raise typer.Exit(code=1)
    del named[name]
    config.set("models", named)
    config.save_config()
    console.print(f"Removed {name}.")


@models_app.command("check")
def models_check(
    model: str = typer.Argument(..., help="Model id, or a named model."),
    provider: Optional[str] = typer.Option(
        None, "--provider", "-p", help="Provider serving it (default: the configured one)."
    ),
) -> None:
    """Send one small request to see whether a model answers and calls tools."""
    from joshu.core.model_catalog import resolve_named_model
    from joshu.core.providers import DEFAULT_PROVIDER

    named = resolve_named_model(model)
    if named is not None:
        provider, model = named.provider, named.model
    provider = provider or _config().get("provider") or DEFAULT_PROVIDER
    if provider not in _providers():
        console.print(f"[red]Unknown provider '{provider}'.[/red] See joshu providers.")
        raise typer.Exit(code=2)
    if not _check(provider, model):
        raise typer.Exit(code=1)


def use(
    model: str = typer.Argument(..., help="Model id, or a named model."),
    provider: Optional[str] = typer.Option(
        None, "--provider", "-p", help="Provider serving it (default: the configured one)."
    ),
    check: bool = typer.Option(
        False, "--check", help="Send one small request to make sure the model works."
    ),
) -> None:
    """Make a model the default (saved in your user config)."""
    from joshu.core.model_catalog import resolve_named_model
    from joshu.core.providers import DEFAULT_PROVIDER

    config = _config()
    named = resolve_named_model(model)
    if named is not None:
        if check and not _check(named.provider, named.model):
            raise typer.Exit(code=1)
        config.set("model", named.name)
        config.save_config()
        console.print(f"Using {named.name}: {named.provider} / {named.model}")
        return

    provider = provider or config.get("provider") or DEFAULT_PROVIDER
    if provider not in _providers():
        console.print(f"[red]Unknown provider '{provider}'.[/red] See joshu providers.")
        raise typer.Exit(code=2)
    _warn_if_missing(provider, model)
    if check and not _check(provider, model):
        raise typer.Exit(code=1)
    config.set("provider", provider)
    config.set("model", model)
    config.save_config()
    console.print(f"Using {provider} / {model}")


def _check(provider: str, model: str) -> bool:
    """Run check_model and report; False when the model can't be used."""
    from joshu.core.model_catalog import check_model

    console.print(f"[dim]Checking {provider} / {model}...[/dim]")
    result = check_model(_providers()[provider], model)
    if not result.ok:
        console.print(f"[red]{model} didn't answer: {result.error}[/red]")
        return False
    if result.tool_call:
        console.print(f"[green]{model} works and calls tools ({result.seconds:.1f}s).[/green]")
    else:
        console.print(
            f"[yellow]{model} answered ({result.seconds:.1f}s) but didn't call the test "
            "tool; it may not handle the agent's tools well.[/yellow]"
        )
    return True


def _warn_if_missing(provider: str, model: str) -> None:
    """Check the model against the provider's list; warn, never block."""
    from joshu.core.model_catalog import CatalogError, list_models

    try:
        models = {m.id: m for m in list_models(_providers()[provider])}
    except CatalogError:
        console.print(f"[dim]Couldn't check {provider}'s model list; saving anyway.[/dim]")
        return
    if model not in models:
        console.print(
            f"[yellow]{provider} doesn't list '{model}'. Check the id with "
            f"joshu models --provider {provider} --search ...[/yellow]"
        )
    elif models[model].tools is False:
        console.print(f"[yellow]{model} doesn't support tool calling; the agent needs it.[/yellow]")
