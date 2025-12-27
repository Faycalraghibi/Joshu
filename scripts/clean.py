#!/usr/bin/env python3
"""
clean.py - Remove build artifacts for all languages.

Purpose:
    Cleans build artifacts, cache directories, and temporary files
    from the Joshu monorepo for 20+ programming languages.

Inputs:
    --all             Clean everything including vendored dependencies
    --<language>      Clean only artifacts for that language
    --dry-run         Show what would be deleted without deleting
    --verbose         Enable verbose output

Outputs:
    - Removes specified directories and files

Side Effects:
    - Deletes files and directories (unless --dry-run)

Safety Considerations:
    - Use --dry-run to preview deletions
    - Does not touch source files or git history
"""

import argparse
import shutil
import sys
from pathlib import Path
from typing import List, Set

SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent


def log(message: str, verbose: bool = True) -> None:
    """Print a log message if verbose mode is enabled."""
    if verbose:
        print(f"[clean] {message}")


def log_error(message: str) -> None:
    """Print an error message."""
    print(f"[clean] ERROR: {message}", file=sys.stderr)


def log_success(message: str) -> None:
    """Print a success message."""
    print(f"[clean] ✓ {message}")


# =============================================================================
# Language-specific artifact patterns
# =============================================================================


def get_python_targets(include_all: bool = False) -> Set[Path]:
    """Get Python build artifacts."""
    targets = set()

    for pycache in PROJECT_ROOT.rglob("__pycache__"):
        targets.add(pycache)
    for egg_info in PROJECT_ROOT.rglob("*.egg-info"):
        targets.add(egg_info)
    for pyc in PROJECT_ROOT.rglob("*.pyc"):
        targets.add(pyc)
    for pyo in PROJECT_ROOT.rglob("*.pyo"):
        targets.add(pyo)

    for pattern in [
        "dist",
        "build",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".nox",
        ".coverage",
        "htmlcov",
        ".eggs",
    ]:
        path = PROJECT_ROOT / pattern
        if path.exists():
            targets.add(path)

    for marker in PROJECT_ROOT.glob(".last_build*"):
        targets.add(marker)

    if include_all:
        for venv in [".venv", "venv", ".virtualenv", "virtualenv"]:
            path = PROJECT_ROOT / venv
            if path.exists():
                targets.add(path)

    return targets


def get_typescript_targets(include_all: bool = False) -> Set[Path]:
    """Get TypeScript/Node.js build artifacts."""
    targets = set()

    for pattern in [
        "out",
        "dist",
        ".tsbuildinfo",
        "*.vsix",
        ".eslintcache",
        ".cache",
        "coverage",
        ".parcel-cache",
        ".next",
        ".nuxt",
    ]:
        for path in PROJECT_ROOT.rglob(pattern):
            targets.add(path)

    if include_all:
        for node_modules in PROJECT_ROOT.rglob("node_modules"):
            targets.add(node_modules)
        for pnpm in PROJECT_ROOT.rglob(".pnpm-store"):
            targets.add(pnpm)

    return targets


def get_java_targets(include_all: bool = False) -> Set[Path]:
    """Get Java build artifacts."""
    targets = set()

    for pattern in ["target", ".gradle", "out", "*.class"]:
        for path in PROJECT_ROOT.rglob(pattern) if "*" in pattern else [PROJECT_ROOT / pattern]:
            if path.exists():
                targets.add(path)

    for class_file in PROJECT_ROOT.rglob("*.class"):
        targets.add(class_file)
    for jar in PROJECT_ROOT.rglob("*.jar"):
        if "lib" not in str(jar) and "vendor" not in str(jar):
            targets.add(jar)

    for pattern in [".idea", "*.iml"]:
        for path in PROJECT_ROOT.glob(pattern):
            targets.add(path)

    return targets


def get_cpp_targets(include_all: bool = False) -> Set[Path]:
    """Get C/C++ build artifacts."""
    targets = set()

    for pattern in ["build", "cmake-build-*", "_build", "out"]:
        for path in PROJECT_ROOT.glob(pattern):
            if path.exists():
                targets.add(path)

    for ext in ["*.o", "*.obj", "*.a", "*.so", "*.dylib", "*.dll", "*.lib", "*.exe"]:
        for path in PROJECT_ROOT.rglob(ext):
            targets.add(path)

    for cmake in PROJECT_ROOT.rglob("CMakeFiles"):
        targets.add(cmake)
    for cmake in PROJECT_ROOT.rglob("CMakeCache.txt"):
        targets.add(cmake)

    compile_commands = PROJECT_ROOT / "compile_commands.json"
    if compile_commands.exists():
        targets.add(compile_commands)

    return targets


def get_go_targets(include_all: bool = False) -> Set[Path]:
    """Get Go build artifacts."""
    targets = set()

    if (PROJECT_ROOT / "go.mod").exists():
        for exe in PROJECT_ROOT.glob("*.exe"):
            targets.add(exe)

    if include_all:
        vendor = PROJECT_ROOT / "vendor"
        if vendor.exists():
            targets.add(vendor)

    for coverage in PROJECT_ROOT.rglob("*coverage*.out"):
        targets.add(coverage)

    return targets


def get_rust_targets(include_all: bool = False) -> Set[Path]:
    """Get Rust build artifacts."""
    targets = set()

    if (PROJECT_ROOT / "Cargo.toml").exists():
        target = PROJECT_ROOT / "target"
        if target.exists():
            targets.add(target)

    return targets


def get_csharp_targets(include_all: bool = False) -> Set[Path]:
    """Get C# build artifacts."""
    targets = set()

    for pattern in ["bin", "obj", "packages"]:
        for path in PROJECT_ROOT.rglob(pattern):
            targets.add(path)

    for pattern in [".vs", "*.user", "*.suo"]:
        for path in PROJECT_ROOT.glob(pattern):
            targets.add(path)

    return targets


def get_ruby_targets(include_all: bool = False) -> Set[Path]:
    """Get Ruby build artifacts."""
    targets = set()

    for pattern in [".bundle", "coverage", "doc", "pkg"]:
        path = PROJECT_ROOT / pattern
        if path.exists():
            targets.add(path)

    if include_all:
        vendor = PROJECT_ROOT / "vendor" / "bundle"
        if vendor.exists():
            targets.add(vendor)

    return targets


def get_php_targets(include_all: bool = False) -> Set[Path]:
    """Get PHP build artifacts."""
    targets = set()

    for pattern in [".phpunit.result.cache", ".php_cs.cache", ".php-cs-fixer.cache"]:
        path = PROJECT_ROOT / pattern
        if path.exists():
            targets.add(path)

    if include_all:
        vendor = PROJECT_ROOT / "vendor"
        if vendor.exists():
            targets.add(vendor)

    return targets


def get_kotlin_targets(include_all: bool = False) -> Set[Path]:
    """Get Kotlin build artifacts (uses Java patterns)."""
    return get_java_targets(include_all)


def get_swift_targets(include_all: bool = False) -> Set[Path]:
    """Get Swift build artifacts."""
    targets = set()

    for pattern in [".build", ".swiftpm", "DerivedData"]:
        path = PROJECT_ROOT / pattern
        if path.exists():
            targets.add(path)
        for path in PROJECT_ROOT.rglob(pattern):
            targets.add(path)

    return targets


def get_scala_targets(include_all: bool = False) -> Set[Path]:
    """Get Scala build artifacts."""
    targets = set()

    for pattern in ["target", "project/target", ".bloop", ".metals", ".bsp"]:
        path = PROJECT_ROOT / pattern
        if path.exists():
            targets.add(path)

    return targets


def get_dart_targets(include_all: bool = False) -> Set[Path]:
    """Get Dart/Flutter build artifacts."""
    targets = set()

    for pattern in ["build", ".dart_tool", ".packages"]:
        path = PROJECT_ROOT / pattern
        if path.exists():
            targets.add(path)
        for path in PROJECT_ROOT.rglob(pattern):
            targets.add(path)

    return targets


def get_elixir_targets(include_all: bool = False) -> Set[Path]:
    """Get Elixir build artifacts."""
    targets = set()

    for pattern in ["_build", "deps", "cover"]:
        path = PROJECT_ROOT / pattern
        if path.exists():
            targets.add(path)

    return targets


def get_haskell_targets(include_all: bool = False) -> Set[Path]:
    """Get Haskell build artifacts."""
    targets = set()

    for pattern in ["dist", "dist-newstyle", ".stack-work", ".cabal"]:
        path = PROJECT_ROOT / pattern
        if path.exists():
            targets.add(path)

    for hi in PROJECT_ROOT.rglob("*.hi"):
        targets.add(hi)
    for o in PROJECT_ROOT.rglob("*.o"):
        targets.add(o)

    return targets


def get_lua_targets(include_all: bool = False) -> Set[Path]:
    """Get Lua build artifacts."""
    targets = set()

    for luac in PROJECT_ROOT.rglob("*.luac"):
        targets.add(luac)

    if include_all:
        lua_modules = PROJECT_ROOT / "lua_modules"
        if lua_modules.exists():
            targets.add(lua_modules)

    return targets


def get_shell_targets(include_all: bool = False) -> Set[Path]:
    """Shell scripts don't have build artifacts."""
    return set()


def get_yaml_targets(include_all: bool = False) -> Set[Path]:
    """YAML doesn't have build artifacts."""
    return set()


def get_json_targets(include_all: bool = False) -> Set[Path]:
    """JSON doesn't have build artifacts."""
    return set()


def get_sql_targets(include_all: bool = False) -> Set[Path]:
    """SQL doesn't have build artifacts."""
    return set()


# =============================================================================
# Main
# =============================================================================

LANGUAGE_HANDLERS = {
    "python": get_python_targets,
    "typescript": get_typescript_targets,
    "java": get_java_targets,
    "cpp": get_cpp_targets,
    "go": get_go_targets,
    "rust": get_rust_targets,
    "csharp": get_csharp_targets,
    "ruby": get_ruby_targets,
    "php": get_php_targets,
    "kotlin": get_kotlin_targets,
    "swift": get_swift_targets,
    "scala": get_scala_targets,
    "dart": get_dart_targets,
    "elixir": get_elixir_targets,
    "haskell": get_haskell_targets,
    "lua": get_lua_targets,
    "shell": get_shell_targets,
    "yaml": get_yaml_targets,
    "json": get_json_targets,
    "sql": get_sql_targets,
}


def get_clean_targets(languages: List[str], include_all: bool = False) -> Set[Path]:
    """Get all paths to clean based on selected languages."""
    targets = set()

    for lang in languages:
        handler = LANGUAGE_HANDLERS.get(lang)
        if handler:
            targets.update(handler(include_all))

    return targets


def remove_path(path: Path, dry_run: bool = False, verbose: bool = False) -> bool:
    """Remove a file or directory."""
    if not path.exists():
        return True

    try:
        rel_path = path.relative_to(PROJECT_ROOT)
    except ValueError:
        rel_path = path

    if dry_run:
        if path.is_dir():
            log(f"Would remove directory: {rel_path}/", verbose)
        else:
            log(f"Would remove file: {rel_path}", verbose)
        return True

    try:
        if path.is_dir():
            shutil.rmtree(path)
            log(f"Removed directory: {rel_path}/", verbose)
        else:
            path.unlink()
            log(f"Removed file: {rel_path}", verbose)
        return True
    except Exception as e:
        log_error(f"Failed to remove {rel_path}: {e}")
        return False


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Clean build artifacts for 20 languages",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Supported Languages:
    Python, TypeScript, Java, C++, Go, Rust, C#, Ruby, PHP,
    Kotlin, Swift, Scala, Dart, Elixir, Haskell, Lua, Shell,
    YAML, JSON, SQL

Examples:
    python scripts/clean.py                    # Clean all languages
    python scripts/clean.py --dry-run          # Preview
    python scripts/clean.py --python           # Python only
    python scripts/clean.py --all              # Include vendored deps
        """,
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Clean everything including vendored dependencies",
    )
    for lang in LANGUAGE_HANDLERS.keys():
        parser.add_argument(
            f"--{lang}",
            action="store_true",
            help=f"Clean only {lang.capitalize()} artifacts",
        )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without deleting",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    all_languages = list(LANGUAGE_HANDLERS.keys())
    selected = [lang for lang in all_languages if getattr(args, lang, False)]
    if not selected:
        selected = all_languages

    if args.dry_run:
        print("=" * 60)
        print("DRY RUN - No files will be deleted")
        print("=" * 60)

    print(f"Cleaning: {len(selected)} languages")

    targets = get_clean_targets(selected, args.all)

    if not targets:
        log_success("Nothing to clean")
        return 0

    log(f"Found {len(targets)} items to clean", args.verbose or args.dry_run)

    failed = 0
    for target in sorted(targets):
        if not remove_path(target, args.dry_run, args.verbose or args.dry_run):
            failed += 1

    if args.dry_run:
        print("=" * 60)
        print(f"Would remove {len(targets)} items")
        print("=" * 60)
    elif failed > 0:
        log_error(f"Failed to remove {failed} items")
        return 1
    else:
        log_success(f"Cleaned {len(targets)} items")

    return 0


if __name__ == "__main__":
    sys.exit(main())
