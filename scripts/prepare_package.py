#!/usr/bin/env python3
"""
prepare_package.py - Propagate common files to packages.

Purpose:
    Copies common project files (README, LICENSE) to package
    directories for consistent distribution.

Inputs:
    --verbose         Enable verbose output

Outputs:
    - Copied README.md and LICENSE to package directories

Side Effects:
    - Overwrites existing files in package directories

Safety Considerations:
    - Only copies root-level common files
    - Does not modify original files
"""

import argparse
import shutil
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent


def log(message: str, verbose: bool = True) -> None:
    """Print a log message if verbose mode is enabled."""
    if verbose:
        print(f"[prepare_package] {message}")


def log_error(message: str) -> None:
    """Print an error message."""
    print(f"[prepare_package] ERROR: {message}", file=sys.stderr)


def log_success(message: str) -> None:
    """Print a success message."""
    print(f"[prepare_package] ✓ {message}")


# Common files to propagate
COMMON_FILES = ["README.md", "LICENSE"]

# Package directories to update
PACKAGE_DIRS = [
    "packages/vscode-joshu-companion",
]


def propagate_file(source: Path, dest_dir: Path, verbose: bool = False) -> bool:
    """Copy a file to a destination directory."""
    if not source.exists():
        log(f"Source file not found: {source.name}", verbose)
        return False

    if not dest_dir.exists():
        log(f"Destination directory not found: {dest_dir}", verbose)
        return False

    dest_file = dest_dir / source.name
    shutil.copy2(source, dest_file)
    log(f"Copied {source.name} -> {dest_dir.name}/", verbose)
    return True


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Propagate common files to packages",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/prepare_package.py
    python scripts/prepare_package.py --verbose
        """,
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    log("Propagating common files to packages...", args.verbose)

    copied = 0

    for pkg_rel_path in PACKAGE_DIRS:
        pkg_dir = PROJECT_ROOT / pkg_rel_path

        if not pkg_dir.exists():
            log(f"Package directory not found: {pkg_rel_path}", args.verbose)
            continue

        for file_name in COMMON_FILES:
            source = PROJECT_ROOT / file_name
            if propagate_file(source, pkg_dir, args.verbose):
                copied += 1

    if copied > 0:
        log_success(f"Propagated {copied} files")
    else:
        log("No files propagated", args.verbose)

    return 0


if __name__ == "__main__":
    sys.exit(main())
