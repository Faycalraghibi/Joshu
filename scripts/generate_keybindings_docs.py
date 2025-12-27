#!/usr/bin/env python3
"""
generate_keybindings_docs.py - Generate keybinding reference documentation.

Purpose:
    Parses keybinding definitions from CLI/UI code and generates
    Markdown documentation with binding tables.

Inputs:
    --output PATH     Output file path (default: docs/keybindings.md)
    --verbose         Enable verbose output

Outputs:
    - Markdown documentation file with keybinding tables

Side Effects:
    - Reads source code for keybinding introspection

Safety Considerations:
    - Read-only introspection
    - Idempotent output
"""

import argparse
import ast
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, NamedTuple

SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent


def log(message: str, verbose: bool = True) -> None:
    if verbose:
        print(f"[keybindings] {message}")


def log_error(message: str) -> None:
    print(f"[keybindings] ERROR: {message}", file=sys.stderr)


def log_success(message: str) -> None:
    print(f"[keybindings] ✓ {message}")


class KeyBinding(NamedTuple):
    """Represents a single keybinding."""

    key: str
    action: str
    description: str
    context: str  # "Global", "NORMAL mode", etc.


# =============================================================================
# Key name formatting
# =============================================================================

KEY_DISPLAY_MAP = {
    "c-": "Ctrl+",
    "s-": "Shift+",
    "m-": "Alt+",
    "escape": "Escape",
    "enter": "Enter",
    "tab": "Tab",
    "backspace": "Backspace",
    "delete": "Delete",
    "up": "↑",
    "down": "↓",
    "left": "←",
    "right": "→",
}


def format_key(key: str) -> str:
    """Format a key string for display."""
    result = key

    # Convert modifiers
    if result.startswith("c-"):
        result = "Ctrl+" + result[2:].upper()
    elif result.startswith("s-"):
        result = "Shift+" + result[2:].upper()
    elif result.startswith("m-"):
        result = "Alt+" + result[2:].upper()
    else:
        # Single key
        result = result.upper() if len(result) == 1 else result.capitalize()

    return result


def extract_action_from_docstring(docstring: str) -> str:
    """Extract action name from docstring."""
    if not docstring:
        return "Unknown action"

    # Remove quotes and clean up
    doc = docstring.strip().strip("\"'")

    # Extract the main action (usually before "for" or first sentence)
    if " for " in doc.lower():
        parts = doc.split(" for ", 1)
        return parts[1].strip() if len(parts) > 1 else doc

    return doc


# =============================================================================
# Source Code Introspection
# =============================================================================


def parse_keybindings_file(file_path: Path, verbose: bool = False) -> List[KeyBinding]:
    """Parse keybindings from a Python source file using AST."""
    bindings = []

    if not file_path.exists():
        log(f"File not found: {file_path}", verbose)
        return bindings

    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except Exception as e:
        log(f"Failed to parse {file_path}: {e}", verbose)
        return bindings

    # Find decorated functions
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for decorator in node.decorator_list:
                key = None
                context = "Global"

                # Handle @kb.add("key") or @kb.add("key", filter=...)
                if isinstance(decorator, ast.Call):
                    if isinstance(decorator.func, ast.Attribute):
                        if decorator.func.attr == "add":
                            # Get the key argument
                            if decorator.args:
                                arg = decorator.args[0]
                                if isinstance(arg, ast.Constant):
                                    key = arg.value

                            # Check for filter (context)
                            for keyword in decorator.keywords:
                                if keyword.arg == "filter":
                                    # Try to extract context from filter
                                    if isinstance(keyword.value, ast.Call):
                                        # Condition(lambda: ...)
                                        context = "NORMAL mode (Vim)"

                if key:
                    # Get docstring
                    docstring = ast.get_docstring(node) or ""
                    action = extract_action_from_docstring(docstring)

                    bindings.append(
                        KeyBinding(
                            key=format_key(key),
                            action=action.split("'")[0].strip() if "'" in action else action,
                            description=docstring.strip().strip("\"'"),
                            context=context,
                        )
                    )
                    log(f"Found: {key!s} -> {action}", verbose)

    return bindings


def parse_keybindings_regex(file_path: Path, verbose: bool = False) -> List[KeyBinding]:
    """Parse keybindings using regex as fallback."""
    bindings = []

    if not file_path.exists():
        return bindings

    source = file_path.read_text(encoding="utf-8")

    # Pattern: @kb.add("key") or @kb.add("key", filter=...)
    # Followed by def func and docstring
    pattern = re.compile(
        r'@kb\.add\(["\']([^"\']+)["\'](?:,\s*filter=[^)]+)?\)\s*'
        r"def\s+\w+\([^)]*\):\s*"
        r'(?:"""([^"]+)"""|\'\'\'([^\']+)\'\'\')?',
        re.MULTILINE | re.DOTALL,
    )

    for match in pattern.finditer(source):
        key = match.group(1)
        docstring = match.group(2) or match.group(3) or ""

        # Check if it's a vim-filtered binding
        context = "Global"
        if "filter=" in source[max(0, match.start() - 50) : match.start()]:
            context = "NORMAL mode (Vim)"

        bindings.append(
            KeyBinding(
                key=format_key(key),
                action=extract_action_from_docstring(docstring),
                description=docstring.strip(),
                context=context,
            )
        )

    return bindings


def get_keybindings(verbose: bool = False) -> Dict[str, List[KeyBinding]]:
    """Get all keybindings from the codebase."""
    keybindings_file = PROJECT_ROOT / "src" / "joshu" / "ui" / "interactive" / "keybindings.py"

    # Try AST parsing first
    bindings = parse_keybindings_file(keybindings_file, verbose)

    # Fall back to regex if AST fails
    if not bindings:
        log("AST parsing failed, trying regex...", verbose)
        bindings = parse_keybindings_regex(keybindings_file, verbose)

    if not bindings:
        log("No bindings found, using defaults", verbose)
        return get_default_keybindings()

    # Group by context
    grouped: Dict[str, List[KeyBinding]] = {}
    for binding in bindings:
        if binding.context not in grouped:
            grouped[binding.context] = []
        grouped[binding.context].append(binding)

    log(f"Found {len(bindings)} keybindings in {len(grouped)} contexts", verbose)
    return grouped


def get_default_keybindings() -> Dict[str, List[KeyBinding]]:
    """Return default keybindings as fallback."""
    return {
        "Global": [
            KeyBinding("Ctrl+C", "Cancel", "Cancel current operation or exit", "Global"),
            KeyBinding("Ctrl+D", "Exit", "Exit Joshu CLI", "Global"),
            KeyBinding("Ctrl+L", "Clear screen", "Clear the terminal screen", "Global"),
            KeyBinding("Ctrl+R", "Reverse search", "Search command history", "Global"),
            KeyBinding("Ctrl+T", "Toggle suggestions", "Toggle command suggestions", "Global"),
            KeyBinding("Enter", "Send message", "Submit the current input", "Global"),
        ],
        "NORMAL mode (Vim)": [
            KeyBinding("H", "Move left", "Move cursor left", "NORMAL mode (Vim)"),
            KeyBinding("J", "Move down", "Navigate history down", "NORMAL mode (Vim)"),
            KeyBinding("K", "Move up", "Navigate history up", "NORMAL mode (Vim)"),
            KeyBinding("L", "Move right", "Move cursor right", "NORMAL mode (Vim)"),
            KeyBinding("W", "Word forward", "Move to next word", "NORMAL mode (Vim)"),
            KeyBinding("B", "Word backward", "Move to previous word", "NORMAL mode (Vim)"),
            KeyBinding("I", "Insert mode", "Enter INSERT mode", "NORMAL mode (Vim)"),
            KeyBinding("A", "Append", "Append after cursor", "NORMAL mode (Vim)"),
            KeyBinding("D", "Delete", "Start delete command", "NORMAL mode (Vim)"),
            KeyBinding("Y", "Yank", "Start yank command", "NORMAL mode (Vim)"),
            KeyBinding("P", "Paste", "Paste from clipboard", "NORMAL mode (Vim)"),
            KeyBinding(":", "Command mode", "Enter command mode", "NORMAL mode (Vim)"),
            KeyBinding("Escape", "Normal mode", "Switch to NORMAL mode", "Global"),
        ],
    }


# =============================================================================
# Documentation Generation
# =============================================================================


def generate_docs(output_path: Path, verbose: bool = False) -> bool:
    """Generate keybindings documentation."""
    keybindings = get_keybindings(verbose)

    lines = [
        "# Joshu CLI Keybindings",
        "",
        "> **Auto-generated** from source code introspection.",
        f"> Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "This document lists all keyboard shortcuts available in Joshu CLI.",
        "",
        "## Quick Reference",
        "",
        "| Key | Action |",
        "|-----|--------|",
        "| `Ctrl+C` | Cancel/Exit |",
        "| `Ctrl+D` | Exit (empty line) |",
        "| `Ctrl+L` | Clear screen |",
        "| `Ctrl+R` | Search history |",
        "| `Escape` | Switch to NORMAL mode |",
        "",
    ]

    # Generate sections for each context
    for context, bindings in keybindings.items():
        lines.append(f"## {context}")
        lines.append("")
        lines.append("| Keybinding | Action | Description |")
        lines.append("|------------|--------|-------------|")

        for binding in bindings:
            key = binding.key.replace("|", "\\|")
            action = binding.action.replace("|", "\\|")
            desc = binding.description.replace("|", "\\|")
            lines.append(f"| `{key}` | {action} | {desc} |")

        lines.append("")

    # Add customization section
    lines.extend(
        [
            "## Customization",
            "",
            "Keybindings can be customized in your configuration file:",
            "",
            "```yaml",
            "# ~/.joshu/config.yaml",
            "keybindings:",
            "  send_message: 'ctrl+enter'",
            "  cancel: 'escape'",
            "  clear_screen: 'ctrl+l'",
            "```",
            "",
            "## Vim Mode",
            "",
            "Joshu supports Vim-style navigation. Press `Escape` to enter NORMAL mode,",
            "then use standard Vim keys (`h`, `j`, `k`, `l`, `w`, `b`, `i`, `a`, etc.).",
            "",
            "To exit Vim mode, press `i` or `a` to return to INSERT mode.",
            "",
        ]
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        output_path.write_text("\n".join(lines))
        log_success(f"Generated {output_path}")
        return True
    except Exception as e:
        log_error(f"Failed to write documentation: {e}")
        return False


# =============================================================================
# Main
# =============================================================================


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate keybinding reference documentation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Introspects keybindings from:
    src/joshu/ui/interactive/keybindings.py

Examples:
    python scripts/generate_keybindings_docs.py
    python scripts/generate_keybindings_docs.py --verbose
        """,
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=PROJECT_ROOT / "docs" / "keybindings.md",
        help="Output file path",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output

    if not generate_docs(output, args.verbose):
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
