"""
Plugins: one installable bundle of skills, commands, output styles, hooks and
MCP servers.

A plugin is a directory with a `joshu-plugin.yaml` manifest:

    name: release-tools
    version: 1.2.0
    description: Changelog and release helpers
    hooks:                       # same form as `hooks:` in config.yaml
      stop:
        - python ${PLUGIN_DIR}/hooks/check.py
    mcp_servers:                 # same form as `mcp_servers:` in config.yaml
      tracker:
        command: npx
        args: ["-y", "tracker-mcp"]

and any of `skills/`, `commands/` and `output-styles/` next to it, laid out as
in `.joshu/`. `joshu plugin install <git-url | path>` copies it to
~/.joshu/plugins/<name>/; the loaders then search its directories after the
project's and the user's own (which win on a name clash). `${PLUGIN_DIR}` in
hook commands and MCP server settings is the plugin's installed directory.

Claude Code plugins work as they are: `.claude-plugin/plugin.json` as the
manifest, `hooks/hooks.json` (events and tool names translated, see
joshu.core.claude_compat), `.mcp.json`, `agents/`, `commands/` and `skills/`,
with `${CLAUDE_PLUGIN_ROOT}`. So do their marketplaces: `joshu plugin
marketplace add owner/repo` reads `.claude-plugin/marketplace.json`, and
`joshu plugin install <plugin>@<marketplace>` installs from it. A source can
be a git URL, `owner/repo` (GitHub) or a directory.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

MANIFEST = "joshu-plugin.yaml"
CLAUDE_MANIFEST = Path(".claude-plugin") / "plugin.json"
MARKETPLACE_FILE = Path(".claude-plugin") / "marketplace.json"
MARKETPLACES = ".marketplaces"  # inside plugins_dir()
SOURCE_FILE = ".joshu-plugin-source.json"  # where it was installed from (for update)
DISABLED_FILE = ".disabled"
NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


class PluginError(Exception):
    """A plugin can't be installed, read or found."""


@dataclass
class Plugin:
    name: str
    path: Path
    version: str = ""
    description: str = ""
    hooks: Dict[str, Any] = field(default_factory=dict)
    mcp_servers: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    source: str = ""

    def dir(self, kind: str) -> Path:
        """skills, commands or output-styles inside the plugin."""
        return self.path / kind

    def contents(self) -> List[str]:
        """What the plugin adds, for listings and the install confirmation."""
        parts = []
        for kind in ("skills", "commands", "agents", "output-styles"):
            directory = self.dir(kind)
            if directory.is_dir():
                names = sorted(p.stem if p.is_file() else p.name for p in directory.iterdir())
                if names:
                    parts.append(f"{kind}: {', '.join(names)}")
        for event, entries in self.hooks.items():
            for entry in entries if isinstance(entries, list) else [entries]:
                command = entry.get("command") if isinstance(entry, dict) else entry
                parts.append(f"hook {event}: {command}")
        for name, server in self.mcp_servers.items():
            target = server.get("command") or server.get("url") if isinstance(server, dict) else ""
            parts.append(f"MCP server {name}: {target}")
        return parts


def github_url(source: str) -> Optional[str]:
    """`owner/repo` (not an existing path) as its GitHub clone URL."""
    if re.fullmatch(r"[A-Za-z0-9][\w.-]*/[\w.-]+", source) and not Path(source).exists():
        return f"https://github.com/{source.removesuffix('.git')}.git"
    return None


def plugins_dir() -> Path:
    from joshu.core.paths import joshu_home

    return joshu_home() / "plugins"


def _expand(value: Any, directory: Path) -> Any:
    """Replace ${PLUGIN_DIR} (and ${CLAUDE_PLUGIN_ROOT}) in strings, lists and mappings."""
    from joshu.core.claude_compat import expand_root

    return expand_root(value, directory)


def has_manifest(directory: Path) -> bool:
    return (directory / MANIFEST).is_file() or (directory / CLAUDE_MANIFEST).is_file()


def _read_claude_plugin(directory: Path) -> Dict[str, Any]:
    """A Claude Code plugin's manifest, hooks and MCP servers, as a Joshu manifest."""
    from joshu.core.claude_compat import read_hooks_json, read_mcp_json

    manifest = directory / CLAUDE_MANIFEST
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise PluginError(f"{manifest}: {e}") from e
    if not isinstance(data, dict):
        raise PluginError(f"{manifest} must be an object")
    hooks_spec = data.get("hooks", "./hooks/hooks.json")
    hooks: Dict[str, Any] = {}
    for spec in hooks_spec if isinstance(hooks_spec, list) else [hooks_spec]:
        if isinstance(spec, str) and (directory / spec).is_file():
            for event, entries in read_hooks_json(directory / spec, directory).items():
                hooks.setdefault(event, []).extend(entries)
        elif isinstance(spec, dict):
            temp = directory / ".joshu-inline-hooks.json"
            temp.write_text(json.dumps({"hooks": spec.get("hooks", spec)}), encoding="utf-8")
            for event, entries in read_hooks_json(temp, directory).items():
                hooks.setdefault(event, []).extend(entries)
            temp.unlink()
    mcp_spec = data.get("mcpServers", "./.mcp.json")
    if isinstance(mcp_spec, dict):
        servers = _expand(mcp_spec, directory)
    elif isinstance(mcp_spec, str) and (directory / mcp_spec).is_file():
        servers = read_mcp_json(directory / mcp_spec, directory)
    else:
        servers = {}
    return {
        "name": data.get("name"),
        "version": data.get("version"),
        "description": data.get("description"),
        "hooks": hooks,
        "mcp_servers": servers,
    }


def read_plugin(directory: Path) -> Plugin:
    """The plugin in `directory` (its manifest checked)."""
    manifest = directory / MANIFEST
    if not manifest.is_file():
        if (directory / CLAUDE_MANIFEST).is_file():
            return _plugin_from(
                directory, _read_claude_plugin(directory), directory / CLAUDE_MANIFEST
            )
        raise PluginError(f"{directory} has no {MANIFEST} or {CLAUDE_MANIFEST.as_posix()}")
    try:
        data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise PluginError(f"{manifest}: {e}") from e
    return _plugin_from(directory, data, manifest)


def _plugin_from(directory: Path, data: Any, manifest: Path) -> Plugin:
    if not isinstance(data, dict):
        raise PluginError(f"{manifest} must be a mapping")
    name = str(data.get("name") or "").strip()
    if not NAME.match(name):
        raise PluginError(
            f"{manifest}: name must be lowercase letters, digits, '.', '-' or '_' (got {name!r})"
        )
    for key in ("hooks", "mcp_servers"):
        if data.get(key) is not None and not isinstance(data[key], dict):
            raise PluginError(f"{manifest}: {key} must be a mapping")
    source = ""
    source_file = directory / SOURCE_FILE
    if source_file.is_file():
        try:
            source = str(json.loads(source_file.read_text(encoding="utf-8")).get("source", ""))
        except ValueError:
            pass
    return Plugin(
        name=name,
        path=directory,
        version=str(data.get("version") or ""),
        description=str(data.get("description") or ""),
        hooks=_expand(data.get("hooks") or {}, directory),
        mcp_servers=_expand(data.get("mcp_servers") or {}, directory),
        enabled=not (directory / DISABLED_FILE).exists(),
        source=source,
    )


def installed_plugins(enabled_only: bool = False) -> List[Plugin]:
    """Installed plugins by name; broken ones are skipped."""
    root = plugins_dir()
    if not root.is_dir():
        return []
    plugins = []
    for directory in sorted(p for p in root.iterdir() if p.is_dir()):
        try:
            plugin = read_plugin(directory)
        except PluginError:
            continue
        if plugin.enabled or not enabled_only:
            plugins.append(plugin)
    return plugins


def plugin_dirs(kind: str) -> List[Path]:
    """`kind` directories (skills, commands, output-styles) of the enabled plugins."""
    return [p.dir(kind) for p in installed_plugins(enabled_only=True) if p.dir(kind).is_dir()]


def plugin_hooks() -> List[tuple]:
    """(plugin name, hooks mapping) of the enabled plugins."""
    return [(p.name, p.hooks) for p in installed_plugins(enabled_only=True) if p.hooks]


def plugin_mcp_servers() -> Dict[str, Dict[str, Any]]:
    """MCP servers declared by the enabled plugins, by server name."""
    servers: Dict[str, Dict[str, Any]] = {}
    for plugin in installed_plugins(enabled_only=True):
        for name, server in plugin.mcp_servers.items():
            if isinstance(server, dict):
                servers.setdefault(name, server)
    return servers


# ------------------------------------------------------------------ install


def is_git_source(source: str) -> bool:
    return (
        bool(re.match(r"^(https?://|git@|ssh://|file://)", source) or source.endswith(".git"))
        and not Path(source).exists()
    ) or github_url(source) is not None


def fetch(source: str, into: Path) -> Path:
    """Copy or clone `source` into `into`; returns the plugin's directory."""
    source = github_url(source) or source
    if is_git_source(source):
        try:
            result = subprocess.run(
                ["git", "clone", "--depth", "1", "--quiet", source, str(into)],
                capture_output=True,
                text=True,
                timeout=300,
            )
        except (OSError, subprocess.SubprocessError) as e:
            raise PluginError(f"git clone failed: {e}") from e
        if result.returncode != 0:
            raise PluginError(f"git clone failed: {(result.stderr or result.stdout).strip()}")
    else:
        path = Path(source).expanduser()
        if not path.is_dir():
            raise PluginError(f"Not a directory or git URL: {source}")
        shutil.copytree(path, into, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    return into


def prepare(source: str) -> tuple:
    """Fetch `source` into a temporary directory: (plugin, temporary dir to clean up)."""
    temp = Path(tempfile.mkdtemp(prefix="joshu-plugin-"))
    try:
        located = _from_marketplace(source)
        plugin = read_plugin(fetch(located or source, temp / "plugin"))
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise
    return plugin, temp


def install(source: str, force: bool = False, prepared: Optional[tuple] = None) -> Plugin:
    """Install the plugin at `source` (a git URL or a directory) into ~/.joshu/plugins."""
    plugin, temp = prepared or prepare(source)
    try:
        target = plugins_dir() / plugin.name
        if target.exists():
            if not force:
                raise PluginError(
                    f"Plugin '{plugin.name}' is already installed (update it, or use --force)"
                )
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(plugin.path, target, ignore=shutil.ignore_patterns(".git"))
        canonical = _marketplace_name(source)
        if canonical is not None:
            resolved = canonical  # name@marketplace, so update fetches the marketplace again
        elif is_git_source(source):
            resolved = source
        else:
            resolved = str(Path(source).expanduser().resolve())
        (target / SOURCE_FILE).write_text(json.dumps({"source": resolved}), encoding="utf-8")
    finally:
        shutil.rmtree(temp, ignore_errors=True)
    return read_plugin(target)


def find(name: str) -> Plugin:
    path = plugins_dir() / name
    if name.startswith(".") or not has_manifest(path):
        raise PluginError(f"No plugin named '{name}' (see `joshu plugin list`)")
    return read_plugin(path)


def remove(name: str) -> None:
    shutil.rmtree(find(name).path)


def update(name: str) -> Plugin:
    """Install the plugin again from where it came from."""
    plugin = find(name)
    if not plugin.source:
        raise PluginError(f"'{name}' doesn't record where it was installed from")
    enabled = plugin.enabled
    marketplace = _split_marketplace(plugin.source)
    if marketplace is not None:
        update_marketplace(marketplace[1])
    install(plugin.source, force=True)
    if not enabled:
        set_enabled(name, False)
    return find(name)


def set_enabled(name: str, enabled: bool) -> None:
    marker = find(name).path / DISABLED_FILE
    if enabled:
        marker.unlink(missing_ok=True)
    else:
        marker.write_text("", encoding="utf-8")


# -------------------------------------------------------------- marketplaces


@dataclass
class Marketplace:
    name: str
    path: Path
    description: str = ""
    plugins: List[Dict[str, Any]] = field(default_factory=list)  # name, description, source
    source: str = ""


def marketplaces_dir() -> Path:
    return plugins_dir() / MARKETPLACES


def read_marketplace(directory: Path) -> Marketplace:
    """A Claude Code marketplace (.claude-plugin/marketplace.json) in `directory`."""
    path = directory / MARKETPLACE_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise PluginError(f"{directory} has no readable {MARKETPLACE_FILE.as_posix()}: {e}") from e
    name = str(data.get("name") or "").strip()
    if not NAME.match(name):
        raise PluginError(f"{path}: invalid marketplace name {name!r}")
    plugins = [
        p
        for p in data.get("plugins") or []
        if isinstance(p, dict) and NAME.match(str(p.get("name", "")))
    ]
    source = ""
    if (directory / SOURCE_FILE).is_file():
        try:
            source = str(
                json.loads((directory / SOURCE_FILE).read_text(encoding="utf-8"))["source"]
            )
        except (ValueError, KeyError):
            pass
    description = (data.get("metadata") or {}).get("description") or data.get("description") or ""
    return Marketplace(name, directory, str(description), plugins, source)


def add_marketplace(source: str) -> Marketplace:
    """Fetch a marketplace (git URL, owner/repo or directory) and remember it."""
    temp = Path(tempfile.mkdtemp(prefix="joshu-marketplace-"))
    try:
        fetched = fetch(source, temp / "marketplace")
        market = read_marketplace(fetched)
        target = marketplaces_dir() / market.name
        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(fetched, target, ignore=shutil.ignore_patterns(".git"))
        recorded = source if is_git_source(source) else str(Path(source).expanduser().resolve())
        (target / SOURCE_FILE).write_text(json.dumps({"source": recorded}), encoding="utf-8")
    finally:
        shutil.rmtree(temp, ignore_errors=True)
    return read_marketplace(target)


def list_marketplaces() -> List[Marketplace]:
    root = marketplaces_dir()
    if not root.is_dir():
        return []
    markets = []
    for directory in sorted(p for p in root.iterdir() if p.is_dir()):
        try:
            markets.append(read_marketplace(directory))
        except PluginError:
            continue
    return markets


def find_marketplace(name: str) -> Marketplace:
    path = marketplaces_dir() / name
    if not (path / MARKETPLACE_FILE).is_file():
        raise PluginError(f"No marketplace named '{name}' (see `joshu plugin marketplace list`)")
    return read_marketplace(path)


def remove_marketplace(name: str) -> None:
    shutil.rmtree(find_marketplace(name).path)


def update_marketplace(name: str) -> Marketplace:
    market = find_marketplace(name)
    if not market.source:
        raise PluginError(f"'{name}' doesn't record where it was added from")
    return add_marketplace(market.source)


def _split_marketplace(source: str) -> Optional[tuple]:
    """`plugin@marketplace` -> (plugin, marketplace), or None."""
    if is_git_source(source) or Path(source).exists():
        return None
    match = re.fullmatch(r"([a-z0-9][a-z0-9._-]*)@([a-z0-9][a-z0-9._-]*)", source)
    return (match.group(1), match.group(2)) if match else None


def _marketplace_name(source: str) -> Optional[str]:
    """`plugin@marketplace` for a marketplace source (also a plain plugin name), else None."""
    split = _split_marketplace(source)
    if split is not None:
        return f"{split[0]}@{split[1]}"
    if not NAME.match(source) or Path(source).exists():
        return None
    found = [m for m in list_marketplaces() if any(p["name"] == source for p in m.plugins)]
    return f"{source}@{found[0].name}" if len(found) == 1 else None


def _from_marketplace(source: str) -> Optional[str]:
    """
    Where `plugin@marketplace` (or a plain plugin name found in exactly one
    added marketplace) is: a directory or a git URL. None for other sources.
    """
    split = _split_marketplace(source)
    if split is None:
        if not NAME.match(source) or Path(source).exists():
            return None
        found = [m for m in list_marketplaces() if any(p["name"] == source for p in m.plugins)]
        if len(found) != 1:
            return None
        split = (source, found[0].name)
    name, market_name = split
    market = find_marketplace(market_name)
    entry = next((p for p in market.plugins if p["name"] == name), None)
    if entry is None:
        names = ", ".join(p["name"] for p in market.plugins) or "none"
        raise PluginError(f"'{market_name}' has no plugin '{name}' (it has: {names})")
    where = entry.get("source", "./")
    if isinstance(where, dict):
        kind = where.get("source")
        if kind == "github" and where.get("repo"):
            return f"https://github.com/{where['repo']}.git"
        if where.get("url"):
            return str(where["url"])
        raise PluginError(f"{name}@{market_name}: unsupported source {where!r}")
    where = str(where)
    if is_git_source(where):
        return github_url(where) or where
    directory = (market.path / where).resolve()
    if not directory.is_relative_to(market.path.resolve()) or not directory.is_dir():
        raise PluginError(
            f"{name}@{market_name}: source {where!r} isn't a directory of the marketplace"
        )
    return str(directory)
