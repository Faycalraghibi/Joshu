#!/usr/bin/env python3
"""
build.py - Multi-language build orchestrator for Joshu monorepo.

Purpose:
    Orchestrates the complete build process for projects in multiple
    languages: 15+ languages supported with auto-detection.

Inputs:
    --<language>      Build only that language's components
    --skip-codegen    Skip code generation steps
    --skip-deps       Skip dependency installation
    --verbose         Enable verbose output

Outputs:
    - Built packages in dist/ (or language-specific directories)
    - .last_build marker file with timestamp

Side Effects:
    - Installs missing dependencies if detected
    - Creates/updates build marker files

Safety Considerations:
    - All operations are idempotent
    - Build can be interrupted and resumed safely
"""

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent


def log(message: str, verbose: bool = True) -> None:
    if verbose:
        print(f"[build] {message}")


def log_error(message: str) -> None:
    print(f"[build] ERROR: {message}", file=sys.stderr)


def log_success(message: str) -> None:
    print(f"[build] ✓ {message}")


def log_skip(message: str) -> None:
    print(f"[build] ○ {message}")


def has_tool(tool: str) -> bool:
    return shutil.which(tool) is not None


def has_files(directory: Path, extensions: List[str]) -> bool:
    if not directory.exists():
        return False
    for ext in extensions:
        if list(directory.rglob(f"*{ext}")):
            return True
    return False


def run_command(
    cmd: List[str], cwd: Path = PROJECT_ROOT, verbose: bool = False, shell: bool = False
) -> Tuple[bool, str]:
    log(f"Running: {' '.join(cmd)}", verbose)
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, shell=shell, timeout=600
        )
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)


# =============================================================================
# Language Builders
# =============================================================================


def build_python(skip_deps: bool, skip_codegen: bool, verbose: bool) -> List[Tuple[str, bool]]:
    results = []
    if not has_files(PROJECT_ROOT / "src", [".py"]):
        return results

    if sys.version_info < (3, 10):
        log_error("Python 3.10+ required")
        return [("Python: version check", False)]

    log_success(f"Python {sys.version_info.major}.{sys.version_info.minor}")

    if not skip_deps:
        try:
            import joshu  # noqa
        except ImportError:
            success, output = run_command(
                [sys.executable, "-m", "pip", "install", "-e", ".[dev]"], verbose=verbose
            )
            results.append(("Python: pip install", success))
            if not success:
                return results

    if not skip_codegen:
        gen_script = SCRIPTS_DIR / "generate_git_info.py"
        if gen_script.exists():
            success, _ = run_command([sys.executable, str(gen_script)], verbose=verbose)
            results.append(("Python: codegen", success))

    build_script = SCRIPTS_DIR / "build_package.py"
    if build_script.exists():
        success, _ = run_command(
            [sys.executable, str(build_script), "--package", "joshu"], verbose=verbose
        )
        results.append(("Python: build package", success))

    return results


def build_typescript(skip_deps: bool, verbose: bool) -> List[Tuple[str, bool]]:
    results = []
    vscode_ext = PROJECT_ROOT / "packages" / "vscode-joshu-companion"
    if not vscode_ext.exists() or not has_tool("node"):
        return results

    if not skip_deps and not (vscode_ext / "node_modules").exists():
        success, _ = run_command(["npm", "install"], cwd=vscode_ext, verbose=verbose, shell=True)
        results.append(("TypeScript: npm install", success))
        if not success:
            return results

    if (vscode_ext / "esbuild.js").exists():
        success, _ = run_command(["node", "esbuild.js"], cwd=vscode_ext, verbose=verbose)
        results.append(("TypeScript: esbuild", success))
    elif (vscode_ext / "tsconfig.json").exists():
        success, _ = run_command(["npx", "tsc"], cwd=vscode_ext, verbose=verbose, shell=True)
        results.append(("TypeScript: tsc", success))

    return results


def build_java(skip_deps: bool, verbose: bool) -> List[Tuple[str, bool]]:
    results = []

    if (PROJECT_ROOT / "pom.xml").exists() and has_tool("mvn"):
        cmd = (
            ["mvn", "clean", "package", "-DskipTests"]
            if not skip_deps
            else ["mvn", "package", "-DskipTests"]
        )
        success, _ = run_command(cmd, verbose=verbose)
        results.append(("Java: maven", success))
    elif (PROJECT_ROOT / "build.gradle").exists() and has_tool("gradle"):
        cmd = (
            ["gradle", "clean", "build", "-x", "test"]
            if not skip_deps
            else ["gradle", "build", "-x", "test"]
        )
        success, _ = run_command(cmd, verbose=verbose)
        results.append(("Java: gradle", success))

    return results


def build_cpp(verbose: bool) -> List[Tuple[str, bool]]:
    results = []

    if (PROJECT_ROOT / "CMakeLists.txt").exists() and has_tool("cmake"):
        build_dir = PROJECT_ROOT / "build"
        build_dir.mkdir(exist_ok=True)
        success, _ = run_command(["cmake", ".."], cwd=build_dir, verbose=verbose)
        if success:
            success, _ = run_command(["cmake", "--build", "."], cwd=build_dir, verbose=verbose)
        results.append(("C++: cmake", success))
    elif (PROJECT_ROOT / "Makefile").exists() and has_tool("make"):
        success, _ = run_command(["make"], verbose=verbose)
        results.append(("C++: make", success))

    return results


def build_go(verbose: bool) -> List[Tuple[str, bool]]:
    results = []
    if not (PROJECT_ROOT / "go.mod").exists() or not has_tool("go"):
        return results

    success, _ = run_command(["go", "build", "./..."], verbose=verbose)
    results.append(("Go: go build", success))
    return results


def build_rust(verbose: bool) -> List[Tuple[str, bool]]:
    results = []
    if not (PROJECT_ROOT / "Cargo.toml").exists() or not has_tool("cargo"):
        return results

    success, _ = run_command(["cargo", "build", "--release"], verbose=verbose)
    results.append(("Rust: cargo build", success))
    return results


def build_csharp(skip_deps: bool, verbose: bool) -> List[Tuple[str, bool]]:
    results = []
    sln_files = list(PROJECT_ROOT.glob("*.sln"))
    csproj_files = list(PROJECT_ROOT.rglob("*.csproj"))

    if not (sln_files or csproj_files) or not has_tool("dotnet"):
        return results

    if not skip_deps:
        success, _ = run_command(["dotnet", "restore"], verbose=verbose)
        results.append(("C#: dotnet restore", success))
        if not success:
            return results

    success, _ = run_command(["dotnet", "build", "-c", "Release"], verbose=verbose)
    results.append(("C#: dotnet build", success))
    return results


def build_ruby(skip_deps: bool, verbose: bool) -> List[Tuple[str, bool]]:
    results = []
    if not (PROJECT_ROOT / "Gemfile").exists() or not has_tool("bundle"):
        return results

    if not skip_deps:
        success, _ = run_command(["bundle", "install"], verbose=verbose)
        results.append(("Ruby: bundle install", success))

    return results


def build_php(skip_deps: bool, verbose: bool) -> List[Tuple[str, bool]]:
    results = []
    if not (PROJECT_ROOT / "composer.json").exists() or not has_tool("composer"):
        return results

    if not skip_deps:
        success, _ = run_command(["composer", "install"], verbose=verbose)
        results.append(("PHP: composer install", success))

    return results


def build_swift(verbose: bool) -> List[Tuple[str, bool]]:
    results = []
    if not (PROJECT_ROOT / "Package.swift").exists() or not has_tool("swift"):
        return results

    success, _ = run_command(["swift", "build", "-c", "release"], verbose=verbose)
    results.append(("Swift: swift build", success))
    return results


def build_dart(skip_deps: bool, verbose: bool) -> List[Tuple[str, bool]]:
    results = []
    if not (PROJECT_ROOT / "pubspec.yaml").exists() or not has_tool("dart"):
        return results

    if not skip_deps:
        success, _ = run_command(["dart", "pub", "get"], verbose=verbose)
        results.append(("Dart: pub get", success))

    return results


def build_elixir(skip_deps: bool, verbose: bool) -> List[Tuple[str, bool]]:
    results = []
    if not (PROJECT_ROOT / "mix.exs").exists() or not has_tool("mix"):
        return results

    if not skip_deps:
        success, _ = run_command(["mix", "deps.get"], verbose=verbose)
        results.append(("Elixir: mix deps.get", success))

    success, _ = run_command(["mix", "compile"], verbose=verbose)
    results.append(("Elixir: mix compile", success))
    return results


def build_haskell(verbose: bool) -> List[Tuple[str, bool]]:
    results = []

    if (PROJECT_ROOT / "stack.yaml").exists() and has_tool("stack"):
        success, _ = run_command(["stack", "build"], verbose=verbose)
        results.append(("Haskell: stack build", success))
    elif (PROJECT_ROOT / "*.cabal").exists() and has_tool("cabal"):
        success, _ = run_command(["cabal", "build"], verbose=verbose)
        results.append(("Haskell: cabal build", success))

    return results


def build_scala(skip_deps: bool, verbose: bool) -> List[Tuple[str, bool]]:
    results = []
    if not (PROJECT_ROOT / "build.sbt").exists() or not has_tool("sbt"):
        return results

    success, _ = run_command(["sbt", "compile"], verbose=verbose)
    results.append(("Scala: sbt compile", success))
    return results


def build_kotlin(skip_deps: bool, verbose: bool) -> List[Tuple[str, bool]]:
    # Uses Gradle (same as Java)
    return build_java(skip_deps, verbose)


# =============================================================================
# Main
# =============================================================================

LANGUAGE_BUILDERS = {
    "python": lambda sd, sc, v: build_python(sd, sc, v),
    "typescript": lambda sd, sc, v: build_typescript(sd, v),
    "java": lambda sd, sc, v: build_java(sd, v),
    "cpp": lambda sd, sc, v: build_cpp(v),
    "go": lambda sd, sc, v: build_go(v),
    "rust": lambda sd, sc, v: build_rust(v),
    "csharp": lambda sd, sc, v: build_csharp(sd, v),
    "ruby": lambda sd, sc, v: build_ruby(sd, v),
    "php": lambda sd, sc, v: build_php(sd, v),
    "swift": lambda sd, sc, v: build_swift(v),
    "dart": lambda sd, sc, v: build_dart(sd, v),
    "elixir": lambda sd, sc, v: build_elixir(sd, v),
    "haskell": lambda sd, sc, v: build_haskell(v),
    "scala": lambda sd, sc, v: build_scala(sd, v),
    "kotlin": lambda sd, sc, v: build_kotlin(sd, v),
}


def create_build_marker(verbose: bool = False) -> None:
    marker_path = PROJECT_ROOT / ".last_build"
    build_info = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "platform": sys.platform,
    }
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, capture_output=True, text=True
        )
        if result.returncode == 0:
            build_info["git_commit"] = result.stdout.strip()
    except Exception:
        pass
    marker_path.write_text(json.dumps(build_info, indent=2))
    log("Created build marker", verbose)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Multi-language build orchestrator (15 languages)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Supported Languages:
    Python, TypeScript, Java, C++, Go, Rust, C#, Ruby, PHP,
    Swift, Dart, Elixir, Haskell, Scala, Kotlin

Examples:
    python scripts/build.py                    # Build all
    python scripts/build.py --python           # Python only
    python scripts/build.py --rust --go        # Rust and Go
    python scripts/build.py --skip-deps        # Skip deps
        """,
    )
    for lang in LANGUAGE_BUILDERS.keys():
        parser.add_argument(f"--{lang}", action="store_true", help=f"Build {lang.capitalize()}")
    parser.add_argument("--skip-codegen", action="store_true", help="Skip code generation")
    parser.add_argument("--skip-deps", action="store_true", help="Skip dependencies")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    all_languages = list(LANGUAGE_BUILDERS.keys())
    selected = [lang for lang in all_languages if getattr(args, lang, False)]
    if not selected:
        selected = all_languages

    print("=" * 60)
    print("Joshu Multi-Language Build System (15 Languages)")
    print("=" * 60)
    print(f"Building: {', '.join(selected)}")

    all_results: List[Tuple[str, bool]] = []

    for lang in selected:
        builder = LANGUAGE_BUILDERS.get(lang)
        if builder:
            results = builder(args.skip_deps, args.skip_codegen, args.verbose)
            for name, success in results:
                all_results.append((name, success))
                if success:
                    log_success(f"{name}")
                else:
                    log_error(f"{name} failed")

    create_build_marker(args.verbose)

    print("=" * 60)

    if not all_results:
        log_skip("No build steps (no languages detected)")
        return 0

    passed = sum(1 for _, s in all_results if s)
    failed = sum(1 for _, s in all_results if not s)

    if failed == 0:
        log_success(f"Build complete! ({passed} steps)")
        return 0

    log_error(f"Build failed: {failed} errors, {passed} passed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
