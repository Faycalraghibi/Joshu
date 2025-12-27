#!/usr/bin/env python3
"""
check_lockfile.py - Validate dependency integrity.

Purpose:
    Compares requirements.txt with installed packages and reports
    any missing or version-mismatched dependencies.

Inputs:
    --strict          Exit with error on any mismatch
    --verbose         Enable verbose output

Outputs:
    - Dependency status report to stdout

Side Effects:
    - None (read-only check)

Safety Considerations:
    - Does not modify any files
    - Non-destructive inspection only
"""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent


def log(message: str, verbose: bool = True) -> None:
    """Print a log message if verbose mode is enabled."""
    if verbose:
        print(f"[check_lockfile] {message}")


def log_error(message: str) -> None:
    """Print an error message."""
    print(f"[check_lockfile] ERROR: {message}", file=sys.stderr)


def log_success(message: str) -> None:
    """Print a success message."""
    print(f"[check_lockfile] ✓ {message}")


def log_warning(message: str) -> None:
    """Print a warning message."""
    print(f"[check_lockfile] ⚠ {message}")


def parse_requirements(requirements_path: Path) -> Dict[str, str]:
    """Parse requirements.txt and return package->version mapping."""
    packages = {}

    if not requirements_path.exists():
        return packages

    for line in requirements_path.read_text().splitlines():
        line = line.strip()

        # Skip comments and empty lines
        if not line or line.startswith("#"):
            continue

        # Skip options like -e or --index-url
        if line.startswith("-"):
            continue

        # Parse package==version, package>=version, etc.
        for sep in ["==", ">=", "<=", "~=", ">", "<"]:
            if sep in line:
                name, version = line.split(sep, 1)
                packages[name.strip().lower()] = version.strip()
                break
        else:
            # No version specifier
            packages[line.lower()] = "*"

    return packages


def get_installed_packages() -> Dict[str, str]:
    """Get currently installed packages via pip."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--format=freeze"],
            capture_output=True,
            text=True,
        )

        packages = {}
        for line in result.stdout.splitlines():
            if "==" in line:
                name, version = line.split("==", 1)
                packages[name.strip().lower()] = version.strip()

        return packages
    except Exception:
        return {}


def check_dependencies(
    required: Dict[str, str],
    installed: Dict[str, str],
    verbose: bool = False,
) -> Tuple[List[str], List[str], List[str]]:
    """
    Compare required vs installed packages.
    Returns (missing, mismatched, ok) lists.
    """
    missing = []
    mismatched = []
    ok = []

    for pkg, req_version in required.items():
        if pkg not in installed:
            missing.append(pkg)
            log(f"Missing: {pkg}", verbose)
        elif req_version != "*":
            inst_version = installed[pkg]
            # Simple version check - just compare strings for ==
            if req_version.startswith(inst_version) or inst_version.startswith(
                req_version.rstrip("*")
            ):
                ok.append(pkg)
                log(f"OK: {pkg}=={inst_version}", verbose)
            else:
                mismatched.append(f"{pkg} (want {req_version}, have {inst_version})")
                log(f"Mismatch: {pkg} (want {req_version}, have {inst_version})", verbose)
        else:
            ok.append(pkg)
            log(f"OK: {pkg}=={installed[pkg]}", verbose)

    return missing, mismatched, ok


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate dependency integrity",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/check_lockfile.py
    python scripts/check_lockfile.py --strict
        """,
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with error on any mismatch",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    requirements_path = PROJECT_ROOT / "requirements.txt"

    if not requirements_path.exists():
        log_warning("requirements.txt not found, skipping check")
        return 0

    log("Checking dependency integrity...", args.verbose)

    # Parse requirements
    required = parse_requirements(requirements_path)
    log(f"Found {len(required)} required packages", args.verbose)

    # Get installed packages
    installed = get_installed_packages()
    log(f"Found {len(installed)} installed packages", args.verbose)

    # Check dependencies
    missing, mismatched, ok = check_dependencies(required, installed, args.verbose)

    # Report results
    print("=" * 60)
    print("Dependency Check Results")
    print("=" * 60)

    if ok:
        log_success(f"{len(ok)} packages OK")

    if missing:
        log_warning(f"{len(missing)} packages missing:")
        for pkg in missing:
            print(f"  - {pkg}")

    if mismatched:
        log_warning(f"{len(mismatched)} version mismatches:")
        for pkg in mismatched:
            print(f"  - {pkg}")

    print("=" * 60)

    if missing or mismatched:
        if args.strict:
            log_error("Dependency check failed")
            return 1
        else:
            log_warning("Some dependencies may need attention")
            return 0

    log_success("All dependencies verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
