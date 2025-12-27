# Development Automation

Joshu includes a comprehensive Python-based automation system for building, testing, releasing, and maintaining polyglot projects supporting **20+ programming languages**.

## Quick Reference

| Task | Command |
|------|---------|
| Build project | `python scripts/build.py` |
| Run linting | `python scripts/lint.py` |
| Fix lint issues | `python scripts/lint.py --fix` |
| Clean artifacts | `python scripts/clean.py` |
| Check build freshness | `python scripts/check_build_status.py` |
| Pre-commit checks | `python scripts/pre_commit.py` |

> [!TIP]
> All scripts support `--help` for detailed usage information.

---

## Supported Languages

### Linting (20 Languages, 30+ Tools)

| Language | Tools |
|----------|-------|
| **Python** | ruff check, ruff format, mypy |
| **TypeScript** | tsc, eslint |
| **Java** | checkstyle, spotbugs |
| **C/C++** | clang-format, clang-tidy, cppcheck |
| **Go** | go vet, gofmt, golangci-lint |
| **Rust** | cargo check, clippy, cargo fmt |
| **C#** | dotnet format |
| **Ruby** | rubocop |
| **PHP** | phpcs, php-cs-fixer, phpstan |
| **Kotlin** | ktlint, detekt |
| **Swift** | swiftlint, swift-format |
| **Scala** | scalafmt, scalafix |
| **Dart** | dart analyze, dart format |
| **Elixir** | mix format, credo |
| **Haskell** | hlint, ormolu |
| **Lua** | luacheck, stylua |
| **Shell** | shellcheck, shfmt |
| **YAML** | yamllint |
| **JSON** | jsonlint |
| **SQL** | sqlfluff |

### Building (15 Languages)

| Language | Build System |
|----------|--------------|
| Python | pip, setuptools |
| TypeScript | npm, tsc, esbuild |
| Java/Kotlin | Maven, Gradle |
| C++ | CMake, Make |
| Go | go build |
| Rust | cargo build |
| C# | dotnet build |
| Ruby | bundler |
| PHP | composer |
| Swift | swift build |
| Dart | dart pub |
| Elixir | mix compile |
| Haskell | stack, cabal |
| Scala | sbt |

### Pre-commit (30+ File Extensions)

Detects: `.py`, `.ts`, `.tsx`, `.js`, `.java`, `.kt`, `.scala`, `.c`, `.cpp`, `.h`, `.go`, `.rs`, `.cs`, `.rb`, `.php`, `.swift`, `.dart`, `.ex`, `.hs`, `.lua`, `.sh`, `.yaml`, `.json`, `.sql`, and more.

---

## Build Scripts

### Main Build (`scripts/build.py`)

```bash
python scripts/build.py                 # Build all detected languages
python scripts/build.py --python        # Python only
python scripts/build.py --typescript    # TypeScript only
python scripts/build.py --rust --go     # Multiple languages
python scripts/build.py --skip-deps     # Skip dependency installation
python scripts/build.py --verbose       # Verbose output
```

### Cleanup (`scripts/clean.py`)

```bash
python scripts/clean.py              # Clean all languages
python scripts/clean.py --dry-run    # Preview deletions
python scripts/clean.py --python     # Python only
python scripts/clean.py --all        # Include vendored dependencies
```

### VSCode Extension (`scripts/build_vscode_companion.py`)

```bash
python scripts/build_vscode_companion.py           # Compile only
python scripts/build_vscode_companion.py --package # Create .vsix
```

---

## Code Quality

### Linting (`scripts/lint.py`)

```bash
python scripts/lint.py              # Check all detected languages
python scripts/lint.py --fix        # Auto-fix issues
python scripts/lint.py --python     # Python only
python scripts/lint.py --rust --go  # Multiple languages
```

> [!NOTE]
> The linter auto-detects languages by scanning for source files.
> Missing tools are gracefully skipped with a message.

### Pre-commit Hook (`scripts/pre_commit.py`)

```bash
python scripts/pre_commit.py        # Staged files only
python scripts/pre_commit.py --all  # All files
python scripts/pre_commit.py --fix  # Auto-fix issues
```

**Install as git hook:**
```bash
echo 'python scripts/pre_commit.py' > .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit  # Linux/macOS
```

### Dependency Check (`scripts/check_lockfile.py`)

Validates both Python and npm lockfile integrity:

```bash
python scripts/check_lockfile.py              # Check all
python scripts/check_lockfile.py --python     # Python only
python scripts/check_lockfile.py --npm        # npm only
python scripts/check_lockfile.py --strict     # Fail on issues
```

**Validates:**
- Python: `requirements.txt` vs installed packages
- npm: `package-lock.json` `resolved` and `integrity` fields

### Secrets Scanner (`scripts/check_secrets.py`)

Scans source code for accidental credential commits:

```bash
python scripts/check_secrets.py              # Scan project
python scripts/check_secrets.py --strict     # Fail on secrets
python scripts/check_secrets.py --verbose    # Show details
```

**Detects:**
- API keys and tokens (AWS, GCP, Azure, GitHub, Slack)
- Private keys (RSA, SSH, PGP)
- Database connection strings
- JWTs, OAuth tokens, Bearer tokens

> [!TIP]
> Create `.secretsignore` to suppress false positives.

### Build Status (`scripts/check_build_status.py`)

```bash
python scripts/check_build_status.py
python scripts/check_build_status.py --fail-on-stale
```

---

## Code Generation

### Version Info (`scripts/generate_git_info.py`)

```bash
python scripts/generate_git_info.py
```

Generates `src/joshu/_version.py` with version, commit hash, branch, and build timestamp.

### Settings Schema (`scripts/generate_settings_schema.py`)

```bash
python scripts/generate_settings_schema.py
```

### Documentation Generators

```bash
python scripts/generate_settings_docs.py      # → docs/settings.md
python scripts/generate_keybindings_docs.py   # → docs/keybindings.md
```

---

## Release Management

Scripts in `scripts/releasing/`:

```bash
# Version calculation
python scripts/releasing/get_release_version.py --type stable
python scripts/releasing/get_release_version.py --type nightly

# GitHub release preparation
python scripts/releasing/prepare_github_release.py --version 0.2.0

# Patch release automation
python scripts/releasing/create_patch_pr.py --base v0.1.0 --commits abc123

# PR comments
python scripts/releasing/comment_on_pr.py --pr 123 --template release_ready
```

---

## Sandbox (Docker/Podman)

```bash
python scripts/build_sandbox.py                    # Build image
python scripts/sandbox_command.py -- --help        # Run command
python scripts/sandbox_command.py --mount-cwd -- analyze file.py
```

---

## Telemetry (Opt-in)

```bash
python scripts/telemetry.py --status   # Check status
python scripts/telemetry.py --enable   # Enable
python scripts/telemetry.py --disable  # Disable

# Local debugging
python scripts/telemetry_local.py --start
python scripts/telemetry_local.py --logs
python scripts/telemetry_local.py --stop
```

---

## CI Integration

```yaml
- name: Run linting
  run: python scripts/lint.py

- name: Check build status
  run: python scripts/check_build_status.py
```

### Reproduce CI Locally

```bash
pip install -e ".[dev]"
python scripts/lint.py
pytest tests/ -q --tb=short
```

---

## Script Directory Structure

```
scripts/
├── build.py                    # Multi-language build orchestrator
├── clean.py                    # Multi-language artifact cleanup
├── lint.py                     # Multi-language linter (20 languages)
├── pre_commit.py               # Multi-language pre-commit hook
├── build_package.py            # Python package builder
├── build_vscode_companion.py   # VSCode extension builder
├── build_sandbox.py            # Container image builder
├── check_lockfile.py           # Dependency validator
├── check_build_status.py       # Build freshness checker
├── generate_git_info.py        # Version embedder
├── generate_settings_*.py      # Config documentation
├── sandbox_command.py          # Sandbox CLI wrapper
├── telemetry*.py               # Telemetry utilities
└── releasing/
    ├── get_release_version.py
    ├── prepare_github_release.py
    ├── create_patch_pr.py
    └── comment_on_pr.py
```
