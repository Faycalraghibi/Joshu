#!/usr/bin/env python3
"""
lint.py - Unified multi-language linter for Joshu monorepo.

Purpose:
    Runs linters for all detected languages in the project with
    clear pass/fail reporting. Supports 15+ languages.

Inputs:
    --fix             Auto-fix issues where possible
    --<language>      Run only linters for that language
    --verbose         Enable verbose output

Outputs:
    - Linting results to stdout
    - Exit code 0 on success, 1 on failure

Side Effects:
    - With --fix, modifies source files

Safety Considerations:
    - Preview mode by default (no changes)
    - --fix is explicit and required for modifications
    - Gracefully skips languages without tooling
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent
VSCODE_EXT_DIR = PROJECT_ROOT / "packages" / "vscode-joshu-companion"


def log(message: str, verbose: bool = True) -> None:
    """Print a log message if verbose mode is enabled."""
    if verbose:
        print(f"[lint] {message}")


def log_error(message: str) -> None:
    """Print an error message."""
    print(f"[lint] ERROR: {message}", file=sys.stderr)


def log_success(message: str) -> None:
    """Print a success message."""
    print(f"[lint] ✓ {message}")


def log_failure(message: str) -> None:
    """Print a failure message."""
    print(f"[lint] ✗ {message}")


def log_skip(message: str) -> None:
    """Print a skip message."""
    print(f"[lint] ○ {message}")


def has_tool(tool: str) -> bool:
    """Check if a tool is available in PATH."""
    return shutil.which(tool) is not None


def has_files(directory: Path, extensions: List[str]) -> bool:
    """Check if directory contains files with given extensions."""
    if not directory.exists():
        return False
    for ext in extensions:
        if list(directory.rglob(f"*{ext}")):
            return True
    return False


def run_command(
    cmd: List[str],
    cwd: Path,
    verbose: bool = False,
    shell: bool = False,
) -> Tuple[bool, str]:
    """Run a command and return (success, output)."""
    log(f"Running: {' '.join(cmd)}", verbose)

    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            shell=shell,
            timeout=300,
        )
        output = result.stdout + result.stderr
        success = result.returncode == 0
        return success, output
    except subprocess.TimeoutExpired:
        return False, "Command timed out after 5 minutes"
    except FileNotFoundError:
        return False, f"Command not found: {cmd[0]}"
    except Exception as e:
        return False, str(e)


# =============================================================================
# Language Checkers
# =============================================================================


def check_python(fix: bool = False, verbose: bool = False) -> List[Tuple[str, bool, str]]:
    """Run Python linters."""
    results = []
    if not has_files(PROJECT_ROOT / "src", [".py"]) and not has_files(PROJECT_ROOT, [".py"]):
        return results

    # Ruff
    if has_tool("ruff"):
        cmd = ["ruff", "check", "src/", "tests/"]
        if fix:
            cmd.append("--fix")
        success, output = run_command(cmd, PROJECT_ROOT, verbose)
        results.append(("Python: ruff check", success, output))

        cmd = ["ruff", "format", "--check" if not fix else "", "src/", "tests/"]
        cmd = [c for c in cmd if c]
        success, output = run_command(cmd, PROJECT_ROOT, verbose)
        results.append(("Python: ruff format", success, output))

    # Mypy
    if has_tool("mypy"):
        cmd = ["mypy", "src/", "--config-file", "mypy.ini"]
        success, output = run_command(cmd, PROJECT_ROOT, verbose)
        results.append(("Python: mypy", success, output))

    return results


def check_typescript(fix: bool = False, verbose: bool = False) -> List[Tuple[str, bool, str]]:
    """Run TypeScript linters."""
    results = []
    if not VSCODE_EXT_DIR.exists() or not has_tool("node"):
        return results

    if (VSCODE_EXT_DIR / "tsconfig.json").exists():
        cmd = ["npx", "tsc", "--noEmit"]
        success, output = run_command(cmd, VSCODE_EXT_DIR, verbose, shell=True)
        results.append(("TypeScript: tsc", success, output))

    if has_tool("eslint") or (VSCODE_EXT_DIR / "node_modules" / ".bin" / "eslint").exists():
        cmd = ["npx", "eslint", "src/"]
        if fix:
            cmd.append("--fix")
        success, output = run_command(cmd, VSCODE_EXT_DIR, verbose, shell=True)
        if "not found" not in output.lower():
            results.append(("TypeScript: eslint", success, output))

    return results


def check_java(fix: bool = False, verbose: bool = False) -> List[Tuple[str, bool, str]]:
    """Run Java linters."""
    results = []
    if not has_files(PROJECT_ROOT, [".java"]):
        return results

    if has_tool("checkstyle"):
        cmd = ["checkstyle", "-c", "/google_checks.xml", "src/"]
        success, output = run_command(cmd, PROJECT_ROOT, verbose)
        results.append(("Java: checkstyle", success, output))

    if has_tool("spotbugs") and (PROJECT_ROOT / "target" / "classes").exists():
        cmd = ["spotbugs", "-textui", "target/classes"]
        success, output = run_command(cmd, PROJECT_ROOT, verbose)
        results.append(("Java: spotbugs", success, output))

    return results


def check_cpp(fix: bool = False, verbose: bool = False) -> List[Tuple[str, bool, str]]:
    """Run C/C++ linters."""
    results = []
    if not has_files(PROJECT_ROOT, [".c", ".cpp", ".cc", ".h", ".hpp"]):
        return results

    # clang-format
    if has_tool("clang-format"):
        cpp_files = (
            list(PROJECT_ROOT.rglob("*.cpp"))
            + list(PROJECT_ROOT.rglob("*.c"))
            + list(PROJECT_ROOT.rglob("*.h"))
        )
        if cpp_files:
            file_args = [str(f) for f in cpp_files[:50]]
            if fix:
                cmd = ["clang-format", "-i"] + file_args
            else:
                cmd = ["clang-format", "--dry-run", "--Werror"] + file_args
            success, output = run_command(cmd, PROJECT_ROOT, verbose)
            results.append(("C++: clang-format", success, output))

    # cppcheck
    if has_tool("cppcheck"):
        cmd = ["cppcheck", "--enable=warning,style", "--error-exitcode=1", "src/"]
        success, output = run_command(cmd, PROJECT_ROOT, verbose)
        results.append(("C++: cppcheck", success, output))

    return results


def check_go(fix: bool = False, verbose: bool = False) -> List[Tuple[str, bool, str]]:
    """Run Go linters."""
    results = []
    if not (PROJECT_ROOT / "go.mod").exists() and not has_files(PROJECT_ROOT, [".go"]):
        return results

    if not has_tool("go"):
        return results

    # go vet
    cmd = ["go", "vet", "./..."]
    success, output = run_command(cmd, PROJECT_ROOT, verbose)
    results.append(("Go: go vet", success, output))

    # gofmt
    cmd = ["gofmt", "-l", "."] if not fix else ["gofmt", "-w", "."]
    success, output = run_command(cmd, PROJECT_ROOT, verbose)
    if not fix and output.strip():
        success = False
    results.append(("Go: gofmt", success, output))

    # golangci-lint
    if has_tool("golangci-lint"):
        cmd = ["golangci-lint", "run"]
        if fix:
            cmd.append("--fix")
        success, output = run_command(cmd, PROJECT_ROOT, verbose)
        results.append(("Go: golangci-lint", success, output))

    return results


def check_rust(fix: bool = False, verbose: bool = False) -> List[Tuple[str, bool, str]]:
    """Run Rust linters."""
    results = []
    if not (PROJECT_ROOT / "Cargo.toml").exists():
        return results

    if not has_tool("cargo"):
        return results

    # cargo check
    cmd = ["cargo", "check"]
    success, output = run_command(cmd, PROJECT_ROOT, verbose)
    results.append(("Rust: cargo check", success, output))

    # clippy
    cmd = ["cargo", "clippy", "--", "-D", "warnings"]
    if fix:
        cmd = ["cargo", "clippy", "--fix", "--allow-dirty", "--", "-D", "warnings"]
    success, output = run_command(cmd, PROJECT_ROOT, verbose)
    results.append(("Rust: clippy", success, output))

    # cargo fmt
    cmd = ["cargo", "fmt", "--check"] if not fix else ["cargo", "fmt"]
    success, output = run_command(cmd, PROJECT_ROOT, verbose)
    results.append(("Rust: cargo fmt", success, output))

    return results


def check_csharp(fix: bool = False, verbose: bool = False) -> List[Tuple[str, bool, str]]:
    """Run C# linters."""
    results = []
    if not has_files(PROJECT_ROOT, [".cs", ".csproj"]):
        return results

    # dotnet format
    if has_tool("dotnet"):
        cmd = ["dotnet", "format", "--verify-no-changes"]
        if fix:
            cmd = ["dotnet", "format"]
        success, output = run_command(cmd, PROJECT_ROOT, verbose)
        results.append(("C#: dotnet format", success, output))

    return results


def check_ruby(fix: bool = False, verbose: bool = False) -> List[Tuple[str, bool, str]]:
    """Run Ruby linters."""
    results = []
    if not has_files(PROJECT_ROOT, [".rb"]):
        return results

    # RuboCop
    if has_tool("rubocop"):
        cmd = ["rubocop"]
        if fix:
            cmd.append("-A")
        success, output = run_command(cmd, PROJECT_ROOT, verbose)
        results.append(("Ruby: rubocop", success, output))

    return results


def check_php(fix: bool = False, verbose: bool = False) -> List[Tuple[str, bool, str]]:
    """Run PHP linters."""
    results = []
    if not has_files(PROJECT_ROOT, [".php"]):
        return results

    # PHP_CodeSniffer
    if has_tool("phpcs"):
        cmd = ["phpcs", "--standard=PSR12", "src/"]
        success, output = run_command(cmd, PROJECT_ROOT, verbose)
        results.append(("PHP: phpcs", success, output))

    # PHP-CS-Fixer
    if has_tool("php-cs-fixer") and fix:
        cmd = ["php-cs-fixer", "fix", "src/"]
        success, output = run_command(cmd, PROJECT_ROOT, verbose)
        results.append(("PHP: php-cs-fixer", success, output))

    # PHPStan
    if has_tool("phpstan"):
        cmd = ["phpstan", "analyse", "src/"]
        success, output = run_command(cmd, PROJECT_ROOT, verbose)
        results.append(("PHP: phpstan", success, output))

    return results


def check_kotlin(fix: bool = False, verbose: bool = False) -> List[Tuple[str, bool, str]]:
    """Run Kotlin linters."""
    results = []
    if not has_files(PROJECT_ROOT, [".kt", ".kts"]):
        return results

    # ktlint
    if has_tool("ktlint"):
        cmd = ["ktlint"]
        if fix:
            cmd.append("-F")
        success, output = run_command(cmd, PROJECT_ROOT, verbose)
        results.append(("Kotlin: ktlint", success, output))

    # detekt
    if has_tool("detekt"):
        cmd = ["detekt", "--input", "src/"]
        success, output = run_command(cmd, PROJECT_ROOT, verbose)
        results.append(("Kotlin: detekt", success, output))

    return results


def check_swift(fix: bool = False, verbose: bool = False) -> List[Tuple[str, bool, str]]:
    """Run Swift linters."""
    results = []
    if not has_files(PROJECT_ROOT, [".swift"]):
        return results

    # SwiftLint
    if has_tool("swiftlint"):
        cmd = ["swiftlint"]
        if fix:
            cmd.append("--fix")
        success, output = run_command(cmd, PROJECT_ROOT, verbose)
        results.append(("Swift: swiftlint", success, output))

    # swift-format
    if has_tool("swift-format"):
        cmd = ["swift-format", "lint", "-r", "Sources/"]
        if fix:
            cmd = ["swift-format", "-i", "-r", "Sources/"]
        success, output = run_command(cmd, PROJECT_ROOT, verbose)
        results.append(("Swift: swift-format", success, output))

    return results


def check_scala(fix: bool = False, verbose: bool = False) -> List[Tuple[str, bool, str]]:
    """Run Scala linters."""
    results = []
    if not has_files(PROJECT_ROOT, [".scala", ".sc"]):
        return results

    # Scalafmt
    if has_tool("scalafmt"):
        cmd = ["scalafmt", "--check"]
        if fix:
            cmd = ["scalafmt"]
        success, output = run_command(cmd, PROJECT_ROOT, verbose)
        results.append(("Scala: scalafmt", success, output))

    # Scalafix
    if has_tool("scalafix"):
        cmd = ["scalafix", "--check"]
        if fix:
            cmd = ["scalafix"]
        success, output = run_command(cmd, PROJECT_ROOT, verbose)
        results.append(("Scala: scalafix", success, output))

    return results


def check_dart(fix: bool = False, verbose: bool = False) -> List[Tuple[str, bool, str]]:
    """Run Dart/Flutter linters."""
    results = []
    if not has_files(PROJECT_ROOT, [".dart"]):
        return results

    if not has_tool("dart"):
        return results

    # dart analyze
    cmd = ["dart", "analyze"]
    success, output = run_command(cmd, PROJECT_ROOT, verbose)
    results.append(("Dart: dart analyze", success, output))

    # dart format
    cmd = ["dart", "format", "--set-exit-if-changed", "."]
    if fix:
        cmd = ["dart", "format", "."]
    success, output = run_command(cmd, PROJECT_ROOT, verbose)
    results.append(("Dart: dart format", success, output))

    return results


def check_elixir(fix: bool = False, verbose: bool = False) -> List[Tuple[str, bool, str]]:
    """Run Elixir linters."""
    results = []
    if not has_files(PROJECT_ROOT, [".ex", ".exs"]) and not (PROJECT_ROOT / "mix.exs").exists():
        return results

    if not has_tool("mix"):
        return results

    # mix format
    cmd = ["mix", "format", "--check-formatted"]
    if fix:
        cmd = ["mix", "format"]
    success, output = run_command(cmd, PROJECT_ROOT, verbose)
    results.append(("Elixir: mix format", success, output))

    # Credo
    cmd = ["mix", "credo"]
    success, output = run_command(cmd, PROJECT_ROOT, verbose)
    if "credo" in output.lower() and "not found" not in output.lower():
        results.append(("Elixir: credo", success, output))

    return results


def check_haskell(fix: bool = False, verbose: bool = False) -> List[Tuple[str, bool, str]]:
    """Run Haskell linters."""
    results = []
    if not has_files(PROJECT_ROOT, [".hs", ".lhs"]):
        return results

    # hlint
    if has_tool("hlint"):
        cmd = ["hlint", "."]
        success, output = run_command(cmd, PROJECT_ROOT, verbose)
        results.append(("Haskell: hlint", success, output))

    # ormolu
    if has_tool("ormolu"):
        cmd = ["ormolu", "--mode", "check", "."]
        if fix:
            cmd = ["ormolu", "--mode", "inplace", "."]
        success, output = run_command(cmd, PROJECT_ROOT, verbose)
        results.append(("Haskell: ormolu", success, output))

    return results


def check_lua(fix: bool = False, verbose: bool = False) -> List[Tuple[str, bool, str]]:
    """Run Lua linters."""
    results = []
    if not has_files(PROJECT_ROOT, [".lua"]):
        return results

    # luacheck
    if has_tool("luacheck"):
        cmd = ["luacheck", "."]
        success, output = run_command(cmd, PROJECT_ROOT, verbose)
        results.append(("Lua: luacheck", success, output))

    # stylua
    if has_tool("stylua"):
        cmd = ["stylua", "--check", "."]
        if fix:
            cmd = ["stylua", "."]
        success, output = run_command(cmd, PROJECT_ROOT, verbose)
        results.append(("Lua: stylua", success, output))

    return results


def check_shell(fix: bool = False, verbose: bool = False) -> List[Tuple[str, bool, str]]:
    """Run Shell script linters."""
    results = []
    if not has_files(PROJECT_ROOT, [".sh", ".bash"]):
        return results

    # shellcheck
    if has_tool("shellcheck"):
        sh_files = list(PROJECT_ROOT.rglob("*.sh"))
        if sh_files:
            cmd = ["shellcheck"] + [str(f) for f in sh_files[:50]]
            success, output = run_command(cmd, PROJECT_ROOT, verbose)
            results.append(("Shell: shellcheck", success, output))

    # shfmt
    if has_tool("shfmt"):
        cmd = ["shfmt", "-d", "."]
        if fix:
            cmd = ["shfmt", "-w", "."]
        success, output = run_command(cmd, PROJECT_ROOT, verbose)
        results.append(("Shell: shfmt", success, output))

    return results


def check_yaml(fix: bool = False, verbose: bool = False) -> List[Tuple[str, bool, str]]:
    """Run YAML linters."""
    results = []
    if not has_files(PROJECT_ROOT, [".yaml", ".yml"]):
        return results

    # yamllint
    if has_tool("yamllint"):
        cmd = ["yamllint", "."]
        success, output = run_command(cmd, PROJECT_ROOT, verbose)
        results.append(("YAML: yamllint", success, output))

    return results


def check_json(fix: bool = False, verbose: bool = False) -> List[Tuple[str, bool, str]]:
    """Run JSON linters."""
    results = []
    if not has_files(PROJECT_ROOT, [".json"]):
        return results

    # jsonlint
    if has_tool("jsonlint"):
        json_files = list(PROJECT_ROOT.rglob("*.json"))
        for jf in json_files[:20]:
            cmd = ["jsonlint", "-q", str(jf)]
            success, output = run_command(cmd, PROJECT_ROOT, verbose)
            if not success:
                results.append((f"JSON: {jf.name}", success, output))

    return results


def check_sql(fix: bool = False, verbose: bool = False) -> List[Tuple[str, bool, str]]:
    """Run SQL linters."""
    results = []
    if not has_files(PROJECT_ROOT, [".sql"]):
        return results

    # sqlfluff
    if has_tool("sqlfluff"):
        cmd = ["sqlfluff", "lint", "."]
        if fix:
            cmd = ["sqlfluff", "fix", "."]
        success, output = run_command(cmd, PROJECT_ROOT, verbose)
        results.append(("SQL: sqlfluff", success, output))

    return results


# =============================================================================
# Main
# =============================================================================

LANGUAGE_CHECKERS = {
    "python": check_python,
    "typescript": check_typescript,
    "java": check_java,
    "cpp": check_cpp,
    "go": check_go,
    "rust": check_rust,
    "csharp": check_csharp,
    "ruby": check_ruby,
    "php": check_php,
    "kotlin": check_kotlin,
    "swift": check_swift,
    "scala": check_scala,
    "dart": check_dart,
    "elixir": check_elixir,
    "haskell": check_haskell,
    "lua": check_lua,
    "shell": check_shell,
    "yaml": check_yaml,
    "json": check_json,
    "sql": check_sql,
}


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Unified multi-language linter (20 languages)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Supported Languages & Tools:
    Python      ruff, mypy
    TypeScript  tsc, eslint
    Java        checkstyle, spotbugs
    C++         clang-format, clang-tidy, cppcheck
    Go          go vet, gofmt, golangci-lint
    Rust        cargo check, clippy, cargo fmt
    C#          dotnet format
    Ruby        rubocop
    PHP         phpcs, php-cs-fixer, phpstan
    Kotlin      ktlint, detekt
    Swift       swiftlint, swift-format
    Scala       scalafmt, scalafix
    Dart        dart analyze, dart format
    Elixir      mix format, credo
    Haskell     hlint, ormolu
    Lua         luacheck, stylua
    Shell       shellcheck, shfmt
    YAML        yamllint
    JSON        jsonlint
    SQL         sqlfluff

Examples:
    python scripts/lint.py                # Check all detected languages
    python scripts/lint.py --fix          # Fix auto-fixable issues
    python scripts/lint.py --python       # Python only
    python scripts/lint.py --rust --go    # Rust and Go only
        """,
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Auto-fix issues where possible",
    )
    # Language filters
    for lang in LANGUAGE_CHECKERS.keys():
        parser.add_argument(
            f"--{lang}",
            action="store_true",
            help=f"Run only {lang.capitalize()} linters",
        )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    # Determine which languages to check
    selected = [lang for lang in LANGUAGE_CHECKERS if getattr(args, lang, False)]
    if not selected:
        selected = list(LANGUAGE_CHECKERS.keys())

    print("=" * 60)
    print("Joshu Multi-Language Linter (20 Languages)")
    print("=" * 60)

    all_results: List[Tuple[str, bool, str]] = []

    for lang in selected:
        checker = LANGUAGE_CHECKERS[lang]
        results = checker(args.fix, args.verbose)

        for name, success, output in results:
            all_results.append((name, success, output))
            if success:
                log_success(name + " passed")
            else:
                log_failure(name + " failed")
                if args.verbose:
                    print(output[:1000])

    # Summary
    print("=" * 60)

    if not all_results:
        log_skip("No linters were run (no supported languages detected or no tools installed)")
        return 0

    passed = sum(1 for _, success, _ in all_results if success)
    total = len(all_results)

    if passed == total:
        log_success(f"All {total} checks passed!")
        return 0
    else:
        log_failure(f"{passed}/{total} checks passed")

        # Show failed outputs
        for name, success, output in all_results:
            if not success and output.strip():
                print(f"\n--- {name} output ---")
                print(output[:2000])
                if len(output) > 2000:
                    print("... (truncated)")

        return 1


if __name__ == "__main__":
    sys.exit(main())
