#!/usr/bin/env python3
"""
pre_commit.py - Multi-language pre-commit hook orchestrator.

Purpose:
    Runs linting and validation on staged Git files for all supported
    languages (20+), suitable for use as a pre-commit hook.

Inputs:
    --all             Check all files, not just staged
    --fix             Auto-fix issues where possible
    --verbose         Enable verbose output

Outputs:
    - Validation results to stdout
    - Exit code 0 on success, 1 on failure

Side Effects:
    - With --fix, modifies source files

Safety Considerations:
    - Only validates staged files (by default)
    - Does not modify files without --fix
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent

# Comprehensive extension to language mapping
EXTENSION_MAP = {
    # Python
    ".py": "python",
    ".pyi": "python",
    ".pyx": "python",
    # TypeScript/JavaScript
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    # Java/JVM
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".scala": "scala",
    ".sc": "scala",
    ".groovy": "groovy",
    # C/C++
    ".c": "cpp",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".h": "cpp",
    ".hpp": "cpp",
    ".hxx": "cpp",
    # Systems
    ".go": "go",
    ".rs": "rust",
    ".zig": "zig",
    # .NET
    ".cs": "csharp",
    ".fs": "fsharp",
    ".vb": "vb",
    # Scripting
    ".rb": "ruby",
    ".php": "php",
    ".pl": "perl",
    ".pm": "perl",
    ".lua": "lua",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    # Functional
    ".hs": "haskell",
    ".lhs": "haskell",
    ".ex": "elixir",
    ".exs": "elixir",
    ".erl": "erlang",
    ".hrl": "erlang",
    ".clj": "clojure",
    ".cljs": "clojure",
    ".cljc": "clojure",
    ".ml": "ocaml",
    ".mli": "ocaml",
    # Mobile/UI
    ".swift": "swift",
    ".dart": "dart",
    ".m": "objc",
    ".mm": "objc",
    # Data/Config
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".toml": "toml",
    ".xml": "xml",
    ".sql": "sql",
    # Web
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".sass": "sass",
    ".less": "less",
    # Other
    ".r": "r",
    ".R": "r",
    ".jl": "julia",
    ".nim": "nim",
    ".v": "v",
    ".asm": "asm",
    ".s": "asm",
}


def log(message: str, verbose: bool = True) -> None:
    if verbose:
        print(f"[pre_commit] {message}")


def log_error(message: str) -> None:
    print(f"[pre_commit] ERROR: {message}", file=sys.stderr)


def log_success(message: str) -> None:
    print(f"[pre_commit] ✓ {message}")


def log_failure(message: str) -> None:
    print(f"[pre_commit] ✗ {message}")


def log_skip(message: str) -> None:
    print(f"[pre_commit] ○ {message}")


def has_tool(tool: str) -> bool:
    return shutil.which(tool) is not None


def get_staged_files() -> Dict[str, List[Path]]:
    """Get staged files grouped by language."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return {}

        files_by_lang: Dict[str, List[Path]] = {}

        for line in result.stdout.splitlines():
            path = PROJECT_ROOT / line.strip()
            ext = path.suffix.lower()
            lang = EXTENSION_MAP.get(ext)

            if lang:
                if lang not in files_by_lang:
                    files_by_lang[lang] = []
                files_by_lang[lang].append(path)

        return files_by_lang
    except Exception:
        return {}


def run_command(
    cmd: List[str], cwd: Path = PROJECT_ROOT, verbose: bool = False
) -> Tuple[bool, str]:
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120)
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)


# =============================================================================
# Language Checkers
# =============================================================================


def check_python_files(files: List[Path], fix: bool, verbose: bool) -> List[Tuple[str, bool]]:
    results = []
    if not files or not has_tool("ruff"):
        return results

    file_args = [str(f) for f in files]
    cmd = ["ruff", "check"] + file_args + (["--fix"] if fix else [])
    success, _ = run_command(cmd, verbose=verbose)
    results.append(("Python: ruff check", success))

    cmd = ["ruff", "format"] + ([] if fix else ["--check"]) + file_args
    success, _ = run_command(cmd, verbose=verbose)
    results.append(("Python: ruff format", success))

    return results


def check_typescript_files(files: List[Path], fix: bool, verbose: bool) -> List[Tuple[str, bool]]:
    results = []
    if not files or not has_tool("node"):
        return results

    # Project-level TypeScript check
    vscode_ext = PROJECT_ROOT / "packages" / "vscode-joshu-companion"
    if (vscode_ext / "tsconfig.json").exists():
        cmd = ["npx", "tsc", "--noEmit"]
        success, _ = run_command(cmd, cwd=vscode_ext, verbose=verbose)
        results.append(("TypeScript: tsc", success))

    return results


def check_go_files(files: List[Path], fix: bool, verbose: bool) -> List[Tuple[str, bool]]:
    results = []
    if not files or not has_tool("go"):
        return results

    cmd = ["gofmt", "-l"] + [str(f) for f in files]
    if fix:
        cmd = ["gofmt", "-w"] + [str(f) for f in files]
    success, output = run_command(cmd, verbose=verbose)
    if not fix and output.strip():
        success = False
    results.append(("Go: gofmt", success))

    return results


def check_rust_files(files: List[Path], fix: bool, verbose: bool) -> List[Tuple[str, bool]]:
    results = []
    if not files or not has_tool("cargo"):
        return results

    if (PROJECT_ROOT / "Cargo.toml").exists():
        cmd = ["cargo", "fmt", "--check"] if not fix else ["cargo", "fmt"]
        success, _ = run_command(cmd, verbose=verbose)
        results.append(("Rust: cargo fmt", success))

    return results


def check_cpp_files(files: List[Path], fix: bool, verbose: bool) -> List[Tuple[str, bool]]:
    results = []
    cpp_files = [f for f in files if f.suffix in [".c", ".cpp", ".cc", ".h", ".hpp"]]
    if not cpp_files:
        return results

    if has_tool("clang-format"):
        file_args = [str(f) for f in cpp_files[:50]]
        cmd = ["clang-format", "-i" if fix else "--dry-run", "--Werror"] + file_args
        if fix:
            cmd = ["clang-format", "-i"] + file_args
        success, _ = run_command(cmd, verbose=verbose)
        results.append(("C++: clang-format", success))

    return results


def check_java_files(files: List[Path], fix: bool, verbose: bool) -> List[Tuple[str, bool]]:
    results = []
    if not files:
        return results

    if has_tool("checkstyle"):
        file_args = [str(f) for f in files]
        cmd = ["checkstyle", "-c", "/google_checks.xml"] + file_args
        success, _ = run_command(cmd, verbose=verbose)
        results.append(("Java: checkstyle", success))

    return results


def check_ruby_files(files: List[Path], fix: bool, verbose: bool) -> List[Tuple[str, bool]]:
    results = []
    if not files or not has_tool("rubocop"):
        return results

    cmd = ["rubocop"] + (["-A"] if fix else []) + [str(f) for f in files]
    success, _ = run_command(cmd, verbose=verbose)
    results.append(("Ruby: rubocop", success))

    return results


def check_php_files(files: List[Path], fix: bool, verbose: bool) -> List[Tuple[str, bool]]:
    results = []
    if not files:
        return results

    if has_tool("phpcs"):
        cmd = ["phpcs", "--standard=PSR12"] + [str(f) for f in files]
        success, _ = run_command(cmd, verbose=verbose)
        results.append(("PHP: phpcs", success))

    return results


def check_shell_files(files: List[Path], fix: bool, verbose: bool) -> List[Tuple[str, bool]]:
    results = []
    if not files:
        return results

    if has_tool("shellcheck"):
        file_args = [str(f) for f in files]
        cmd = ["shellcheck"] + file_args
        success, _ = run_command(cmd, verbose=verbose)
        results.append(("Shell: shellcheck", success))

    return results


def check_yaml_files(files: List[Path], fix: bool, verbose: bool) -> List[Tuple[str, bool]]:
    results = []
    if not files or not has_tool("yamllint"):
        return results

    cmd = ["yamllint"] + [str(f) for f in files]
    success, _ = run_command(cmd, verbose=verbose)
    results.append(("YAML: yamllint", success))

    return results


def check_swift_files(files: List[Path], fix: bool, verbose: bool) -> List[Tuple[str, bool]]:
    results = []
    if not files or not has_tool("swiftlint"):
        return results

    cmd = ["swiftlint"] + (["--fix"] if fix else [])
    success, _ = run_command(cmd, verbose=verbose)
    results.append(("Swift: swiftlint", success))

    return results


def check_dart_files(files: List[Path], fix: bool, verbose: bool) -> List[Tuple[str, bool]]:
    results = []
    if not files or not has_tool("dart"):
        return results

    cmd = ["dart", "format", "--set-exit-if-changed"] + [str(f) for f in files]
    if fix:
        cmd = ["dart", "format"] + [str(f) for f in files]
    success, _ = run_command(cmd, verbose=verbose)
    results.append(("Dart: dart format", success))

    return results


def check_kotlin_files(files: List[Path], fix: bool, verbose: bool) -> List[Tuple[str, bool]]:
    results = []
    if not files or not has_tool("ktlint"):
        return results

    cmd = ["ktlint"] + (["-F"] if fix else []) + [str(f) for f in files]
    success, _ = run_command(cmd, verbose=verbose)
    results.append(("Kotlin: ktlint", success))

    return results


def check_csharp_files(files: List[Path], fix: bool, verbose: bool) -> List[Tuple[str, bool]]:
    results = []
    if not files or not has_tool("dotnet"):
        return results

    cmd = ["dotnet", "format", "--verify-no-changes"]
    if fix:
        cmd = ["dotnet", "format"]
    success, _ = run_command(cmd, verbose=verbose)
    results.append(("C#: dotnet format", success))

    return results


# =============================================================================
# Main
# =============================================================================

LANGUAGE_CHECKERS = {
    "python": check_python_files,
    "typescript": check_typescript_files,
    "javascript": check_typescript_files,
    "java": check_java_files,
    "cpp": check_cpp_files,
    "go": check_go_files,
    "rust": check_rust_files,
    "csharp": check_csharp_files,
    "ruby": check_ruby_files,
    "php": check_php_files,
    "kotlin": check_kotlin_files,
    "swift": check_swift_files,
    "dart": check_dart_files,
    "shell": check_shell_files,
    "yaml": check_yaml_files,
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Multi-language pre-commit hook (20+ languages)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Supported Languages:
    Python, TypeScript, JavaScript, Java, C++, Go, Rust, C#, Ruby, PHP,
    Kotlin, Swift, Dart, Shell, YAML, and file detection for 30+ extensions

Examples:
    python scripts/pre_commit.py              # Check staged files
    python scripts/pre_commit.py --all        # Check all files
    python scripts/pre_commit.py --fix        # Auto-fix issues

To install as a git hook:
    echo 'python scripts/pre_commit.py' > .git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit
        """,
    )
    parser.add_argument("--all", action="store_true", help="Check all files")
    parser.add_argument("--fix", action="store_true", help="Auto-fix issues")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    print("=" * 60)
    print("Multi-Language Pre-commit Checks")
    print("=" * 60)

    if args.all:
        log("Checking all files via lint.py...", True)
        lint_script = SCRIPTS_DIR / "lint.py"
        if lint_script.exists():
            cmd = [sys.executable, str(lint_script)] + (["--fix"] if args.fix else [])
            result = subprocess.run(cmd, cwd=PROJECT_ROOT)
            return result.returncode
        log_error("lint.py not found")
        return 1

    files_by_lang = get_staged_files()

    if not files_by_lang:
        log_success("No staged files to check")
        return 0

    total_files = sum(len(files) for files in files_by_lang.values())
    log(f"Found {total_files} staged files in {len(files_by_lang)} language(s)", True)

    all_results: List[Tuple[str, bool]] = []

    for lang, files in files_by_lang.items():
        checker = LANGUAGE_CHECKERS.get(lang)
        if checker:
            results = checker(files, args.fix, args.verbose)
            all_results.extend(results)

    print("=" * 60)

    passed = sum(1 for _, success in all_results if success)
    failed = sum(1 for _, success in all_results if not success)

    for name, success in all_results:
        if success:
            log_success(f"{name} passed")
        else:
            log_failure(f"{name} failed")

    print("=" * 60)

    if failed == 0:
        if passed == 0:
            log_skip("No checks were run")
        else:
            log_success(f"All {passed} checks passed!")
        return 0

    log_failure(f"{failed}/{passed + failed} checks failed")
    print("\nTip: Run 'python scripts/lint.py --fix' to auto-fix issues")
    return 1


if __name__ == "__main__":
    sys.exit(main())
