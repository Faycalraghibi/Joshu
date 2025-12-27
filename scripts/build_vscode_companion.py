#!/usr/bin/env python3
"""
build_vscode_companion.py - Build the VSCode Joshu Companion extension.

Purpose:
    Builds the VSCode extension for Joshu CLI integration.

Inputs:
    --package         Create .vsix package file
    --verbose         Enable verbose output

Outputs:
    - Compiled extension in packages/vscode-joshu-companion/out/
    - Optional .vsix package in dist/

Side Effects:
    - Runs npm install if node_modules missing
    - Compiles TypeScript sources

Safety Considerations:
    - Requires Node.js and npm to be installed
    - Does not modify source files
"""

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent
EXTENSION_DIR = PROJECT_ROOT / "packages" / "vscode-joshu-companion"


def log(message: str, verbose: bool = True) -> None:
    """Print a log message if verbose mode is enabled."""
    if verbose:
        print(f"[build_vscode] {message}")


def log_error(message: str) -> None:
    """Print an error message."""
    print(f"[build_vscode] ERROR: {message}", file=sys.stderr)


def log_success(message: str) -> None:
    """Print a success message."""
    print(f"[build_vscode] ✓ {message}")


def check_node_available() -> bool:
    """Check if Node.js and npm are available."""
    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return False

        result = subprocess.run(
            ["npm", "--version"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def check_vsce_available() -> bool:
    """Check if vsce (VS Code Extension CLI) is available."""
    try:
        result = subprocess.run(
            ["npx", "vsce", "--version"],
            capture_output=True,
            text=True,
            cwd=EXTENSION_DIR,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def install_dependencies(verbose: bool = False) -> bool:
    """Install npm dependencies."""
    node_modules = EXTENSION_DIR / "node_modules"

    if node_modules.exists():
        log("Dependencies already installed", verbose)
        return True

    log("Installing npm dependencies...", verbose)
    result = subprocess.run(
        ["npm", "install"],
        cwd=EXTENSION_DIR,
        capture_output=not verbose,
        text=True,
    )

    if result.returncode != 0:
        log_error("Failed to install npm dependencies")
        if not verbose and result.stderr:
            print(result.stderr)
        return False

    log_success("Dependencies installed")
    return True


def compile_extension(verbose: bool = False) -> bool:
    """Compile TypeScript sources."""
    log("Compiling TypeScript...", verbose)

    result = subprocess.run(
        ["npm", "run", "compile"],
        cwd=EXTENSION_DIR,
        capture_output=not verbose,
        text=True,
        shell=True,  # Required on Windows for npm scripts
    )

    if result.returncode != 0:
        log_error("TypeScript compilation failed")
        if not verbose and result.stderr:
            print(result.stderr)
        return False

    log_success("TypeScript compiled")
    return True


def create_vsix_package(verbose: bool = False) -> bool:
    """Create .vsix package using vsce."""
    log("Creating .vsix package...", verbose)

    result = subprocess.run(
        ["npx", "vsce", "package", "--out", str(PROJECT_ROOT / "dist")],
        cwd=EXTENSION_DIR,
        capture_output=not verbose,
        text=True,
        shell=True,
    )

    if result.returncode != 0:
        log_error("Failed to create .vsix package")
        if not verbose and result.stderr:
            print(result.stderr)
        return False

    log_success("Created .vsix package in dist/")
    return True


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Build the VSCode Joshu Companion extension",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/build_vscode_companion.py
    python scripts/build_vscode_companion.py --package
        """,
    )
    parser.add_argument(
        "--package",
        action="store_true",
        help="Create .vsix package file",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    # Check extension directory exists
    if not EXTENSION_DIR.exists():
        log_error(f"Extension directory not found: {EXTENSION_DIR}")
        return 1

    log(f"Building extension in: {EXTENSION_DIR}", args.verbose)

    # Step 1: Check Node.js availability
    if not check_node_available():
        log_error("Node.js and npm are required but not found")
        log_error("Install from: https://nodejs.org/")
        return 1
    log_success("Node.js and npm detected")

    # Step 2: Install dependencies
    if not install_dependencies(args.verbose):
        return 1

    # Step 3: Compile TypeScript
    if not compile_extension(args.verbose):
        return 1

    # Step 4: Create .vsix package if requested
    if args.package:
        # Ensure dist directory exists
        (PROJECT_ROOT / "dist").mkdir(exist_ok=True)
        if not create_vsix_package(args.verbose):
            return 1

    log_success("VSCode extension build complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
