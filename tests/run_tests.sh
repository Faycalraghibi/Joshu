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

# Model configuration
if [ -z "${OPENROUTER_MODEL:-}" ]; then export OPENROUTER_MODEL="poolside/laguna-s-2.1:free"; fi
if [ -z "${GLM_Identifier:-}" ]; then export GLM_Identifier="z-ai/glm-4.5-air:free"; fi

# Skip LLM tests in CI (set SKIP_LLM_TESTS=1 to skip)
if [ -z "${SKIP_LLM_TESTS:-}" ]; then export SKIP_LLM_TESTS="0"; fi

# Ensure package is importable (editable install fallback)
if ! python -c "import joshu" 2>/dev/null; then
  pip install -e ".[dev]"
fi

# Run tests
pytest tests/ -q --tb=short
