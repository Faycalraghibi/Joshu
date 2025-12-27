#!/usr/bin/env python3
"""
generate_settings_docs.py - Generate human-readable settings documentation.

Purpose:
    Creates Markdown documentation from Pydantic config models,
    including field descriptions, types, and default values.

Inputs:
    --output PATH     Output file path (default: docs/settings.md)
    --verbose         Enable verbose output

Outputs:
    - Markdown documentation file

Side Effects:
    - Imports joshu.core.config module

Safety Considerations:
    - Read-only introspection of config models
    - Idempotent output
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent


def log(message: str, verbose: bool = True) -> None:
    """Print a log message if verbose mode is enabled."""
    if verbose:
        print(f"[generate_settings_docs] {message}")


def log_error(message: str) -> None:
    """Print an error message."""
    print(f"[generate_settings_docs] ERROR: {message}", file=sys.stderr)


def log_success(message: str) -> None:
    """Print a success message."""
    print(f"[generate_settings_docs] ✓ {message}")


def get_config_model():
    """Import and return the main Config model."""
    try:
        src_path = PROJECT_ROOT / "src"
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

        from joshu.core.config import Config

        return Config
    except ImportError as e:
        log_error(f"Failed to import Config: {e}")
        return None


def format_type(type_hint: Any) -> str:
    """Format a type hint for documentation."""
    if hasattr(type_hint, "__origin__"):
        origin = type_hint.__origin__
        args = getattr(type_hint, "__args__", ())

        if origin is list:
            inner = format_type(args[0]) if args else "Any"
            return f"list[{inner}]"
        elif origin is dict:
            key = format_type(args[0]) if len(args) > 0 else "Any"
            val = format_type(args[1]) if len(args) > 1 else "Any"
            return f"dict[{key}, {val}]"
        elif origin is type(None):
            return "None"
        else:
            return str(origin.__name__)

    if hasattr(type_hint, "__name__"):
        return type_hint.__name__

    return str(type_hint)


def format_default(value: Any) -> str:
    """Format a default value for documentation."""
    if value is None:
        return "`None`"
    if isinstance(value, str):
        return f'`"{value}"`'
    if isinstance(value, bool):
        return f"`{value}`"
    if isinstance(value, (int, float)):
        return f"`{value}`"
    if isinstance(value, list):
        if not value:
            return "`[]`"
        return f"`{value}`"
    if isinstance(value, dict):
        if not value:
            return "`{}`"
        return "`{...}`"
    return f"`{value}`"


def generate_model_docs(model_class, verbose: bool = False) -> str:
    """Generate documentation for a single Pydantic model."""
    lines = []

    model_name = model_class.__name__
    model_doc = model_class.__doc__ or "Configuration settings."

    lines.append(f"## {model_name}")
    lines.append("")
    lines.append(model_doc.strip())
    lines.append("")

    # Get field information
    try:
        fields = model_class.model_fields
    except AttributeError:
        log_error(f"Model {model_name} does not have model_fields")
        return "\n".join(lines)

    if not fields:
        lines.append("*No configuration fields defined.*")
        return "\n".join(lines)

    # Create table
    lines.append("| Setting | Type | Default | Description |")
    lines.append("|---------|------|---------|-------------|")

    for field_name, field_info in fields.items():
        # Get type
        field_type = "Any"
        if hasattr(field_info, "annotation") and field_info.annotation:
            field_type = format_type(field_info.annotation)

        # Get default
        default = "Required"
        if hasattr(field_info, "default") and field_info.default is not None:
            default = format_default(field_info.default)
        elif hasattr(field_info, "default_factory") and field_info.default_factory:
            default = "*factory*"

        # Get description
        description = ""
        if hasattr(field_info, "description") and field_info.description:
            description = field_info.description

        # Clean up for table
        field_type = field_type.replace("|", "\\|")
        description = description.replace("|", "\\|").replace("\n", " ")

        lines.append(f"| `{field_name}` | {field_type} | {default} | {description} |")

    return "\n".join(lines)


def generate_docs(output_path: Path, verbose: bool = False) -> bool:
    """Generate complete settings documentation."""
    model = get_config_model()

    if not model:
        return False

    lines = [
        "# Joshu CLI Settings",
        "",
        "> Auto-generated documentation from Pydantic configuration models.",
        f"> Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "This document describes all available configuration options for Joshu CLI.",
        "",
    ]

    # Generate documentation for the model
    model_docs = generate_model_docs(model, verbose)
    lines.append(model_docs)

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
        description="Generate human-readable settings documentation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/generate_settings_docs.py
    python scripts/generate_settings_docs.py --output docs/settings.md
        """,
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=PROJECT_ROOT / "docs" / "settings.md",
        help="Output file path (default: docs/settings.md)",
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
