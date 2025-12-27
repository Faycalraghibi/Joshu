#!/usr/bin/env python3
"""
check_build_status.py - Check if build is fresh relative to source changes.

Purpose:
    Compares .last_build timestamp with source file modification times
    to determine if a rebuild is needed.

Inputs:
    --fail-on-stale   Exit with error if build is stale
    --verbose         Enable verbose output

Outputs:
    - Build freshness report to stdout

Side Effects:
    - None (read-only check)

Safety Considerations:
    - Does not modify any files
    - Warning only by default (not an error)
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent


def log(message: str, verbose: bool = True) -> None:
    """Print a log message if verbose mode is enabled."""
    if verbose:
        print(f"[check_build_status] {message}")


def log_error(message: str) -> None:
    """Print an error message."""
    print(f"[check_build_status] ERROR: {message}", file=sys.stderr)


def log_success(message: str) -> None:
    """Print a success message."""
    print(f"[check_build_status] ✓ {message}")


def log_warning(message: str) -> None:
    """Print a warning message."""
    print(f"[check_build_status] ⚠ {message}")


def get_build_timestamp() -> datetime | None:
    """Get timestamp from .last_build marker."""
    marker_path = PROJECT_ROOT / ".last_build"

    if not marker_path.exists():
        return None

    try:
        data = json.loads(marker_path.read_text())
        timestamp_str = data.get("timestamp")
        if timestamp_str:
            return datetime.fromisoformat(timestamp_str)
    except Exception:
        pass

    # Fallback to file mtime
    return datetime.fromtimestamp(marker_path.stat().st_mtime, tz=timezone.utc)


def get_changed_files(since: datetime, verbose: bool = False) -> List[Tuple[Path, datetime]]:
    """Find source files modified after the given timestamp."""
    changed = []

    source_dirs = [
        PROJECT_ROOT / "src",
        PROJECT_ROOT / "scripts",
    ]

    source_extensions = {".py", ".yaml", ".yml", ".json", ".toml"}

    for source_dir in source_dirs:
        if not source_dir.exists():
            continue

        for source_file in source_dir.rglob("*"):
            if source_file.is_file() and source_file.suffix in source_extensions:
                try:
                    mtime = datetime.fromtimestamp(source_file.stat().st_mtime, tz=timezone.utc)
                    if mtime > since:
                        changed.append((source_file, mtime))
                        log(f"Changed: {source_file.relative_to(PROJECT_ROOT)}", verbose)
                except Exception:
                    pass

    return changed


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Check if build is fresh relative to source changes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/check_build_status.py
    python scripts/check_build_status.py --fail-on-stale
        """,
    )
    parser.add_argument(
        "--fail-on-stale",
        action="store_true",
        help="Exit with error if build is stale",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    log("Checking build freshness...", args.verbose)

    # Get build timestamp
    build_time = get_build_timestamp()

    if build_time is None:
        log_warning("No build marker found (.last_build)")
        log_warning("Run 'python scripts/build.py' to create a build")
        if args.fail_on_stale:
            return 1
        return 0

    log(f"Last build: {build_time.isoformat()}", args.verbose)

    # Find changed files
    changed = get_changed_files(build_time, args.verbose)

    print("=" * 60)
    print("Build Status Check")
    print("=" * 60)
    print(f"Last build: {build_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")

    if changed:
        log_warning(f"Build is STALE - {len(changed)} files changed since last build")
        print("\nChanged files:")
        for path, mtime in sorted(changed, key=lambda x: x[1], reverse=True)[:10]:
            rel_path = path.relative_to(PROJECT_ROOT)
            print(f"  - {rel_path} ({mtime.strftime('%H:%M:%S')})")

        if len(changed) > 10:
            print(f"  ... and {len(changed) - 10} more")

        print("\nRecommendation: Run 'python scripts/build.py'")
        print("=" * 60)

        if args.fail_on_stale:
            return 1
        return 0

    log_success("Build is FRESH - no changes since last build")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
