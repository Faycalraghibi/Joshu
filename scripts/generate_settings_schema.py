#!/usr/bin/env python3
"""
generate_settings_schema.py - Generate JSON schema from Pydantic config models.

Purpose:
    Exports JSON schema from Joshu's Pydantic configuration models
    for IDE autocompletion and validation.

Inputs:
    --output PATH     Output file path (default: docs/settings-schema.json)
    --verbose         Enable verbose output

Outputs:
    - JSON schema file

Side Effects:
    - Imports joshu.core.config module

Safety Considerations:
    - Read-only introspection of config models
    - Idempotent output
"""

import argparse
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent


def log(message: str, verbose: bool = True) -> None:
    """Print a log message if verbose mode is enabled."""
    if verbose:
        print(f"[generate_settings_schema] {message}")


def log_error(message: str) -> None:
    """Print an error message."""
    print(f"[generate_settings_schema] ERROR: {message}", file=sys.stderr)


def log_success(message: str) -> None:
    """Print a success message."""
    print(f"[generate_settings_schema] ✓ {message}")


def get_config_models() -> list:
    """Import and return Pydantic config models."""
    try:
        # Add src to path for import
        src_path = PROJECT_ROOT / "src"
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

        from joshu.core.config import Config

        return [("Config", Config)]
    except ImportError as e:
        log_error(f"Failed to import config models: {e}")
        return []


def generate_schema(output_path: Path, verbose: bool = False) -> bool:
    """Generate JSON schema from config models."""
    models = get_config_models()

    if not models:
        log_error("No config models found")
        return False

    schemas = {}

    for name, model in models:
        log(f"Processing model: {name}", verbose)
        try:
            schema = model.model_json_schema()
            schemas[name] = schema
        except Exception as e:
            log_error(f"Failed to generate schema for {name}: {e}")
            return False

    # Create combined schema
    combined_schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "Joshu CLI Settings",
        "description": "Configuration schema for Joshu CLI",
        "definitions": schemas,
    }

    # If there's only one model, make it the root
    if len(schemas) == 1:
        root_name = list(schemas.keys())[0]
        combined_schema.update(schemas[root_name])
        del combined_schema["definitions"]

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(output_path, "w") as f:
            json.dump(combined_schema, f, indent=2)
        log_success(f"Generated {output_path}")
        return True
    except Exception as e:
        log_error(f"Failed to write schema: {e}")
        return False


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate JSON schema from Pydantic config models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/generate_settings_schema.py
    python scripts/generate_settings_schema.py --output docs/settings-schema.json
        """,
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=PROJECT_ROOT / "docs" / "settings-schema.json",
        help="Output file path (default: docs/settings-schema.json)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    output = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output

    if not generate_schema(output, args.verbose):
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
