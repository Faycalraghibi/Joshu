#!/usr/bin/env python3
"""
telemetry_local.py - Local OpenTelemetry debugging setup.

Purpose:
    Sets up a local OTEL collector for debugging telemetry without
    sending data to external services.

Inputs:
    --start           Start local collector
    --stop            Stop local collector
    --logs            Show collector logs
    --verbose         Enable verbose output

Outputs:
    - Local OTEL collector running in container

Side Effects:
    - Starts/stops Docker container
    - Updates local telemetry endpoint

Safety Considerations:
    - Data stays local, never sent externally
    - Requires Docker or Podman
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent

CONTAINER_NAME = "joshu-otel-collector"
COLLECTOR_IMAGE = "otel/opentelemetry-collector:latest"
DEFAULT_OTLP_PORT = 4317
DEFAULT_HTTP_PORT = 4318


def log(message: str, verbose: bool = True) -> None:
    """Print a log message if verbose mode is enabled."""
    if verbose:
        print(f"[telemetry_local] {message}")


def log_error(message: str) -> None:
    """Print an error message."""
    print(f"[telemetry_local] ERROR: {message}", file=sys.stderr)


def log_success(message: str) -> None:
    """Print a success message."""
    print(f"[telemetry_local] ✓ {message}")


def detect_container_engine() -> str | None:
    """Detect available container engine."""
    for engine in ["docker", "podman"]:
        if shutil.which(engine):
            return engine
    return None


def is_collector_running(engine: str) -> bool:
    """Check if collector container is running."""
    try:
        result = subprocess.run(
            [engine, "ps", "-q", "-f", f"name={CONTAINER_NAME}"],
            capture_output=True,
            text=True,
        )
        return bool(result.stdout.strip())
    except Exception:
        return False


def start_collector(engine: str, verbose: bool = False) -> bool:
    """Start the local OTEL collector."""
    if is_collector_running(engine):
        log("Collector already running", verbose)
        return True

    log("Starting local OTEL collector...", verbose)

    # Create basic collector config
    config_content = """
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

exporters:
  logging:
    loglevel: debug

service:
  pipelines:
    traces:
      receivers: [otlp]
      exporters: [logging]
    metrics:
      receivers: [otlp]
      exporters: [logging]
    logs:
      receivers: [otlp]
      exporters: [logging]
"""

    config_path = PROJECT_ROOT / ".otel-collector-config.yaml"
    config_path.write_text(config_content)

    cmd = [
        engine,
        "run",
        "-d",
        "--name",
        CONTAINER_NAME,
        "-p",
        f"{DEFAULT_OTLP_PORT}:4317",
        "-p",
        f"{DEFAULT_HTTP_PORT}:4318",
        "-v",
        f"{config_path}:/etc/otel/config.yaml",
        COLLECTOR_IMAGE,
        "--config",
        "/etc/otel/config.yaml",
    ]

    log(f"Running: {' '.join(cmd)}", verbose)

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        log_error(f"Failed to start collector: {result.stderr}")
        return False

    log_success("Local OTEL collector started")
    print(f"\nOTLP gRPC endpoint: localhost:{DEFAULT_OTLP_PORT}")
    print(f"OTLP HTTP endpoint: localhost:{DEFAULT_HTTP_PORT}")
    print("\nTo configure Joshu:")
    print(f"  python scripts/telemetry.py --enable --endpoint http://localhost:{DEFAULT_HTTP_PORT}")

    return True


def stop_collector(engine: str, verbose: bool = False) -> bool:
    """Stop the local OTEL collector."""
    if not is_collector_running(engine):
        log("Collector not running", verbose)
        return True

    log("Stopping local OTEL collector...", verbose)

    subprocess.run([engine, "stop", CONTAINER_NAME], capture_output=True)
    subprocess.run([engine, "rm", CONTAINER_NAME], capture_output=True)

    # Cleanup config
    config_path = PROJECT_ROOT / ".otel-collector-config.yaml"
    if config_path.exists():
        config_path.unlink()

    log_success("Local OTEL collector stopped")
    return True


def show_logs(engine: str, verbose: bool = False) -> bool:
    """Show collector container logs."""
    if not is_collector_running(engine):
        log_error("Collector not running")
        return False

    subprocess.run([engine, "logs", "-f", CONTAINER_NAME])
    return True


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Local OpenTelemetry debugging setup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/telemetry_local.py --start
    python scripts/telemetry_local.py --logs
    python scripts/telemetry_local.py --stop
        """,
    )
    parser.add_argument(
        "--start",
        action="store_true",
        help="Start local OTEL collector",
    )
    parser.add_argument(
        "--stop",
        action="store_true",
        help="Stop local OTEL collector",
    )
    parser.add_argument(
        "--logs",
        action="store_true",
        help="Show collector logs",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show collector status",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    # Detect container engine
    engine = detect_container_engine()
    if not engine:
        log_error("Docker or Podman required for local telemetry debugging")
        return 1

    log(f"Using container engine: {engine}", args.verbose)

    if args.start:
        return 0 if start_collector(engine, args.verbose) else 1

    if args.stop:
        return 0 if stop_collector(engine, args.verbose) else 1

    if args.logs:
        return 0 if show_logs(engine, args.verbose) else 1

    if args.status or not any([args.start, args.stop, args.logs]):
        running = is_collector_running(engine)
        print(f"Local OTEL Collector: {'RUNNING' if running else 'STOPPED'}")
        if running:
            print(f"Container: {CONTAINER_NAME}")
            print(f"OTLP gRPC: localhost:{DEFAULT_OTLP_PORT}")
            print(f"OTLP HTTP: localhost:{DEFAULT_HTTP_PORT}")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
