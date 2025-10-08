#!/usr/bin/env bash
set -euo pipefail

# Clean dev install for OpenCLI Assistant
# - Creates fresh venv at .venv
# - Upgrades pip/setuptools/wheel
# - Installs runtime + dev requirements
# - Editable install of the package

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo "[info] Project root: $PROJECT_ROOT"

# Choose python executable
if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "[error] python not found in PATH" >&2
  exit 1
fi

VENV_DIR=".OpenCLIvenv"

if [ -d "$VENV_DIR" ]; then
  echo "[info] Removing existing venv: $VENV_DIR"
  rm -rf "$VENV_DIR"
fi

echo "[info] Creating venv: $VENV_DIR"
"$PY" -m venv "$VENV_DIR"

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "[info] Python: $(python --version)"
echo "[info] Upgrading pip/setuptools/wheel"
python -m pip install -U pip setuptools wheel

echo "[info] Installing dependencies"
pip install -r requirements.txt -r requirements-dev.txt

echo "[info] Editable install"
pip install -e .

echo
echo "[done] Development environment ready."
echo
echo "Next steps:"
echo "  1) Optionally export OpenRouter env vars (use your own values):"
echo "     export OPENROUTER_API_KEY=\"sk-...\""
echo "     export OPENROUTER_MODEL=\"openai/gpt-4o\""
echo "     export OPENROUTER_SITE_URL=\"https://your-site\""
echo "     export OPENROUTER_SITE_TITLE=\"Your Site\""
echo "  2) Run tests:"
echo "     pytest -q"
echo "  3) Use the CLI:"
echo "     opencli run \"show disk usage of current directory\" -y"


