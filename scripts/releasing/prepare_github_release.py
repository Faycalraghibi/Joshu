#!/usr/bin/env python3
"""
prepare_github_release.py - Prepare artifacts for GitHub Release.

Purpose:
    Builds distribution packages and prepares release notes
    for creating a GitHub Release.

Inputs:
    --version VERSION Required version string
    --output PATH     Output directory (default: dist)
    --verbose         Enable verbose output

Outputs:
    - Wheel and sdist packages in output directory
    - Release notes excerpt (RELEASE_NOTES.md)

Side Effects:
    - Runs Python build to create packages
    - Creates/updates release notes file

Safety Considerations:
    - Does not push or publish anything
    - Output can be reviewed before release
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent.parent


def log(message: str, verbose: bool = True) -> None:
    """Print a log message if verbose mode is enabled."""
    if verbose:
        print(f"[prepare_github_release] {message}")


def log_error(message: str) -> None:
    """Print an error message."""
    print(f"[prepare_github_release] ERROR: {message}", file=sys.stderr)


def log_success(message: str) -> None:
    """Print a success message."""
    print(f"[prepare_github_release] ✓ {message}")


def build_packages(output_dir: Path, verbose: bool = False) -> bool:
    """Build wheel and source distribution packages."""
    log("Building distribution packages...", verbose)

    cmd = [
        sys.executable,
        "-m",
        "build",
        "--outdir",
        str(output_dir),
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            capture_output=not verbose,
            text=True,
        )

        if result.returncode != 0:
            log_error("Failed to build packages")
            if not verbose and result.stderr:
                print(result.stderr)
            return False

        log_success("Built distribution packages")
        return True

    except Exception as e:
        log_error(f"Build failed: {e}")
        return False


def extract_changelog_for_version(version: str, verbose: bool = False) -> str:
    """Extract changelog section for specific version."""
    changelog_path = PROJECT_ROOT / "CHANGELOG.md"

    if not changelog_path.exists():
        log("CHANGELOG.md not found", verbose)
        return f"## Version {version}\n\nNo changelog available."

    content = changelog_path.read_text()

    # Try to find version section (various formats)
    patterns = [
        rf"##\s*\[?{re.escape(version)}\]?.*?\n(.*?)(?=\n##|\Z)",
        rf"##\s*v?{re.escape(version)}.*?\n(.*?)(?=\n##|\Z)",
    ]

    for pattern in patterns:
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if match:
            section = match.group(0).strip()
            log(f"Found changelog section for {version}", verbose)
            return section

    log(f"No changelog section found for {version}", verbose)
    return f"## Version {version}\n\nSee CHANGELOG.md for details."


def create_release_notes(
    version: str,
    output_dir: Path,
    verbose: bool = False,
) -> bool:
    """Create release notes file."""
    log("Creating release notes...", verbose)

    changelog = extract_changelog_for_version(version, verbose)

    release_notes = f"""# Joshu CLI v{version}

{changelog}

## Installation

```bash
pip install joshu
```

## Upgrade

```bash
pip install --upgrade joshu
```

## Documentation

See [README.md](https://github.com/Faycalraghibi/Joshu/blob/main/README.md) for documentation.
"""

    output_dir.mkdir(parents=True, exist_ok=True)
    notes_path = output_dir / "RELEASE_NOTES.md"
    notes_path.write_text(release_notes)

    log_success(f"Created {notes_path}")
    return True


def list_artifacts(output_dir: Path, verbose: bool = False) -> None:
    """List built artifacts."""
    if not output_dir.exists():
        return

    artifacts = list(output_dir.glob("joshu-*.whl")) + list(output_dir.glob("joshu-*.tar.gz"))

    if artifacts:
        log("Release artifacts:", True)
        for artifact in artifacts:
            size_kb = artifact.stat().st_size / 1024
            print(f"  - {artifact.name} ({size_kb:.1f} KB)")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Prepare artifacts for GitHub Release",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/releasing/prepare_github_release.py --version 0.1.0
    python scripts/releasing/prepare_github_release.py --version 0.1.0 --verbose
        """,
    )
    parser.add_argument(
        "--version",
        "-V",
        required=True,
        help="Version string for the release",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=PROJECT_ROOT / "dist",
        help="Output directory for artifacts (default: dist)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    output_dir = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output

    print("=" * 60)
    print(f"Preparing GitHub Release v{args.version}")
    print("=" * 60)

    # Step 1: Build packages
    if not build_packages(output_dir, args.verbose):
        return 1

    # Step 2: Create release notes
    if not create_release_notes(args.version, output_dir, args.verbose):
        return 1

    # Step 3: List artifacts
    list_artifacts(output_dir, args.verbose)

    print("=" * 60)
    log_success("Release preparation complete!")
    print("\nNext steps:")
    print(f"  1. Review artifacts in {output_dir}")
    print(f"  2. Create GitHub release with 'gh release create v{args.version}'")
    print(f"  3. Upload artifacts: 'gh release upload v{args.version} {output_dir}/*'")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
