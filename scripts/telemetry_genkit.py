#!/usr/bin/env python3
"""
telemetry_genkit.py - Local Genkit telemetry server integration.

Purpose:
    Sets up a local Genkit telemetry server for viewing traces
    and debugging AI operations.

Inputs:
    --start           Start Genkit server
    --stop            Stop Genkit server
    --status          Show status
    --port PORT       Server port (default: 4000)
    --verbose         Enable verbose output

Outputs:
    - Local Genkit telemetry server with UI

Side Effects:
    - Starts/stops Genkit process
    - Configures OTEL to export to Genkit

Safety Considerations:
    - Data stays local
    - Requires Node.js and Genkit CLI
"""

import argparse
import shutil
import signal
import subprocess
import sys
from pathlib import Path
from typing import Optional

SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent

DEFAULT_PORT = 4000
PID_FILE = PROJECT_ROOT / ".genkit-server.pid"


def log(message: str, verbose: bool = True) -> None:
    if verbose:
        print(f"[telemetry_genkit] {message}")


def log_error(message: str) -> None:
    print(f"[telemetry_genkit] ERROR: {message}", file=sys.stderr)


def log_success(message: str) -> None:
    print(f"[telemetry_genkit] ✓ {message}")


def check_genkit_cli() -> bool:
    """Check if Genkit CLI is installed."""
    return shutil.which("genkit") is not None


def check_node() -> bool:
    """Check if Node.js is installed."""
    return shutil.which("node") is not None


def get_running_pid() -> Optional[int]:
    """Get PID of running Genkit server."""
    if not PID_FILE.exists():
        return None

    try:
        pid = int(PID_FILE.read_text().strip())
        # Check if process is still running
        try:
            import os

            os.kill(pid, 0)
            return pid
        except (OSError, ProcessLookupError):
            PID_FILE.unlink()
            return None
    except Exception:
        return None


def is_server_running() -> bool:
    """Check if Genkit server is running."""
    return get_running_pid() is not None


def start_server(port: int = DEFAULT_PORT, verbose: bool = False) -> bool:
    """Start Genkit telemetry server."""
    if is_server_running():
        log("Genkit server already running", verbose)
        return True

    if not check_genkit_cli():
        log_error("Genkit CLI not found")
        log_error("Install: npm install -g genkit")
        return False

    log(f"Starting Genkit telemetry server on port {port}...", verbose)

    # Start Genkit in dev mode with telemetry
    cmd = ["genkit", "start", "--port", str(port)]

    log(f"Running: {' '.join(cmd)}", verbose)

    try:
        # Start process in background
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=PROJECT_ROOT,
            start_new_session=True,
        )

        # Save PID
        PID_FILE.write_text(str(process.pid))

        log_success(f"Genkit server started (PID: {process.pid})")
        print(f"\nGenkit UI: http://localhost:{port}")
        print(f"OTLP endpoint: http://localhost:{port}/api/telemetry")
        print("\nTo configure Joshu:")
        print(
            f"  python scripts/telemetry.py --enable --endpoint http://localhost:{port}/api/telemetry"
        )

        return True

    except Exception as e:
        log_error(f"Failed to start Genkit: {e}")
        return False


def stop_server(verbose: bool = False) -> bool:
    """Stop Genkit server."""
    pid = get_running_pid()

    if not pid:
        log("Genkit server not running", verbose)
        return True

    log(f"Stopping Genkit server (PID: {pid})...", verbose)

    try:
        import os

        os.kill(pid, signal.SIGTERM)

        # Wait a moment and force kill if needed
        import time

        time.sleep(2)

        try:
            os.kill(pid, 0)
            # Still running, force kill
            os.kill(pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass

        if PID_FILE.exists():
            PID_FILE.unlink()

        log_success("Genkit server stopped")
        return True

    except Exception as e:
        log_error(f"Failed to stop Genkit: {e}")
        return False


def show_status() -> None:
    """Show server status."""
    running = is_server_running()
    pid = get_running_pid()
    genkit_installed = check_genkit_cli()

    print("=" * 50)
    print("Genkit Telemetry Status")
    print("=" * 50)
    print(f"  Server:   {'RUNNING' if running else 'STOPPED'}")
    if pid:
        print(f"  PID:      {pid}")
    print(f"  Genkit:   {'Installed' if genkit_installed else 'Not installed'}")

    if running:
        print(f"\n  UI: http://localhost:{DEFAULT_PORT}")
    elif not genkit_installed:
        print("\n  Install Genkit: npm install -g genkit")

    print("=" * 50)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Local Genkit telemetry server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Provides:
    - Local trace visualization
    - AI operation debugging
    - Span inspection UI

Examples:
    python scripts/telemetry_genkit.py --start
    python scripts/telemetry_genkit.py --start --port 5000
    python scripts/telemetry_genkit.py --stop
        """,
    )
    parser.add_argument("--start", action="store_true", help="Start Genkit server")
    parser.add_argument("--stop", action="store_true", help="Stop Genkit server")
    parser.add_argument("--status", action="store_true", help="Show status")
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help=f"Server port (default: {DEFAULT_PORT})"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if args.start:
        if not check_node():
            log_error("Node.js required for Genkit")
            return 1
        return 0 if start_server(args.port, args.verbose) else 1

    if args.stop:
        return 0 if stop_server(args.verbose) else 1

    # Default to status
    show_status()
    return 0


if __name__ == "__main__":
    sys.exit(main())
