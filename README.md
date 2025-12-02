# Joshu

AI-powered command-line assistant that converts natural language into shell commands and code.

![Architecture](diagram.png)

## Installation

### Quick Setup (Recommended)

**Windows (PowerShell):**
```powershell
git clone https://github.com/Faycacalraghibi/joshu.git
cd joshu
.\clean_install.ps1
```

**Linux/macOS:**
```bash
git clone https://github.com/Faycacalraghibi/joshu.git
cd joshu
chmod +x clean_install.sh
./clean_install.sh
```

This will:
- Create a fresh virtual environment
- Install all dependencies
- Set up pre-commit hooks
- Create config directories
- Clear cache files

### Manual Installation

```bash
pip install -e .
```

**Optional dependencies:**
```bash
pip install -e .[dev]   # Development tools (testing, linting, pre-commit)
pip install -e .[use]   # All features (semantic memory, local LLMs)
```

## Quick Start

```bash
joshu interactive              # Start interactive mode
joshu "your command here"      # One-shot execution
joshu search "query"           # Search the web for information
```

## Documentation

See [`docs/`](docs/) for complete documentation:

- **[interactive Mode](docs/interactive_mode.md)** — Features and commands
- **[Web Search](docs/web-search.md)** — Search the web from your terminal
- **[VLLM Server Integration](docs/VLLM_SERVER_INTEGRATION.md)** — Local model setup
- **[Rules & Guidelines](docs/Rules.md)** — Development standards
- **[Todo](docs/Todo.md)** — Roadmap and planned features

## Configuration

Create `~/.joshu/config.yaml` or set environment variables. See [docs](docs/) for details.

## License

MIT — See [LICENSE](LICENSE)
