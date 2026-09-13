# GPT-6 适配变更说明：建立项目隔离开发环境，不改全局 Python、ComfyUI 或系统 PATH。
[CmdletBinding()]
param([string]$Python = "python")

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvRoot = Join-Path $projectRoot ".venv"
$venvPython = Join-Path $venvRoot "Scripts/python.exe"

if (-not (Test-Path -LiteralPath $venvPython)) {
    if (Test-Path -LiteralPath $venvRoot) {
        throw "Existing .venv has no Python executable. Inspect it before repairing; it was not overwritten."
    }
    & $Python -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 'Python 3.12+ is required')"
    if ($LASTEXITCODE -ne 0) { throw "Select Python 3.12+ with -Python <executable>." }
    & $Python -m venv $venvRoot
    if ($LASTEXITCODE -ne 0) { throw "Could not create .venv. Use a Python installation with venv and ensurepip." }
}

& $venvPython -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 'Existing .venv needs Python 3.12+')"
if ($LASTEXITCODE -ne 0) { throw "Inspect the existing .venv; it was not replaced." }
& $venvPython -m pip install -e "${projectRoot}[dev,canvas]"
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed; inspect the error before retrying." }
& $venvPython -c "import mcp, pytest, yaml; print('Development environment ready:', __import__('sys').executable)"
if ($LASTEXITCODE -ne 0) { throw "Development environment verification failed." }
