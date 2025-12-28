Param()
$ErrorActionPreference = "Stop"

# Clean dev install for Joshu Assistant on Windows PowerShell
# - Creates fresh venv at .joshuvenv
# - Upgrades pip/setuptools/wheel
# - Installs runtime + dev requirements from pyproject.toml
# - Editable install of the package

function Resolve-Python {
  if (Get-Command python -ErrorAction SilentlyContinue) { return "python" }
  if (Get-Command python3 -ErrorAction SilentlyContinue) { return "python3" }
  throw "Python not found in PATH. Install Python 3.8+ and retry."
}

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot
Write-Host "[info] Project root: $projectRoot"

$py = Resolve-Python
$venvDir = ".joshuvenv"

if (Test-Path $venvDir) {
  Write-Host "[info] Removing existing venv: $venvDir"
  try {
    Remove-Item -Recurse -Force $venvDir
  } catch {
    Write-Host "[warn] Could not remove venv directory, it may be in use. Creating new venv with timestamp suffix." -ForegroundColor Yellow
    $venvDir = ".joshuvenv_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    Write-Host "[info] Creating new venv: $venvDir" -ForegroundColor Yellow
  }
}

if (-not (Test-Path $venvDir)) {
  Write-Host "[info] Creating venv: $venvDir"
  & $py -m venv $venvDir
}

$activateScript = Join-Path $venvDir "Scripts\Activate.ps1"
if (!(Test-Path $activateScript)) { throw "Activate script not found: $activateScript" }

. $activateScript
Write-Host "[info] Python: $(& python --version)"

Write-Host "[info] Upgrading pip/setuptools/wheel"
python -m pip install -U pip setuptools wheel

# Install package with dev dependencies (from pyproject.toml)
Write-Host "[info] Installing package with dev dependencies"
pip install -e .[dev]

# Install pre-commit hooks
Write-Host "`n[info] Installing pre-commit hooks"
pre-commit install

# Setup Joshu config directory
Write-Host "[info] Setting up Joshu config directory"
$joshuConfigDir = "$env:USERPROFILE\.joshu"
if (-not (Test-Path $joshuConfigDir)) {
    New-Item -ItemType Directory -Path $joshuConfigDir -Force | Out-Null
    Write-Host "  Created: $joshuConfigDir"
}
# Clear cache folder
Write-Host "[info] Clearing cache folder"
$cacheDir = "./cache"
if (Test-Path $cacheDir) {
    Remove-Item -Recurse -Force $cacheDir
    Write-Host "  Removed: $cacheDir"
}
New-Item -ItemType Directory -Path $cacheDir -Force | Out-Null
Write-Host "  Created: $cacheDir"

Write-Host "`n[done] Development environment ready!`n" -ForegroundColor Green
Write-Host "Next steps:"
Write-Host "  1) Set OpenRouter API key (required):"
Write-Host "     `$env:OPENROUTER_API_KEY = `"sk-or-v1-...`""
Write-Host "     # Or add to .env file: OPENROUTER_API_KEY=sk-or-v1-..."
Write-Host ""
Write-Host "  2) Optional: Configure model (default: z-ai/glm-4.5-air:free):"
Write-Host "     .\setup_config.ps1"
Write-Host ""
Write-Host "  3) Optional: Install all features (semantic memory, local LLMs):"
Write-Host "     pip install -e .[use]"
Write-Host ""
Write-Host "  4) Run tests to verify installation:"
Write-Host "     pytest -q"
Write-Host ""
Write-Host "  5) Start using Joshu:"
Write-Host "     joshu interactive"
Write-Host "     joshu `"show disk usage`" -y"
