Param()
$ErrorActionPreference = "Stop"

# Run test suite with common defaults (Windows PowerShell)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
Set-Location $repoRoot

$venv2 = Join-Path $repoRoot ".joshuvenv\Scripts\Activate.ps1"
if (Test-Path $venv) { . $venv }
elseif (Test-Path $venv2) { . $venv2 }

$env:PYTHONUNBUFFERED = "1"
$env:PYTHONDONTWRITEBYTECODE = "1"

# Optional OpenRouter config
if (-not $env:OPENROUTER_MODEL) { $env:OPENROUTER_MODEL = "openai/gpt-4o" }

# Ensure package is importable (editable install fallback)
try {
  python -c "import joshu" | Out-Null
}
catch {
  pip install -e .
}

pytest -q

