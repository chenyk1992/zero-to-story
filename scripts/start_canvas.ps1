param([int]$Port = 8765)

$ErrorActionPreference = "Stop"
$canvasProjectRoot = Split-Path -Parent $PSScriptRoot
$canvasPython = Join-Path $canvasProjectRoot '.venv/Scripts/python.exe'
& (Join-Path $PSScriptRoot 'check_environment.ps1') -StartupOnly
if ($LASTEXITCODE -ne 0) {
    throw '画布启动条件未满足。请按 scripts/check_environment.ps1 和 guides/windows-setup.md 的提示准备；项目不会自动下载安装。'
}
if (-not (Test-Path -LiteralPath $canvasPython)) {
    throw '请先准备项目 Python 环境，参阅 guides/canvas-guide.md。'
}
Push-Location $canvasProjectRoot
try {
    & $canvasPython -m lfo.canvas --port $Port open
    if ($LASTEXITCODE -ne 0) { throw '画布未启动，请根据上方提示处理。' }
} finally {
    Pop-Location
}
