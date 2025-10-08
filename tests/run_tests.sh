#!/usr/bin/env bash
set -euo pipefail

# Run test suite with common defaults

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

if [ -d .venv ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate || true
fi

export PYTHONUNBUFFERED=1
export PYTHONDONTWRITEBYTECODE=1

# Ensure OpenRouter config is optional
export OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}"
export OPENROUTER_MODEL="${OPENROUTER_MODEL:-openai/gpt-4o}"

# Ensure package import
python - <<'PY'
import sys
try:
    import opencli  # noqa: F401
except Exception as e:
    sys.exit(42)
PY
if [ "$?" -eq 42 ]; then
  pip install -e .
fi

pytest -q

