#!/bin/bash

# Clean dev install for Joshu Assistant on Linux/Unix
# - Creates fresh venv at .joshuvenv
# - Upgrades pip/setuptools/wheel
# - Installs runtime + dev requirements from pyproject.toml
# - Editable install of the package

set -e  # Exit on any error

# Function to find python
resolve_python() {
  if command -v python3 &> /dev/null; then
    echo "python3"
  elif command -v python &> /dev/null; then
    echo "python"
  else
    echo "Error: Python not found in PATH. Install Python 3.8+ and retry." >&2
    exit 1
  fi
}

# Get the project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "[info] Project root: $PROJECT_ROOT"

cd "$PROJECT_ROOT"

PY=$(resolve_python)
VENV_DIR=".joshuvenv"

# Remove existing venv if it exists
if [ -d "$VENV_DIR" ]; then
  echo "[info] Removing existing venv: $VENV_DIR"
  rm -rf "$VENV_DIR"
fi

# Create new venv
echo "[info] Creating venv: $VENV_DIR"
$PY -m venv "$VENV_DIR"

# Activate venv
ACTIVATE_SCRIPT="$VENV_DIR/bin/activate"
if [ ! -f "$ACTIVATE_SCRIPT" ]; then
  echo "Error: Activate script not found: $ACTIVATE_SCRIPT" >&2
  exit 1
fi

# shellcheck source=/dev/null
source "$ACTIVATE_SCRIPT"
echo "[info] Python: $(python --version)"

# Upgrade pip/setuptools/wheel
echo "[info] Upgrading pip/setuptools/wheel"
python -m pip install -U pip setuptools wheel

# Install package with dev dependencies (from pyproject.toml)
echo "[info] Installing package with dev dependencies"
pip install -e .[dev]

# Install pre-commit hooks
echo -e "\n[info] Installing pre-commit hooks"
pre-commit install

# Setup Joshu user config directory
echo "[info] Setting up Joshu user config directory"
JOSHU_CONFIG_DIR="$HOME/.joshu"
if [ ! -d "$JOSHU_CONFIG_DIR" ]; then
    mkdir -p "$JOSHU_CONFIG_DIR"
    echo "  Created: $JOSHU_CONFIG_DIR"
fi

# Create default user config if it doesn't exist
USER_CONFIG_PATH="$JOSHU_CONFIG_DIR/config.yaml"
if [ ! -f "$USER_CONFIG_PATH" ]; then
    echo "model: z-ai/glm-4.5-air:free" > "$USER_CONFIG_PATH"
    echo "  Created: $USER_CONFIG_PATH"
fi

# Clear cache folder
echo "[info] Clearing cache folder"
CACHE_DIR="./cache"
if [ -d "$CACHE_DIR" ]; then
    rm -rf "$CACHE_DIR"
    echo "  Removed: $CACHE_DIR"
fi
mkdir -p "$CACHE_DIR"
echo "  Created: $CACHE_DIR"

echo -e "\n[done] Development environment ready!\n"
echo "Next steps:"
echo "  1) Set OpenRouter API key (required):"
echo "     export OPENROUTER_API_KEY=\"sk-or-v1-...\""
echo "     # Or add to .env file: OPENROUTER_API_KEY=sk-or-v1-..."
echo ""
echo "  2) Optional: Configure model (default: z-ai/glm-4.5-air:free):"
echo "     Edit $USER_CONFIG_PATH"
echo ""
echo "  3) Optional: Install all features (semantic memory, local LLMs):"
echo "     pip install -e .[use]"
echo ""
echo "  4) Run tests to verify installation:"
echo "     pytest -q"
echo ""
echo "  5) Start using Joshu:"
echo "     joshu interactive"
echo "     joshu \"show disk usage\" -y"
