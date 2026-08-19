$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$workspaceRoot = Split-Path -Parent $projectRoot
$env:QIWEN_WORKSPACE_ROOT = $projectRoot
$runtimeRoot = $projectRoot
$apiRuntimeRoot = Join-Path $projectRoot "apps\api"
$apiPython = Join-Path $runtimeRoot ".venv\Scripts\python.exe"
$npmCommand = (Get-Command npm.cmd -ErrorAction Stop).Source
$nodeCommand = (Get-Command node.exe -ErrorAction Stop).Source
$databaseScriptPath = Join-Path $projectRoot "scripts\database\start-postgres.ps1"
$musicScriptPath = Join-Path $projectRoot "scripts\start-music-service.ps1"
$psql = "D:\qiwen-runtime\pgsql\bin\psql.exe"

# Windows PowerShell can expose PATH and Path as duplicate environment keys;
# normalize the process environment before Start-Process creates child processes.
$pathValue = [Environment]::GetEnvironmentVariable("Path", "Process")
if ($pathValue) {
    Remove-Item Env:PATH -ErrorAction SilentlyContinue
    [Environment]::SetEnvironmentVariable("Path", $pathValue, "Process")
}

if (-not (Test-Path -LiteralPath $apiPython)) {
    throw "Missing local runtime. Please reinstall project dependencies."
}

$env:PGPASSWORD = "qiwen_local"
try {
    $databaseReady = (& $psql -h 127.0.0.1 -p 55432 -U qiwen -d postgres -tAc "SELECT 1") -eq "1"
} catch {
    $databaseReady = $false
} finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
}
if (-not $databaseReady) {
    $databaseCode = Get-Content -LiteralPath $databaseScriptPath -Raw -Encoding UTF8
    & ([ScriptBlock]::Create($databaseCode))
}

$env:DATABASE_URL = "postgresql+psycopg://qiwen:qiwen_local@127.0.0.1:55432/qiwen"
Push-Location $apiRuntimeRoot
try {
    & $apiPython -m alembic upgrade head
} finally {
    Pop-Location
}
if ($LASTEXITCODE -ne 0) { throw "Database migration failed." }

# Music is a local dependency of the configured real provider. Start it before
# the API so a one-click launch cannot leave the Music Studio disconnected.
& $musicScriptPath

$existingApi = Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue
if ($existingApi) {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 3
        if ($health.database -ne "ok") {
            Stop-Process -Id $existingApi.OwningProcess -Force
            $existingApi = $null
        }
    } catch {
        Stop-Process -Id $existingApi.OwningProcess -Force -ErrorAction SilentlyContinue
        $existingApi = $null
    }
}

if (-not $existingApi) {
    Start-Process -FilePath $apiPython `
        -ArgumentList "-m", "app.server" `
        -WorkingDirectory $apiRuntimeRoot -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $workspaceRoot "qiwen-api.log") `
        -RedirectStandardError (Join-Path $workspaceRoot "qiwen-api-error.log")
}

$bridgeListener = Get-NetTCPConnection -State Listen -LocalPort 4567 -ErrorAction SilentlyContinue
if (-not $bridgeListener) {
    Start-Process -FilePath $nodeCommand -ArgumentList "apps\bridge\dist\server.js" `
        -WorkingDirectory $runtimeRoot -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $workspaceRoot "qiwen-bridge.log") `
        -RedirectStandardError (Join-Path $workspaceRoot "qiwen-bridge-error.log")
}

$webListener = Get-NetTCPConnection -State Listen -LocalPort 3000 -ErrorAction SilentlyContinue
if (-not $webListener) {
    Start-Process -FilePath $npmCommand -ArgumentList "run", "dev:web" `
        -WorkingDirectory $runtimeRoot -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $workspaceRoot "qiwen-web.log") `
        -RedirectStandardError (Join-Path $workspaceRoot "qiwen-web-error.log")
}

$deadline = (Get-Date).AddSeconds(30)
do {
    $webReady = Get-NetTCPConnection -State Listen -LocalPort 3000 -ErrorAction SilentlyContinue
    $apiReady = Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue
    $bridgeReady = Get-NetTCPConnection -State Listen -LocalPort 4567 -ErrorAction SilentlyContinue
    $musicReady = Get-NetTCPConnection -State Listen -LocalPort 8001 -ErrorAction SilentlyContinue
    if ($webReady -and $apiReady -and $bridgeReady -and $musicReady) { break }
    Start-Sleep -Milliseconds 400
} while ((Get-Date) -lt $deadline)

if (-not $webReady) { throw "Web startup timed out; check qiwen-web-error.log." }
if (-not $apiReady) { throw "API startup timed out; check qiwen-api-error.log." }
if (-not $bridgeReady) { throw "Local Bridge startup timed out; check qiwen-bridge-error.log." }
if (-not $musicReady) { throw "Music service startup timed out; check ace-step-api-error.log." }
Start-Process "http://127.0.0.1:3000"
