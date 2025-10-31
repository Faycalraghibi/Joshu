Param()
$ErrorActionPreference = "Stop"

# Clean dev install for Joshu Assistant on Windows PowerShell
# - Creates fresh venv at .venv
# - Upgrades pip/setuptools/wheel
# - Installs runtime + dev requirements
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

Write-Host "[info] Installing dependencies"
# Install basic requirements and development tools
pip install -r requirements.txt
pip install -e .[dev]

# Optionally install LLM dependencies (uncomment if needed)
# Write-Host "[info] Installing optional LLM dependencies"
# pip install -r requirements-llm.txt

Write-Host "[info] Editable install"
pip install -e .

Write-Host "`n[done] Development environment ready.`n"
Write-Host "Next steps:"
Write-Host "  1) Optionally set OpenRouter env vars (use your own values):"
Write-Host "     `$env:OPENROUTER_API_KEY = `"sk-...`""
Write-Host "     `$env:OPENROUTER_MODEL = `"openai/gpt-4o`""
Write-Host "     `$env:OPENROUTER_SITE_URL = `"https://your-site`""
Write-Host "     `$env:OPENROUTER_SITE_TITLE = `"Your Site`""
Write-Host "  2) Install optional LLM dependencies (if needed):"
Write-Host "     pip install -r requirements-llm.txt"
Write-Host "  3) Run tests:"
Write-Host "     pytest -q"
Write-Host "  4) Use the CLI:"
Write-Host "     joshu run `"show disk usage of current directory`" -y"