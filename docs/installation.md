# Installation Guide

## System Requirements

- Python 3.8+ (tested up to Python 3.13)
- 4GB+ RAM (8GB recommended for local models)
- CUDA-compatible GPU (optional, for local inference)

## Basic Installation

### 1. Clone Repository

```bash
git clone https://github.com/Faycalraghibi/Joshu.git joshu
cd joshu
```

### 2. Create Virtual Environment (Recommended)

**Linux/macOS:**
```bash
python -m venv .joshuvenv
source .joshuvenv/bin/activate
```

**Windows:**
```bash
python -m venv .joshuvenv
.joshuvenv\Scripts\activate
```

### 3. Install Core Package

```bash
pip install -e .
```

## Optional Dependencies

### A2A Server

Enables the HTTP/SSE server for agent-to-agent communication:

```bash
pip install -e .[a2a]
```

Includes:
- `fastapi>=0.104.0` — Web framework
- `uvicorn>=0.24.0` — ASGI server

See [A2A Server Documentation](a2a-server.md) for usage.

### Semantic Memory

Enables semantic search of past conversations using ChromaDB:

```bash
pip install -e .[use]
```

Includes:
- `chromadb>=0.4.0` — Vector database
- `sentence-transformers>=2.2.0` — Text embeddings

### Local Models

No extra packages are needed: run a local OpenAI-compatible server such as
Ollama or LM Studio and select it with `--provider ollama` or
`--provider lmstudio`. See [Models & Providers](models-and-providers.md).

### Development Tools

For contributing to Joshu:

```bash
pip install -e .[dev]
```

Includes:
- `pytest>=8.4.2` — Testing
- `ruff>=0.14.0` — Linting and formatting
- `mypy>=1.19.0` — Type checking

### Complete Installation

Install everything:

```bash
pip install -e .[dev,use]
```

## Automated Installation Scripts

### Windows (PowerShell)

```powershell
.\clean_install.ps1
```

### Linux/macOS (Bash)

```bash
chmod +x clean_install.sh
./clean_install.sh
```

## Verify Installation

```bash
joshu --version
joshu --help
```

## Next Steps

- **[Quick Start Guide](quick-start.md)** — Your first steps with Joshu
- **[Configuration](configuration.md)** — Set up API keys and preferences
- **[A2A Server](a2a-server.md)** — Run the HTTP/SSE server
