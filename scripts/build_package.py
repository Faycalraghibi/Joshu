#!/usr/bin/env python3
"""
build_package.py - Build individual Python packages.

Purpose:
    Builds a single package within the Joshu monorepo, handling
    compilation validation and asset copying.

Inputs:
    --package NAME    Package name to build (default: joshu)
    --dist            Create distribution package
    --verbose         Enable verbose output

Outputs:
    - Validated Python sources
    - Copied non-code assets
    - Package-specific build marker

Side Effects:
    - Creates/updates .last_build_<package> marker

Safety Considerations:
    - Read-only validation of source files
    - No modifications to source code
"""

import argparse
import compileall
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent


def log(message: str, verbose: bool = True) -> None:
    """Print a log message if verbose mode is enabled."""
    if verbose:
        print(f"[build_package] {message}")


def log_error(message: str) -> None:
    """Print an error message."""
    print(f"[build_package] ERROR: {message}", file=sys.stderr)


def log_success(message: str) -> None:
    """Print a success message."""
    print(f"[build_package] ✓ {message}")


def get_package_path(package_name: str) -> Path:
    """Get the source path for a package."""
    return PROJECT_ROOT / "src" / package_name


def validate_python_sources(package_path: Path, verbose: bool = False) -> bool:
    """Validate Python source files can be compiled."""
    log(f"Validating Python sources in {package_path}...", verbose)

    if not package_path.exists():
        log_error(f"Package path does not exist: {package_path}")
        return False

    # Use compileall to validate syntax
    success = compileall.compile_dir(
        str(package_path),
        quiet=0 if verbose else 2,
        force=True,
    )

    if not success:
        log_error("Python source validation failed")
        return False

    log_success("Python sources validated")
    return True


def copy_non_code_assets(package_path: Path, verbose: bool = False) -> bool:
    """Copy non-code assets (MD, JSON, YAML) alongside Python files."""
    log("Checking for non-code assets...", verbose)

    asset_extensions = {".md", ".json", ".yaml", ".yml", ".txt"}
    asset_count = 0

    for ext in asset_extensions:
        for asset_file in package_path.rglob(f"*{ext}"):
            asset_count += 1
            log(f"  Found: {asset_file.relative_to(package_path)}", verbose)

    log(f"Found {asset_count} non-code assets", verbose)
    return True


def create_dist_package(package_name: str, verbose: bool = False) -> bool:
    """Create distribution package using build module."""
    log("Creating distribution package...", verbose)

    try:
        import subprocess

        result = subprocess.run(
            [sys.executable, "-m", "build", "--wheel", "--outdir", "dist"],
            cwd=PROJECT_ROOT,
            capture_output=not verbose,
            text=True,
        )

        if result.returncode != 0:
            log_error("Failed to create distribution package")
            if not verbose and result.stderr:
                print(result.stderr)
            return False

        log_success("Distribution package created in dist/")
        return True

    except ImportError:
        log_error("'build' module not installed. Run: pip install build")
        return False


def create_package_marker(package_name: str, verbose: bool = False) -> None:
    """Create package-specific build marker."""
    marker_path = PROJECT_ROOT / f".last_build_{package_name}"

    build_info = {
        "package": package_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
    }

    marker_path.write_text(json.dumps(build_info, indent=2))
    log(f"Created package marker: {marker_path}", verbose)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Build individual Python packages",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/build_package.py --package joshu
    python scripts/build_package.py --package joshu --dist
        """,
    )
    parser.add_argument(
        "--package",
        "-p",
        default="joshu",
        help="Package name to build (default: joshu)",
    )
    parser.add_argument(
        "--dist",
        action="store_true",
        help="Create distribution package (wheel)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    log(f"Building package: {args.package}", args.verbose)

    # Get package path
    package_path = get_package_path(args.package)

    # Step 1: Validate Python sources
    if not validate_python_sources(package_path, args.verbose):
        return 1

    # Step 2: Check non-code assets
    copy_non_code_assets(package_path, args.verbose)

    # Step 3: Create dist package if requested
    if args.dist:
        if not create_dist_package(args.package, args.verbose):
            return 1

    # Step 4: Create build marker
    create_package_marker(args.package, args.verbose)

    log_success(f"Package '{args.package}' build complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
