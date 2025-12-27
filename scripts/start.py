#!/usr/bin/env python3
"""
start.py - CLI launcher with sandbox detection and integration.

Purpose:
    Launches Joshu CLI either directly or inside a sandboxed container
    environment based on configuration and available tools.

Inputs:
    --sandbox         Force sandbox mode
    --no-sandbox      Force normal mode (skip sandbox)
    --engine          Container engine (docker|podman|auto)
    --tag             Sandbox image tag
    -- [ARGS]         Arguments to pass to joshu

Outputs:
    - Launches CLI in appropriate mode

Side Effects:
    - May start container if sandbox mode enabled

Safety Considerations:
    - Gracefully falls back to normal mode if no container runtime
    - Clear messaging about which mode is active
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent


def log(message: str) -> None:
    """Print a log message."""
    print(f"[start] {message}")


def log_error(message: str) -> None:
    """Print an error message."""
    print(f"[start] ERROR: {message}", file=sys.stderr)


def log_success(message: str) -> None:
    """Print a success message."""
    print(f"[start] ✓ {message}")


# =============================================================================
# Sandbox Detection
# =============================================================================


def get_sandbox_command() -> Optional[str]:
    """
    Detect available sandbox command.

    Returns:
        "docker" if Docker is available and running
        "podman" if Podman is available
        None if no sandbox tool available
    """
    for engine in ["docker", "podman"]:
        if shutil.which(engine):
            # Quick check if engine is responsive
            try:
                result = subprocess.run(
                    [engine, "version"],
                    capture_output=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    return engine
            except Exception:
                continue
    return None


def check_sandbox_image(engine: str, tag: str = "latest") -> bool:
    """Check if sandbox image exists."""
    image = f"joshu-sandbox:{tag}"
    try:
        result = subprocess.run(
            [engine, "image", "inspect", image],
            capture_output=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def get_sandbox_mode_from_config() -> Optional[str]:
    """
    Get sandbox mode from configuration.

    Returns:
        "auto" - auto-detect based on availability
        "enabled" - force sandbox mode
        "disabled" - force normal mode
        None - no configuration found
    """
    config_file = Path.home() / ".joshu" / "config.yaml"

    if not config_file.exists():
        return None

    try:
        import yaml

        config = yaml.safe_load(config_file.read_text())
        sandbox_config = config.get("sandbox", {})
        enabled = sandbox_config.get("enabled", "auto")

        if enabled is True:
            return "enabled"
        elif enabled is False:
            return "disabled"
        else:
            return str(enabled)
    except Exception:
        return None


# =============================================================================
# CLI Launch Modes
# =============================================================================


def launch_normal(args: list, verbose: bool = False) -> int:
    """Launch CLI in normal mode (direct execution)."""
    if verbose:
        log("Launching in normal mode")

    # Try to find joshu entry point
    joshu_cmd = shutil.which("joshu")

    if joshu_cmd:
        cmd = [joshu_cmd] + args
    else:
        # Fall back to module execution
        cmd = [sys.executable, "-m", "joshu"] + args

    if verbose:
        log(f"Command: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd)
        return result.returncode
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        log_error(f"Failed to launch: {e}")
        return 1


def launch_sandbox(
    engine: str,
    tag: str,
    args: list,
    mount_cwd: bool = True,
    verbose: bool = False,
) -> int:
    """Launch CLI in sandbox mode (container execution)."""
    if verbose:
        log(f"Launching in sandbox mode ({engine})")

    image = f"joshu-sandbox:{tag}"

    # Build container run command
    cmd = [engine, "run", "-it", "--rm"]

    # Mount current directory
    if mount_cwd:
        cwd = Path.cwd().resolve()
        cmd.extend(["-v", f"{cwd}:/workspace"])
        cmd.extend(["-w", "/workspace"])

    # Add image
    cmd.append(image)

    # Add user arguments
    if args:
        cmd.extend(args)

    if verbose:
        log(f"Command: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd)
        return result.returncode
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        log_error(f"Failed to launch sandbox: {e}")
        return 1


# =============================================================================
# Main
# =============================================================================


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Joshu CLI Launcher with Sandbox Support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
    Auto (default)  Use sandbox if available, otherwise normal
    Sandbox         Force container-based execution
    Normal          Force direct execution

Examples:
    python scripts/start.py                     # Auto-detect mode
    python scripts/start.py --sandbox           # Force sandbox
    python scripts/start.py --no-sandbox        # Force normal
    python scripts/start.py -- --help           # Pass args to joshu
    python scripts/start.py -- chat "Hello"    # Chat in sandbox
        """,
    )

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--sandbox",
        action="store_true",
        help="Force sandbox mode (container execution)",
    )
    mode_group.add_argument(
        "--no-sandbox",
        action="store_true",
        help="Force normal mode (direct execution)",
    )

    parser.add_argument(
        "--engine",
        choices=["docker", "podman", "auto"],
        default="auto",
        help="Container engine (default: auto-detect)",
    )
    parser.add_argument(
        "--tag",
        default="latest",
        help="Sandbox image tag (default: latest)",
    )
    parser.add_argument(
        "--no-mount",
        action="store_true",
        help="Don't mount current directory in sandbox",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "args",
        nargs="*",
        help="Arguments to pass to joshu",
    )

    args = parser.parse_args()

    # Determine mode
    if args.no_sandbox:
        # Force normal mode
        log("Mode: Normal (forced)")
        return launch_normal(args.args, args.verbose)

    if args.sandbox:
        # Force sandbox mode
        engine = args.engine
        if engine == "auto":
            engine = get_sandbox_command()

        if not engine:
            log_error("Sandbox mode requested but no container engine found")
            log_error("Install Docker or Podman to use sandbox mode")
            return 1

        if not check_sandbox_image(engine, args.tag):
            log_error(f"Sandbox image not found: joshu-sandbox:{args.tag}")
            log_error("Run 'python scripts/build_sandbox.py' first")
            return 1

        log(f"Mode: Sandbox ({engine})")
        return launch_sandbox(
            engine=engine,
            tag=args.tag,
            args=args.args,
            mount_cwd=not args.no_mount,
            verbose=args.verbose,
        )

    # Auto mode - check config first, then availability
    config_mode = get_sandbox_mode_from_config()

    if config_mode == "disabled":
        log("Mode: Normal (from config)")
        return launch_normal(args.args, args.verbose)

    if config_mode == "enabled":
        engine = get_sandbox_command()
        if engine and check_sandbox_image(engine, args.tag):
            log(f"Mode: Sandbox ({engine}, from config)")
            return launch_sandbox(
                engine=engine,
                tag=args.tag,
                args=args.args,
                mount_cwd=not args.no_mount,
                verbose=args.verbose,
            )
        else:
            log_error("Sandbox enabled in config but not available")
            log("Falling back to normal mode")

    # Auto-detect: try sandbox first, fall back to normal
    engine = get_sandbox_command()
    if engine and check_sandbox_image(engine, args.tag):
        log(f"Mode: Sandbox ({engine}, auto-detected)")
        return launch_sandbox(
            engine=engine,
            tag=args.tag,
            args=args.args,
            mount_cwd=not args.no_mount,
            verbose=args.verbose,
        )

    # Fall back to normal mode
    if args.verbose:
        log("Mode: Normal (no sandbox available)")
    return launch_normal(args.args, args.verbose)


if __name__ == "__main__":
    sys.exit(main())
