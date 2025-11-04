# Rules: Technical Constraints \& Specifications

## Supported Language \& Version

- **Primary Language**: Python 3.8+
  - Minimum: Python 3.8 (max compatibility with modern libraries and legacy support)
  - Maximum: Python 3.11

## Required and Recommended Libraries

```yaml
# Requirements
core:
  - transformers==4.36.2
  - sentencepiece==0.1.99
  - torch==2.1.2
  - huggingface_hub==0.23.0
  - llama-cpp-python==0.2.55           # For Llama/Mistral local inference (deprecated, use local model API instead)
  - openai==1.22.0                     # For OpenRouter API or OpenAI models

cli:
  - typer==0.9.0                       # Modern CLI interface
  - rich==13.6.0                       # Colorized output and progress bars
  - pydantic==2.7.2                    # Config, validation, data modeling
  - python-dotenv==1.0.1                # .env config support

utils:
  - requests==2.31.0
  - tqdm==4.66.4
  - pytest==8.2.1                      # For testing
  - black==24.4.0
  - flake8==7.0.0
```

## Model Compatibility Boundaries

- **Supported Models**
  - Any model available through OpenRouter API
  - Any model served via local model API (OpenAI-compatible endpoints)
  - Deprecated: Direct llama.cpp models (use local model API instead)
- **Inference Engine Constraints**:
  - OpenRouter API for cloud-based inference
  - Local model API (OpenAI-compatible) for local inference - supports any local model server
  - Deprecated: Direct llama.cpp inference (<16GB RAM for 7B models, ≥32GB for 13B+, ≥64GB for 70B)

## OS \& Platform Requirements

- **Supported OS**: Linux (Ubuntu/Debian 20.04+), macOS (10.15+), Windows 10/11 (with WSL for GPU)
- **Minimum Hardware**:
  - RAM: 8GB for mid-size models, 4GB for small models
  - Disk Space: >20GB free, SSD recommended
  - GPU: Optional, CUDA 11.8+ for optimal performance with local model servers

## Dependency Management \& Environment Setup

- Use a `requirements.txt` pinned with exact versions
- Use `pyproject.toml` for modern builds (Poetry integration recommended)
- Enforce virtual environments using `venv` or `conda`
- Provide a `Dockerfile` with all dependencies for reproducibility

## Security Restrictions

- Deny or restrict system-level libraries (os, subprocess) except within sandboxed modules[^1][^2]
- Always isolate code execution environments (use docker, firejail, etc.) for sandboxing
- Only trusted, maintained libraries permitted; avoid deprecated or unsafe packages

## Code Structure and Module Boundaries

- Each core component (agent, llm, tools, cli, memory) must be a separate Python package/module
- All configuration via `.env`, `yaml`, or CLI args; never hardcoded secrets or tokens in code
- Logging must use Python’s built-in logging (not print) with INFO/WARN/ERROR levels
- Document all public functions, classes, and modules with docstrings and type hints

## Versioning \& Release Protocols

- Semantic versioning: MAJOR.MINOR.PATCH (e.g. 0.1.0)
- Use GitHub Releases and tags for all production-ready builds
- Automated testing (pytest), linting (flake8, black), security checks in CI pipeline

## Prompt Boundaries for AI Agent

- Refuse prompts that request network or filesystem access outside the predefined working directory
- Only allow code generation or command execution within allowed sandbox environment
- Explicitly document unsupported features or unreasonably high resource requirements to the user

## Example `.env`

```env
PYTHON_VERSION="3.10"
LOG_LEVEL="INFO"
MAX_TOKENS="4096"
MEMORY_ENABLED="true"
SANDBOX_EXECUTION="true"

# OpenRouter API Configuration (for cloud inference)
OPENROUTER_API_KEY="your-api-key"
OPENROUTER_MODEL="openai/gpt-4o-mini"
JOSHU_USE_CLOUD="true"

# Local Model API Configuration (for local inference)
# Configure your local model server (must provide OpenAI-compatible /v1/chat/completions endpoint)
LOCAL_MODEL_URL="http://localhost:1234"           # Base URL (endpoint path will be appended automatically)
LOCAL_MODEL_IDENTIFIER="your-model-name"          # Model identifier/name

# Deprecated: Direct llama.cpp model loading (use local model API instead)
# LLAMA_CPP_MODEL_LLAMA3_8B="/path/to/model.gguf"
```

---

## 🧭 Prompts to Enforce Technical Bounds

- “Generate code for [COMPONENT] using only the libraries provided in requirements.txt.”
- “Suggest optimizations compatible with Python 3.8 and torch 2.1.2.”
- “Limit memory usage to 8GB and ensure the code will run on Linux without special GPU dependencies.”
- “Do not generate any code that requires root privileges or OS-level changes.”

---

### Summary

Technical constraints and strict library/version boundaries keep your AI agent’s development safe, reproducible, and maintainable. They also help your AI co-developer respect your dev environment and ensure all generated code is reliable and compatible with your project.

You can copy-paste these rules into your repo (as `AI_DEV_RULES.md` or similar) and update as your tech stack evolves.

[^1]: <https://arxiv.org/pdf/2408.12289.pdf>

[^2]: <https://arxiv.org/pdf/2209.04963.pdf>
