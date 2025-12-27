#!/usr/bin/env python3
"""
telemetry.py - Telemetry configuration utilities.

Purpose:
    Provides configuration and initialization for telemetry collection
    in the Joshu CLI. Telemetry is opt-in and disabled by default.

Inputs:
    --enable          Enable telemetry
    --disable         Disable telemetry
    --status          Show current telemetry status
    --verbose         Enable verbose output

Outputs:
    - Telemetry configuration status

Side Effects:
    - Updates telemetry configuration in user settings

Safety Considerations:
    - Telemetry is disabled by default
    - User must explicitly opt-in
    - No data is collected without consent
"""

import argparse
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent

# Default telemetry settings path
TELEMETRY_CONFIG_PATH = Path.home() / ".joshu" / "telemetry.json"


def log(message: str, verbose: bool = True) -> None:
    """Print a log message if verbose mode is enabled."""
    if verbose:
        print(f"[telemetry] {message}")


def log_success(message: str) -> None:
    """Print a success message."""
    print(f"[telemetry] ✓ {message}")


def log_warning(message: str) -> None:
    """Print a warning message."""
    print(f"[telemetry] ⚠ {message}")


def get_config() -> dict:
    """Load telemetry configuration."""
    if not TELEMETRY_CONFIG_PATH.exists():
        return {
            "enabled": False,
            "endpoint": None,
            "service_name": "joshu-cli",
        }

    try:
        return json.loads(TELEMETRY_CONFIG_PATH.read_text())
    except Exception:
        return {"enabled": False}


def save_config(config: dict) -> bool:
    """Save telemetry configuration."""
    try:
        TELEMETRY_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        TELEMETRY_CONFIG_PATH.write_text(json.dumps(config, indent=2))
        return True
    except Exception as e:
        print(f"Failed to save config: {e}", file=sys.stderr)
        return False


def show_status(verbose: bool = False) -> None:
    """Display current telemetry status."""
    config = get_config()

    print("=" * 50)
    print("Joshu Telemetry Configuration")
    print("=" * 50)
    print(f"  Enabled:      {config.get('enabled', False)}")
    print(f"  Service Name: {config.get('service_name', 'joshu-cli')}")
    print(f"  Endpoint:     {config.get('endpoint', 'Not configured')}")
    print(f"  Config Path:  {TELEMETRY_CONFIG_PATH}")
    print("=" * 50)

    if not config.get("enabled"):
        print("\nTelemetry is currently DISABLED.")
        print("To enable: python scripts/telemetry.py --enable")
    else:
        print("\nTelemetry is currently ENABLED.")
        print("To disable: python scripts/telemetry.py --disable")


def enable_telemetry(
    endpoint: str | None = None,
    verbose: bool = False,
) -> bool:
    """Enable telemetry collection."""
    config = get_config()
    config["enabled"] = True

    if endpoint:
        config["endpoint"] = endpoint

    if save_config(config):
        log_success("Telemetry enabled")
        return True
    return False


def disable_telemetry(verbose: bool = False) -> bool:
    """Disable telemetry collection."""
    config = get_config()
    config["enabled"] = False

    if save_config(config):
        log_success("Telemetry disabled")
        return True
    return False


def is_telemetry_enabled() -> bool:
    """Check if telemetry is enabled."""
    config = get_config()
    return config.get("enabled", False)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Telemetry configuration for Joshu CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/telemetry.py --status
    python scripts/telemetry.py --enable
    python scripts/telemetry.py --disable
        """,
    )
    parser.add_argument(
        "--enable",
        action="store_true",
        help="Enable telemetry collection",
    )
    parser.add_argument(
        "--disable",
        action="store_true",
        help="Disable telemetry collection",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current telemetry status",
    )
    parser.add_argument(
        "--endpoint",
        help="OTLP endpoint URL (for --enable)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    # Default to showing status
    if not any([args.enable, args.disable, args.status]):
        args.status = True

    if args.enable and args.disable:
        print("Cannot both enable and disable telemetry", file=sys.stderr)
        return 1

    if args.enable:
        return 0 if enable_telemetry(args.endpoint, args.verbose) else 1

    if args.disable:
        return 0 if disable_telemetry(args.verbose) else 1

    if args.status:
        show_status(args.verbose)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
