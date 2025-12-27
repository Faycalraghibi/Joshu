#!/usr/bin/env python3
"""
sandbox_command.py - Execute commands in sandbox container.

Purpose:
    Runs Joshu CLI commands inside a sandboxed container environment
    with appropriate volume mounts and settings.

Inputs:
    --engine          Container engine to use (docker|podman|auto)
    --tag             Image tag (default: latest)
    --mount-cwd       Mount current working directory
    -- [ARGS]         Arguments to pass to joshu

Outputs:
    - Command output from container

Side Effects:
    - Runs container with mounted volumes

Safety Considerations:
    - Runs as non-root inside container
    - Configurable volume mounts
    - Container is removed after execution (--rm)
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent


def log(message: str, verbose: bool = True) -> None:
    """Print a log message if verbose mode is enabled."""
    if verbose:
        print(f"[sandbox] {message}")


def log_error(message: str) -> None:
    """Print an error message."""
    print(f"[sandbox] ERROR: {message}", file=sys.stderr)


def detect_container_engine() -> str | None:
    """Detect available container engine (Docker or Podman)."""
    for engine in ["docker", "podman"]:
        if shutil.which(engine):
            return engine
    return None


def get_sandbox_command() -> str | None:
    """
    API function to get available sandbox command.

    This function is designed to be called by other scripts (like start.py)
    to determine sandbox availability.

    Returns:
        "docker" if Docker is available and responsive
        "podman" if Podman is available and responsive
        None if no sandbox tool is available
    """
    for engine in ["docker", "podman"]:
        if shutil.which(engine):
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


def check_image_exists(engine: str, image: str) -> bool:
    """Check if container image exists locally."""
    try:
        result = subprocess.run(
            [engine, "image", "inspect", image],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def run_sandbox(
    engine: str,
    tag: str,
    mount_cwd: bool,
    args: list,
    verbose: bool = False,
) -> int:
    """Run command in sandbox container."""
    image = f"joshu-sandbox:{tag}"

    # Check image exists
    if not check_image_exists(engine, image):
        log_error(f"Image not found: {image}")
        log_error("Run 'python scripts/build_sandbox.py' first")
        return 1

    # Build docker run command
    cmd = [engine, "run", "-it", "--rm"]

    # Add volume mount for current directory
    if mount_cwd:
        cwd = Path.cwd().resolve()
        cmd.extend(["-v", f"{cwd}:/workspace"])
        cmd.extend(["-w", "/workspace"])

    # Add image name
    cmd.append(image)

    # Add user arguments
    if args:
        cmd.extend(args)

    log(f"Running: {' '.join(cmd)}", verbose)

    # Run container
    try:
        result = subprocess.run(cmd)
        return result.returncode
    except KeyboardInterrupt:
        return 130  # Standard exit code for SIGINT
    except Exception as e:
        log_error(f"Failed to run container: {e}")
        return 1


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Execute commands in sandbox container",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/sandbox_command.py -- --help
    python scripts/sandbox_command.py -- chat "Hello"
    python scripts/sandbox_command.py --mount-cwd -- analyze file.py
        """,
    )
    parser.add_argument(
        "--engine",
        choices=["docker", "podman", "auto"],
        default="auto",
        help="Container engine to use (default: auto-detect)",
    )
    parser.add_argument(
        "--tag",
        default="latest",
        help="Image tag (default: latest)",
    )
    parser.add_argument(
        "--mount-cwd",
        action="store_true",
        help="Mount current working directory to /workspace",
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

    # Detect or use specified engine
    if args.engine == "auto":
        engine = detect_container_engine()
        if not engine:
            log_error("No container engine found (Docker or Podman)")
            return 1
    else:
        engine = args.engine
        if not shutil.which(engine):
            log_error(f"{engine} is not installed")
            return 1

    # Run sandbox
    return run_sandbox(
        engine=engine,
        tag=args.tag,
        mount_cwd=args.mount_cwd,
        args=args.args,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    sys.exit(main())
