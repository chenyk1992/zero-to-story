param([Parameter(Mandatory=$true)][string]$RuntimeRoot)
$ErrorActionPreference = 'Stop'
$serviceRoot = (Resolve-Path -LiteralPath $RuntimeRoot).Path
$configPath = Join-Path $serviceRoot 'runtime.json'
$runtime = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
$manifest = Get-Content -LiteralPath (Join-Path $serviceRoot 'installation.json') -Raw | ConvertFrom-Json
$serviceExe = Join-Path $serviceRoot 'xiaohongshu-mcp-windows-amd64.exe'
if ($manifest.repository -ne 'xpzouying/xiaohongshu-mcp' -or (Get-FileHash -LiteralPath $serviceExe -Algorithm SHA256).Hash -ne $manifest.sha256) {
  throw 'Installation identity/hash differs; inspect before starting'
}
$endpoint = [Uri]$runtime.base_url
if ($endpoint.Host -ne '127.0.0.1' -or $endpoint.Scheme -ne 'http') { throw 'Only loopback is supported' }
$listeners = @(Get-NetTCPConnection -State Listen -LocalPort $endpoint.Port -ErrorAction SilentlyContinue)
if ($listeners.Count -gt 0) {
  $existing = Get-Process -Id $runtime.process_id -ErrorAction SilentlyContinue
  if (-not $existing -or $existing.Path -ne $serviceExe -or @($listeners | Where-Object {$_.OwningProcess -ne $existing.Id -or $_.LocalAddress -ne '127.0.0.1'}).Count -gt 0) {
    throw 'Port is owned by another process or address; not replacing it'
  }
  Write-Output 'Existing local service reused; no restart'
  exit 0
}
$stateRoot = Join-Path $serviceRoot 'state'
$cacheRoot = (Resolve-Path -LiteralPath (Join-Path $serviceRoot $runtime.cache_root)).Path
$launchEnvironment = @{AUTH_TOKEN=[System.IO.File]::ReadAllText((Join-Path $serviceRoot $runtime.token_file)).Trim();COOKIES_PATH=(Join-Path $serviceRoot $runtime.cookie_file);LOCALAPPDATA=$cacheRoot}
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfff')
$serviceProcess = Start-Process -FilePath $serviceExe -ArgumentList @('-port',"127.0.0.1:$($endpoint.Port)",'-headless=true') -WorkingDirectory $serviceRoot -Environment $launchEnvironment -WindowStyle Hidden -RedirectStandardOutput (Join-Path $stateRoot "service-$stamp.stdout.log") -RedirectStandardError (Join-Path $stateRoot "service-$stamp.stderr.log") -PassThru
$runtime.process_id = $serviceProcess.Id
$runtime.started_at = [DateTime]::UtcNow.ToString('o')
$runtime | ConvertTo-Json | Set-Content -LiteralPath $configPath -Encoding utf8
Write-Output "Started local xiaohongshu-mcp $($runtime.version), process $($serviceProcess.Id); check status before collecting"
