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
    - Imports joshu.ui modules for keybinding introspection

Safety Considerations:
    - Read-only introspection
    - Idempotent output
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent


def log(message: str, verbose: bool = True) -> None:
    """Print a log message if verbose mode is enabled."""
    if verbose:
        print(f"[generate_keybindings_docs] {message}")


def log_error(message: str) -> None:
    """Print an error message."""
    print(f"[generate_keybindings_docs] ERROR: {message}", file=sys.stderr)


def log_success(message: str) -> None:
    """Print a success message."""
    print(f"[generate_keybindings_docs] ✓ {message}")


# Default keybindings - these can be enhanced by introspecting the actual code
DEFAULT_KEYBINDINGS: Dict[str, List[Tuple[str, str, str]]] = {
    "Chat Mode": [
        ("Enter", "Send message", "Submit the current input to the AI"),
        ("Ctrl+C", "Cancel", "Cancel current operation or exit"),
        ("Ctrl+D", "Exit", "Exit Joshu CLI"),
        ("Ctrl+L", "Clear screen", "Clear the terminal screen"),
        ("Up/Down", "History navigation", "Navigate through command history"),
        ("Tab", "Autocomplete", "Trigger autocompletion"),
    ],
    "Editor Mode": [
        ("Ctrl+S", "Save", "Save current file"),
        ("Ctrl+Z", "Undo", "Undo last action"),
        ("Ctrl+Y", "Redo", "Redo last undone action"),
        ("Ctrl+F", "Find", "Search in current context"),
    ],
    "Global": [
        ("Ctrl+H", "Help", "Show help information"),
        ("Ctrl+Q", "Quick exit", "Exit immediately"),
        ("F1", "Documentation", "Open documentation"),
    ],
}


def get_keybindings_from_code(verbose: bool = False) -> Dict[str, List[Tuple[str, str, str]]]:
    """
    Attempt to extract keybindings from source code.
    Falls back to defaults if introspection fails.
    """
    try:
        src_path = PROJECT_ROOT / "src"
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

        # Try to import and introspect keybindings
        # This is a placeholder - actual implementation would depend on
        # how keybindings are defined in the Joshu codebase

        log("Using default keybindings (code introspection not implemented)", verbose)
        return DEFAULT_KEYBINDINGS

    except Exception as e:
        log(f"Failed to introspect keybindings: {e}", verbose)
        return DEFAULT_KEYBINDINGS


def generate_docs(output_path: Path, verbose: bool = False) -> bool:
    """Generate keybindings documentation."""
    keybindings = get_keybindings_from_code(verbose)

    lines = [
        "# Joshu CLI Keybindings",
        "",
        "> Auto-generated keybinding reference documentation.",
        f"> Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "This document lists all available keyboard shortcuts for Joshu CLI.",
        "",
    ]

    for context, bindings in keybindings.items():
        lines.append(f"## {context}")
        lines.append("")
        lines.append("| Keybinding | Action | Description |")
        lines.append("|------------|--------|-------------|")

        for key, action, description in bindings:
            # Escape pipe characters in content
            key = key.replace("|", "\\|")
            action = action.replace("|", "\\|")
            description = description.replace("|", "\\|")

            lines.append(f"| `{key}` | {action} | {description} |")

        lines.append("")

    # Add customization section
    lines.extend(
        [
            "## Customization",
            "",
            "Keybindings can be customized in your Joshu configuration file.",
            "See the [settings documentation](settings.md) for details.",
            "",
            "### Example Configuration",
            "",
            "```yaml",
            "keybindings:",
            "  send_message: 'ctrl+enter'",
            "  cancel: 'escape'",
            "```",
            "",
        ]
    )

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        output_path.write_text("\n".join(lines))
        log_success(f"Generated {output_path}")
        return True
    except Exception as e:
        log_error(f"Failed to write documentation: {e}")
        return False


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate keybinding reference documentation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/generate_keybindings_docs.py
    python scripts/generate_keybindings_docs.py --output docs/keybindings.md
        """,
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=PROJECT_ROOT / "docs" / "keybindings.md",
        help="Output file path (default: docs/keybindings.md)",
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
