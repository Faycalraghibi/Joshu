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
        for kind in ("skills", "commands", "output-styles"):
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


def plugins_dir() -> Path:
    from joshu.core.paths import joshu_home

    return joshu_home() / "plugins"


def _expand(value: Any, directory: Path) -> Any:
    """Replace ${PLUGIN_DIR} in strings, lists and mappings."""
    if isinstance(value, str):
        return value.replace("${PLUGIN_DIR}", str(directory))
    if isinstance(value, list):
        return [_expand(v, directory) for v in value]
    if isinstance(value, dict):
        return {k: _expand(v, directory) for k, v in value.items()}
    return value


def read_plugin(directory: Path) -> Plugin:
    """The plugin in `directory` (its manifest checked)."""
    manifest = directory / MANIFEST
    if not manifest.is_file():
        raise PluginError(f"{directory} has no {MANIFEST}")
    try:
        data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise PluginError(f"{manifest}: {e}") from e
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
        bool(re.match(r"^(https?://|git@|ssh://)", source) or source.endswith(".git"))
        and not Path(source).exists()
    )


def fetch(source: str, into: Path) -> Path:
    """Copy or clone `source` into `into`; returns the plugin's directory."""
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
        plugin = read_plugin(fetch(source, temp / "plugin"))
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
        resolved = source if is_git_source(source) else str(Path(source).expanduser().resolve())
        (target / SOURCE_FILE).write_text(json.dumps({"source": resolved}), encoding="utf-8")
    finally:
        shutil.rmtree(temp, ignore_errors=True)
    return read_plugin(target)


def find(name: str) -> Plugin:
    path = plugins_dir() / name
    if not (path / MANIFEST).is_file():
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
