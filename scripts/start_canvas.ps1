param([int]$Port = 8765)

$ErrorActionPreference = "Stop"
$canvasProjectRoot = Split-Path -Parent $PSScriptRoot
$canvasPython = Join-Path $canvasProjectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $canvasPython)) {
    throw '请先准备项目 Python 环境，参阅 docs/canvas-guide.md。'
}
Push-Location $canvasProjectRoot
try {
    & $canvasPython -m lfo.canvas --port $Port open
    if ($LASTEXITCODE -ne 0) { throw '画布未启动，请根据上方提示处理。' }
} finally {
    Pop-Location
}
