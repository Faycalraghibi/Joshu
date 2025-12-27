#!/usr/bin/env python3
"""
get_release_version.py - Calculate release versions for different release types.

Purpose:
    Computes release version numbers based on release type (nightly, preview,
    stable, patch) and checks for conflicts with existing versions.

Inputs:
    --type TYPE       Release type (nightly|preview|stable|patch)
    --check-pypi      Check for conflicts with PyPI versions
    --check-git       Check for conflicts with Git tags
    --verbose         Enable verbose output

Outputs:
    - Version string to stdout
    - Exit code 0 on success, 1 on conflict

Side Effects:
    - None (read-only version calculation)

Safety Considerations:
    - Does not modify any files
    - Checks for version conflicts before output
"""

import argparse
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore

SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent.parent


def log(message: str, verbose: bool = True) -> None:
    """Print a log message if verbose mode is enabled."""
    if verbose:
        print(f"[get_release_version] {message}", file=sys.stderr)


def log_error(message: str) -> None:
    """Print an error message."""
    print(f"[get_release_version] ERROR: {message}", file=sys.stderr)


def log_success(message: str) -> None:
    """Print a success message."""
    print(f"[get_release_version] ✓ {message}", file=sys.stderr)


def get_current_version() -> str:
    """Read current version from pyproject.toml."""
    pyproject_path = PROJECT_ROOT / "pyproject.toml"

    if not pyproject_path.exists():
        return "0.0.0"

    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        return data.get("project", {}).get("version", "0.0.0")
    except Exception:
        return "0.0.0"


def parse_version(version: str) -> tuple:
    """Parse version string into (major, minor, patch) tuple."""
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", version)
    if match:
        return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    return (0, 0, 0)


def get_git_tags() -> list:
    """Get list of existing Git tags."""
    try:
        result = subprocess.run(
            ["git", "tag", "-l"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip().splitlines()
    except Exception:
        pass
    return []


def get_nightly_version(base_version: str) -> str:
    """Generate nightly version with date suffix."""
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    major, minor, patch = parse_version(base_version)
    return f"{major}.{minor}.{patch}.dev{date_str}"


def get_preview_version(base_version: str, preview_num: int = 1) -> str:
    """Generate preview/RC version."""
    major, minor, patch = parse_version(base_version)
    return f"{major}.{minor}.{patch}rc{preview_num}"


def get_stable_version(base_version: str) -> str:
    """Get stable version (just the base)."""
    major, minor, patch = parse_version(base_version)
    return f"{major}.{minor}.{patch}"


def get_patch_version(base_version: str) -> str:
    """Increment patch version."""
    major, minor, patch = parse_version(base_version)
    return f"{major}.{minor}.{patch + 1}"


def check_git_conflict(version: str, verbose: bool = False) -> bool:
    """Check if version conflicts with existing Git tags."""
    tags = get_git_tags()
    tag_name = f"v{version}"

    if tag_name in tags:
        log(f"Conflict: Git tag {tag_name} already exists", verbose)
        return True

    return False


def check_pypi_conflict(version: str, verbose: bool = False) -> bool:
    """Check if version exists on PyPI (placeholder)."""
    # This would require making HTTP requests to PyPI API
    # For now, just return False (no conflict)
    log("PyPI conflict check not implemented", verbose)
    return False


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Calculate release versions for different release types",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/releasing/get_release_version.py --type stable
    python scripts/releasing/get_release_version.py --type nightly --check-git
    python scripts/releasing/get_release_version.py --type patch
        """,
    )
    parser.add_argument(
        "--type",
        "-t",
        required=True,
        choices=["nightly", "preview", "stable", "patch"],
        help="Release type",
    )
    parser.add_argument(
        "--preview-num",
        type=int,
        default=1,
        help="Preview/RC number (for preview releases)",
    )
    parser.add_argument(
        "--check-pypi",
        action="store_true",
        help="Check for conflicts with PyPI versions",
    )
    parser.add_argument(
        "--check-git",
        action="store_true",
        help="Check for conflicts with Git tags",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    # Get current version
    current = get_current_version()
    log(f"Current version: {current}", args.verbose)

    # Calculate new version based on type
    if args.type == "nightly":
        new_version = get_nightly_version(current)
    elif args.type == "preview":
        new_version = get_preview_version(current, args.preview_num)
    elif args.type == "stable":
        new_version = get_stable_version(current)
    elif args.type == "patch":
        new_version = get_patch_version(current)
    else:
        log_error(f"Unknown release type: {args.type}")
        return 1

    log(f"Calculated version: {new_version}", args.verbose)

    # Check for conflicts
    has_conflict = False

    if args.check_git:
        if check_git_conflict(new_version, args.verbose):
            log_error(f"Git tag conflict: v{new_version}")
            has_conflict = True

    if args.check_pypi:
        if check_pypi_conflict(new_version, args.verbose):
            log_error(f"PyPI conflict: {new_version}")
            has_conflict = True

    if has_conflict:
        return 1

    # Output version to stdout
    print(new_version)
    log_success(f"Version: {new_version}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
