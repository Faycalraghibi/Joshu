Param()
$ErrorActionPreference = "Stop"

# Run test suite with common defaults (Windows PowerShell)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
Set-Location $repoRoot

$venv = Join-Path $repoRoot ".joshuvenv\Scripts\Activate.ps1"
if (Test-Path $venv) { . $venv }

$env:PYTHONUNBUFFERED = "1"
$env:PYTHONDONTWRITEBYTECODE = "1"

# Model configuration
if (-not $env:OPENROUTER_MODEL) { $env:OPENROUTER_MODEL = "poolside/laguna-s-2.1:free" }
if (-not $env:GLM_Identifier) { $env:GLM_Identifier = "z-ai/glm-4.5-air:free" }

# Skip LLM tests in CI (set SKIP_LLM_TESTS=1 to skip)
if (-not $env:SKIP_LLM_TESTS) { $env:SKIP_LLM_TESTS = "0" }

# Ensure package is importable (editable install fallback)
try {
  python -c "import joshu" | Out-Null
}
catch {
  pip install -e ".[dev]"
}

# Run tests
pytest tests/ -q --tb=short
