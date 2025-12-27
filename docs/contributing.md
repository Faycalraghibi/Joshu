# Contributing to Joshu

Guide for setting up a development environment and contributing to Joshu.

## Development Setup

### Prerequisites

- Python 3.10 or higher
- Git
- (Optional) Node.js 18+ for VSCode extension development
- (Optional) Docker or Podman for sandbox features

### Quick Start

```bash
# Clone repository
git clone https://github.com/Faycalraghibi/OpenCLI.git
cd OpenCLI

# Create virtual environment
python -m venv .joshuvenv

# Activate virtual environment
# Windows:
.joshuvenv\Scripts\Activate.ps1
# Linux/macOS:
source .joshuvenv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"

# Verify installation
joshu --version
```

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=src/joshu

# Run specific test file
pytest tests/test_config.py

# Using test runner script
python tests/run_tests.ps1  # Windows
./tests/run_tests.sh        # Linux/macOS
```

### Code Quality

```bash
# Run all linters (matches CI)
python scripts/lint.py

# Auto-fix issues
python scripts/lint.py --fix

# Run type checking only
python scripts/lint.py --mypy
```

## Development Workflow

### 1. Create Feature Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Make Changes

Follow the existing code style and patterns.

### 3. Run Quality Checks

```bash
# Before committing
python scripts/pre_commit.py

# Or run full lint
python scripts/lint.py
```

### 4. Run Tests

```bash
pytest tests/ -q --tb=short
```

### 5. Commit & Push

```bash
git add .
git commit -m "feat: your feature description"
git push origin feature/your-feature-name
```

### 6. Open Pull Request

Use the PR template provided.

## Build System

Joshu uses Python-native automation scripts. See [Development Automation](development-automation.md) for complete documentation.

### Common Commands

| Task | Command |
|------|---------|
| Full build | `python scripts/build.py` |
| Clean build | `python scripts/clean.py && python scripts/build.py` |
| Generate docs | `python scripts/generate_settings_docs.py` |
| Check freshness | `python scripts/check_build_status.py` |

## Code Style

- **Formatter**: ruff format (Black-compatible)
- **Linter**: ruff check
- **Type Checker**: mypy
- **Imports**: isort with black profile

Configuration in `pyproject.toml`:
- Line length: 100 characters
- Target: Python 3.10+

## Project Structure

```
joshu/
├── src/joshu/           # Main source code
│   ├── agents/          # Agent implementations
│   ├── commands/        # CLI commands
│   ├── core/            # Core utilities
│   ├── mcp/             # MCP protocol
│   ├── models/          # LLM providers
│   ├── tools/           # Tool implementations
│   └── ui/              # User interface
├── tests/               # Test suite
├── scripts/             # Automation scripts
├── docs/                # Documentation
├── config/              # Configuration files
└── packages/            # Additional packages
    └── vscode-joshu-companion/
```

## Writing Tests

### Test Location

Place tests in `tests/` mirroring the source structure.

### Test Naming

- Files: `test_<module>.py`
- Functions: `test_<description>`

### Example

```python
import pytest
from joshu.core.config import Config

def test_config_load_defaults():
    """Test that Config loads with sensible defaults."""
    config = Config()
    assert config.model_id is not None

@pytest.fixture
def sample_config():
    return Config(model_id="test-model")

def test_config_custom_model(sample_config):
    assert sample_config.model_id == "test-model"
```

## Release Process

Releases are managed through automation scripts:

1. **Calculate version**: `python scripts/releasing/get_release_version.py --type stable`
2. **Prepare artifacts**: `python scripts/releasing/prepare_github_release.py --version X.Y.Z`
3. **Create release**: Use GitHub Releases UI or `gh release create`

See [Development Automation](development-automation.md#release-management) for details.

## VSCode Extension Development

The VSCode Joshu Companion extension is located in `packages/vscode-joshu-companion/`.

### Setup

```bash
cd packages/vscode-joshu-companion
npm install
```

### Build

```bash
# Using automation script
python scripts/build_vscode_companion.py

# Or directly with npm
cd packages/vscode-joshu-companion
npm run build
```

### Package

```bash
python scripts/build_vscode_companion.py --package
```

## Troubleshooting

### TypeScript Errors: "Cannot find module 'vscode'"

**Error messages:**
```
Cannot find module 'vscode' or its corresponding type declarations
Cannot find module 'http', 'fs', 'path', 'os'
Cannot find name 'console'
Cannot find name 'Buffer'
```

**Solution:** Install npm dependencies:
```bash
cd packages/vscode-joshu-companion
npm install
```

### TypeScript Errors: "Parameter implicitly has an 'any' type"

**Solution:** The project has strict TypeScript settings. Add explicit types:
```typescript
// Before
function handler(res, e) { }

// After
function handler(res: http.ServerResponse, e: Error) { }
```

### TypeScript Errors: "'lib' compiler option to include 'dom'"

**Solution:** This is expected for Node.js code. The `console` global is provided by `@types/node`. Run:
```bash
npm install --save-dev @types/node
```

### Python Import Errors

**Error:** `ModuleNotFoundError: No module named 'joshu'`

**Solution:** Install in development mode:
```bash
pip install -e ".[dev]"
```

### Lint Errors After Clean Install

**Error:** `ruff: command not found` or `mypy: command not found`

**Solution:** Install dev dependencies:
```bash
pip install -e ".[dev]"
```

### Pre-commit Hook Failures

**Error:** Pre-commit checks fail unexpectedly

**Solution:**
1. Run `python scripts/lint.py --fix` to auto-fix issues
2. Review remaining errors with `python scripts/lint.py --verbose`

## Getting Help

- Check existing documentation in `docs/`
- Search existing issues on GitHub
- Open a new issue with details
