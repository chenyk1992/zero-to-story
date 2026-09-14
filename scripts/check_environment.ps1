[CmdletBinding()]
param([switch]$StartupOnly)

# Read-only Windows checks. Never install dependencies or start providers.
$ErrorActionPreference = 'Stop'
$checkRoot = Split-Path -Parent $PSScriptRoot
$checkPython = Join-Path $checkRoot '.venv/Scripts/python.exe'
$blocked = 0

function Report-Check([bool]$Okay, [string]$Name, [string]$Hint, [bool]$Required = $false) {
    if ($Okay) { Write-Host "[OK] $Name" }
    else {
        Write-Host "[$(if ($Required) { 'MISSING' } else { 'NOTICE' })] ${Name}: $Hint"
        if ($Required) { $script:blocked++ }
    }
}

$pythonOkay = $false
if (Test-Path -LiteralPath $checkPython -PathType Leaf) {
    try {
        & $checkPython -B -c "import sys; import lfo.canvas; assert sys.version_info >= (3, 12)" 2>$null
        $pythonOkay = $LASTEXITCODE -eq 0
    } catch { $pythonOkay = $false }
}
Report-Check $pythonOkay 'Project Python 3.12+ and lfo' 'Prepare Python 3.12 and a new project .venv; see guides/windows-setup.md.' $true
Report-Check (Test-Path -LiteralPath (Join-Path $checkRoot 'web/canvas/dist/index.html') -PathType Leaf) 'Canvas page build' 'After approving dependency installation, run npm ci and npm run build in web/canvas.' $true

if (-not $StartupOnly) {
    if ($pythonOkay) {
        $mcpOkay = $false
        try {
            & $checkPython -B -c "import mcp" 2>$null
            $mcpOkay = $LASTEXITCODE -eq 0
        } catch { $mcpOkay = $false }
        Report-Check $mcpOkay 'MCP Python dependency' 'Install the project canvas extra if using a host MCP connection.'
    }
    $nodeOkay = $false
    try {
        if (Get-Command node -ErrorAction SilentlyContinue) {
            & node -e "const [a,b]=process.versions.node.split('.').map(Number);process.exit((a===20&&b>=19)||(a===22&&b>=12)||a>22?0:1)" 2>$null
            $nodeOkay = $LASTEXITCODE -eq 0
        }
    } catch { $nodeOkay = $false }
    Report-Check $nodeOkay 'Node.js for page builds' 'Use a supported Node.js LTS version (20.19+ or 22.12+).'
    foreach ($commandName in @('npm', 'ffmpeg', 'ffprobe', 'comfy')) {
        $candidate = $commandName
        if ($commandName -eq 'comfy' -and $env:LFO_COMFY_CLI) { $candidate = $env:LFO_COMFY_CLI }
        if ($commandName -eq 'ffprobe' -and $env:LFO_FFPROBE) { $candidate = $env:LFO_FFPROBE }
        Report-Check ([bool](Get-Command $candidate -CommandType Application -ErrorAction SilentlyContinue)) "$commandName executable discovery" 'Prepare the executable in the service environment; see guides/windows-setup.md. Discovery does not verify it runs.'
    }
    foreach ($keyName in @('MIMO_API_KEY', 'MINIMAX_API_KEY')) {
        Report-Check (-not [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($keyName))) "$keyName presence (optional feature)" 'Configure only when using that API. Authentication and balance are not tested.'
    }
    Write-Host '[MANUAL] Verify host image tools, project Skills/MCP, audio/video review, and continuation support in the actual host.'
    Write-Host '[MANUAL] Verify running ComfyUI, custom nodes and models; the adapter preflights the selected workflow before submission.'
    Write-Host '[MANUAL] mmx requires its external Skill, CLI and authentication. Seedance is not integrated.'
}
Write-Host 'Read-only check finished. No downloads, installations, API generations or private-data migration were performed.'
Write-Host 'Only missing Canvas startup requirements affect the exit code; notices require checking the affected feature.'
if ($blocked -gt 0) { exit 1 }
exit 0
