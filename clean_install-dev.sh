#!/bin/bash

# Clean dev install for OpenCLI Assistant on Linux/Unix
# - Creates fresh venv at .OpenCLIvenv
# - Upgrades pip/setuptools/wheel
# - Installs runtime + dev requirements
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
VENV_DIR=".OpenCLIvenv"

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

source "$ACTIVATE_SCRIPT"
echo "[info] Python: $(python --version)"

# Upgrade pip/setuptools/wheel
echo "[info] Upgrading pip/setuptools/wheel"
python -m pip install -U pip setuptools wheel

# Install dependencies
echo "[info] Installing dependencies"
pip install -r requirements.txt -r requirements-dev.txt

# Editable install
echo "[info] Editable install"
pip install -e .

echo -e "\n[done] Development environment ready.\n"
echo "Next steps:"
echo "  1) Optionally set OpenRouter env vars (use your own values):"
echo "     export OPENROUTER_API_KEY=\"sk-...\""
echo "     export OPENROUTER_MODEL=\"openai/gpt-4o\""
echo "     export OPENROUTER_SITE_URL=\"https://your-site\""
echo "     export OPENROUTER_SITE_TITLE=\"Your Site\""
echo "  2) Run tests:"
echo "     pytest -q"
echo "  3) Use the CLI:"
echo "     opencli run \"show disk usage of current directory\" -y"