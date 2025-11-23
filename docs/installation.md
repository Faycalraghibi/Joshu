# Installation Guide

## System Requirements

- Python 3.8+ (tested up to Python 3.13)
- 4GB+ RAM (8GB recommended for local models)
- CUDA-compatible GPU (optional, for local inference)

## Basic Installation

### 1. Clone Repository

```bash
git clone https://github.com/Faycacalraghibi/joshu-assistant.git
cd joshu-assistant
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

### Semantic Memory

Enables semantic search of past conversations using ChromaDB:

```bash
pip install -e .[semantic]
```

Includes:
- `chromadb>=0.4.0` — Vector database
- `sentence-transformers>=2.2.0` — Text embeddings

### Local LLM Support

Enables running local models (Llama, Mistral, etc.):

```bash
pip install -e .[llm]
```

Includes:
- `transformers>=4.36.2`
- `torch>=2.9.0`
- `llama-cpp-python>=0.2.55`
- `sentencepiece>=0.1.99`

### Development Tools

For contributing to Joshu:

```bash
pip install -e .[dev]
```

Includes:
- `pytest>=8.4.2` — Testing
- `black>=24.4.0` — Code formatting
- `flake8>=7.0.0` — Linting

### Complete Installation

Install everything:

```bash
pip install -e .[dev,llm,semantic]
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
