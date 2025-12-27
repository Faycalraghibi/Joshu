#!/usr/bin/env python3
"""
copy_assets.py - Bundle runtime assets into distribution.

Purpose:
    Collects critical asset files from various source locations
    and consolidates them into a dedicated bundle directory.

Inputs:
    --source PATH     Source directory for assets
    --dest PATH       Destination directory
    --verbose         Enable verbose output

Outputs:
    - Copied asset files in destination directory

Side Effects:
    - Creates destination directory if needed
    - Overwrites existing files in destination

Safety Considerations:
    - Only copies, never deletes source files
    - Preserves directory structure
"""

import argparse
import shutil
import sys
from pathlib import Path
from typing import Set

SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent


def log(message: str, verbose: bool = True) -> None:
    """Print a log message if verbose mode is enabled."""
    if verbose:
        print(f"[copy_assets] {message}")


def log_error(message: str) -> None:
    """Print an error message."""
    print(f"[copy_assets] ERROR: {message}", file=sys.stderr)


def log_success(message: str) -> None:
    """Print a success message."""
    print(f"[copy_assets] ✓ {message}")


# Default asset extensions to copy
DEFAULT_EXTENSIONS: Set[str] = {
    ".yaml",
    ".yml",
    ".json",
    ".md",
    ".txt",
    ".html",
    ".css",
    ".js",
}


def copy_assets(
    source: Path,
    dest: Path,
    extensions: Set[str] | None = None,
    verbose: bool = False,
) -> int:
    """Copy asset files from source to destination."""
    if extensions is None:
        extensions = DEFAULT_EXTENSIONS

    if not source.exists():
        log_error(f"Source directory does not exist: {source}")
        return 0

    # Create destination directory
    dest.mkdir(parents=True, exist_ok=True)

    copied_count = 0

    for src_file in source.rglob("*"):
        if src_file.is_file() and src_file.suffix.lower() in extensions:
            # Compute relative path and destination
            rel_path = src_file.relative_to(source)
            dest_file = dest / rel_path

            # Ensure parent directory exists
            dest_file.parent.mkdir(parents=True, exist_ok=True)

            # Copy file
            shutil.copy2(src_file, dest_file)
            copied_count += 1
            log(f"Copied: {rel_path}", verbose)

    return copied_count


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Bundle runtime assets into distribution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/copy_assets.py --source config --dest dist/config
    python scripts/copy_assets.py --source docs --dest dist/docs
        """,
    )
    parser.add_argument(
        "--source",
        "-s",
        type=Path,
        default=PROJECT_ROOT / "config",
        help="Source directory for assets (default: config)",
    )
    parser.add_argument(
        "--dest",
        "-d",
        type=Path,
        default=PROJECT_ROOT / "dist" / "config",
        help="Destination directory (default: dist/config)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    # Resolve paths relative to project root if not absolute
    source = args.source if args.source.is_absolute() else PROJECT_ROOT / args.source
    dest = args.dest if args.dest.is_absolute() else PROJECT_ROOT / args.dest

    log(f"Copying assets from {source} to {dest}", args.verbose)

    copied = copy_assets(source, dest, verbose=args.verbose)

    if copied > 0:
        log_success(f"Copied {copied} asset files")
    else:
        log("No asset files found to copy", args.verbose)

    return 0


if __name__ == "__main__":
    sys.exit(main())
