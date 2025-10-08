Param()
$ErrorActionPreference = "Stop"

# Run test suite with common defaults (Windows PowerShell)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
Set-Location $repoRoot

# Try activating common venvs
$venv = Join-Path $repoRoot ".venv\Scripts\Activate.ps1"
$venv2 = Join-Path $repoRoot ".OpenCLIvenv\Scripts\Activate.ps1"
if (Test-Path $venv) { . $venv }
elseif (Test-Path $venv2) { . $venv2 }

$env:PYTHONUNBUFFERED = "1"
$env:PYTHONDONTWRITEBYTECODE = "1"

# Optional OpenRouter config
if (-not $env:OPENROUTER_MODEL) { $env:OPENROUTER_MODEL = "openai/gpt-4o" }

# Ensure package is importable (editable install fallback)
try {
  python -c "import opencli" | Out-Null
}
catch {
  pip install -e .
}

pytest -q

