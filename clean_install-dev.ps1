Param()
$ErrorActionPreference = "Stop"

# Clean dev install for OpenCLI Assistant on Windows PowerShell
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
$venvDir = ".OpenCLIvenv"

if (Test-Path $venvDir) {
  Write-Host "[info] Removing existing venv: $venvDir"
  Remove-Item -Recurse -Force $venvDir
}

Write-Host "[info] Creating venv: $venvDir"
& $py -m venv $venvDir

$activateScript = Join-Path $venvDir "Scripts\Activate.ps1"
if (!(Test-Path $activateScript)) { throw "Activate script not found: $activateScript" }

. $activateScript
Write-Host "[info] Python: $(& python --version)"

Write-Host "[info] Upgrading pip/setuptools/wheel"
python -m pip install -U pip setuptools wheel

Write-Host "[info] Installing dependencies"
pip install -r requirements.txt -r requirements-dev.txt

Write-Host "[info] Editable install"
pip install -e .

Write-Host "`n[done] Development environment ready.`n"
Write-Host "Next steps:"
Write-Host "  1) Optionally set OpenRouter env vars (use your own values):"
Write-Host "     `$env:OPENROUTER_API_KEY = \"sk-...\""
Write-Host "     `$env:OPENROUTER_MODEL = \"openai/gpt-4o\""
Write-Host "     `$env:OPENROUTER_SITE_URL = \"https://your-site\""
Write-Host "     `$env:OPENROUTER_SITE_TITLE = \"Your Site\""
Write-Host "  2) Run tests:"
Write-Host "     pytest -q"
Write-Host "  3) Use the CLI:"
Write-Host "     joshu run \"show disk usage of current directory\" -y"


