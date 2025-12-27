#!/usr/bin/env python3
"""
check_lockfile.py - Validate dependency integrity for Python and npm.

Purpose:
    Validates lockfiles for both Python (requirements.txt) and npm
    (package-lock.json) to ensure dependency integrity and security.

Inputs:
    --python          Check Python dependencies only
    --npm             Check npm dependencies only
    --strict          Exit with error on any issue
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
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent


def log(message: str, verbose: bool = True) -> None:
    if verbose:
        print(f"[lockfile] {message}")


def log_error(message: str) -> None:
    print(f"[lockfile] ERROR: {message}", file=sys.stderr)


def log_success(message: str) -> None:
    print(f"[lockfile] ✓ {message}")


def log_warning(message: str) -> None:
    print(f"[lockfile] ⚠ {message}")


# =============================================================================
# Python Dependency Check
# =============================================================================


def parse_requirements(requirements_path: Path) -> Dict[str, str]:
    """Parse requirements.txt and return package->version mapping."""
    packages = {}

    if not requirements_path.exists():
        return packages

    for line in requirements_path.read_text().splitlines():
        line = line.strip()

        if not line or line.startswith("#") or line.startswith("-"):
            continue

        for sep in ["==", ">=", "<=", "~=", ">", "<"]:
            if sep in line:
                name, version = line.split(sep, 1)
                packages[name.strip().lower()] = version.strip()
                break
        else:
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


def check_python_deps(verbose: bool = False) -> Tuple[List[str], List[str], int]:
    """Check Python dependencies. Returns (issues, warnings, ok_count)."""
    issues = []
    warnings = []
    ok_count = 0

    requirements_path = PROJECT_ROOT / "requirements.txt"
    if not requirements_path.exists():
        log("requirements.txt not found, skipping Python check", verbose)
        return issues, warnings, 0

    required = parse_requirements(requirements_path)
    installed = get_installed_packages()

    for pkg, req_version in required.items():
        if pkg not in installed:
            issues.append(f"Python: {pkg} not installed")
        elif req_version != "*":
            inst_version = installed[pkg]
            if not (
                req_version.startswith(inst_version)
                or inst_version.startswith(req_version.rstrip("*"))
            ):
                warnings.append(
                    f"Python: {pkg} version mismatch (want {req_version}, have {inst_version})"
                )
            else:
                ok_count += 1
        else:
            ok_count += 1

    return issues, warnings, ok_count


# =============================================================================
# npm Lockfile Integrity Check
# =============================================================================


def check_npm_lockfile(
    lockfile_path: Path, verbose: bool = False
) -> Tuple[List[str], List[str], int]:
    """
    Validate package-lock.json integrity.
    Checks that all dependencies have resolved and integrity fields.
    Returns (issues, warnings, ok_count).
    """
    issues = []
    warnings = []
    ok_count = 0

    if not lockfile_path.exists():
        log(f"{lockfile_path.name} not found, skipping npm check", verbose)
        return issues, warnings, 0

    try:
        content = json.loads(lockfile_path.read_text())
    except json.JSONDecodeError as e:
        issues.append(f"npm: Invalid JSON in {lockfile_path.name}: {e}")
        return issues, warnings, 0

    # Check lockfileVersion
    lockfile_version = content.get("lockfileVersion", 1)
    log(f"npm lockfile version: {lockfile_version}", verbose)

    # Get packages based on lockfile version
    if lockfile_version >= 2:
        packages = content.get("packages", {})
    else:
        packages = content.get("dependencies", {})

    if not packages:
        log("No packages found in lockfile", verbose)
        return issues, warnings, 0

    # Workspace patterns to exclude (local packages)
    workspace_prefixes = ("packages/", "apps/", "libs/")

    for pkg_path, pkg_info in packages.items():
        # Skip root package
        if pkg_path == "":
            continue

        # Skip workspace packages (local)
        is_workspace = any(pkg_path.startswith(f"node_modules/{p}") for p in workspace_prefixes)
        if is_workspace or pkg_info.get("link") or pkg_info.get("resolved", "").startswith("file:"):
            log(f"Skipping workspace: {pkg_path}", verbose)
            continue

        # Check for resolved field
        resolved = pkg_info.get("resolved")
        integrity = pkg_info.get("integrity")

        pkg_name = pkg_path.replace("node_modules/", "")

        if not resolved:
            # Some local deps don't have resolved
            if pkg_info.get("version"):
                warnings.append(f"npm: {pkg_name} missing 'resolved' field")

        if not integrity:
            if resolved and "registry" in resolved:
                issues.append(f"npm: {pkg_name} missing 'integrity' hash")
            else:
                warnings.append(f"npm: {pkg_name} missing 'integrity' (may be local)")
        else:
            ok_count += 1
            log(f"OK: {pkg_name}", verbose)

    return issues, warnings, ok_count


def find_npm_lockfiles() -> List[Path]:
    """Find all package-lock.json files in the project."""
    lockfiles = []

    # Root lockfile
    root_lockfile = PROJECT_ROOT / "package-lock.json"
    if root_lockfile.exists():
        lockfiles.append(root_lockfile)

    # Package lockfiles
    packages_dir = PROJECT_ROOT / "packages"
    if packages_dir.exists():
        for pkg_dir in packages_dir.iterdir():
            if pkg_dir.is_dir():
                lockfile = pkg_dir / "package-lock.json"
                if lockfile.exists():
                    lockfiles.append(lockfile)

    return lockfiles


def check_npm_deps(verbose: bool = False) -> Tuple[List[str], List[str], int]:
    """Check all npm lockfiles. Returns (issues, warnings, ok_count)."""
    all_issues = []
    all_warnings = []
    total_ok = 0

    lockfiles = find_npm_lockfiles()

    if not lockfiles:
        log("No package-lock.json files found", verbose)
        return all_issues, all_warnings, 0

    for lockfile in lockfiles:
        rel_path = (
            lockfile.relative_to(PROJECT_ROOT)
            if lockfile.is_relative_to(PROJECT_ROOT)
            else lockfile
        )
        log(f"Checking {rel_path}...", verbose)

        issues, warnings, ok_count = check_npm_lockfile(lockfile, verbose)
        all_issues.extend(issues)
        all_warnings.extend(warnings)
        total_ok += ok_count

    return all_issues, all_warnings, total_ok


# =============================================================================
# Main
# =============================================================================


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate dependency integrity (Python + npm)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Checks:
    Python: requirements.txt vs installed packages
    npm: package-lock.json resolved/integrity fields

Examples:
    python scripts/check_lockfile.py              # Check all
    python scripts/check_lockfile.py --python     # Python only
    python scripts/check_lockfile.py --npm        # npm only
    python scripts/check_lockfile.py --strict     # Fail on issues
        """,
    )
    parser.add_argument("--python", action="store_true", help="Check Python only")
    parser.add_argument("--npm", action="store_true", help="Check npm only")
    parser.add_argument("--strict", action="store_true", help="Exit with error on any issue")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Default to both if neither specified
    check_python = args.python or (not args.python and not args.npm)
    check_npm = args.npm or (not args.python and not args.npm)

    print("=" * 60)
    print("Dependency Lockfile Validation")
    print("=" * 60)

    all_issues = []
    all_warnings = []
    total_ok = 0

    if check_python:
        log("Checking Python dependencies...", args.verbose)
        issues, warnings, ok = check_python_deps(args.verbose)
        all_issues.extend(issues)
        all_warnings.extend(warnings)
        total_ok += ok

    if check_npm:
        log("Checking npm dependencies...", args.verbose)
        issues, warnings, ok = check_npm_deps(args.verbose)
        all_issues.extend(issues)
        all_warnings.extend(warnings)
        total_ok += ok

    # Report results
    print("=" * 60)

    if total_ok > 0:
        log_success(f"{total_ok} packages verified")

    if all_warnings:
        log_warning(f"{len(all_warnings)} warnings:")
        for w in all_warnings[:10]:  # Limit output
            print(f"  - {w}")
        if len(all_warnings) > 10:
            print(f"  ... and {len(all_warnings) - 10} more")

    if all_issues:
        log_error(f"{len(all_issues)} issues:")
        for i in all_issues[:10]:
            print(f"  - {i}")
        if len(all_issues) > 10:
            print(f"  ... and {len(all_issues) - 10} more")

    print("=" * 60)

    if all_issues:
        if args.strict:
            log_error("Lockfile validation failed")
            return 1
        log_warning("Some issues found, run with --strict to fail")
        return 0

    log_success("All lockfiles validated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
