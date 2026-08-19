$ErrorActionPreference = "Stop"
$postgresRoot = "D:\qiwen-runtime\pgsql"
$postgresData = "D:\qiwen-data\postgres18"
$workspaceRoot = $env:QIWEN_WORKSPACE_ROOT
if (-not $workspaceRoot) { throw "QIWEN_WORKSPACE_ROOT is required to start PostgreSQL." }
$postgresLog = Join-Path $workspaceRoot "qiwen-postgres.log"
$postgresPort = 55432
$binRoot = Join-Path $postgresRoot "bin"

if (-not (Test-Path -LiteralPath (Join-Path $binRoot "postgres.exe"))) {
    throw "PostgreSQL runtime is missing from D:\qiwen-runtime\pgsql."
}

if (-not (Test-Path -LiteralPath (Join-Path $postgresData "PG_VERSION"))) {
    New-Item -ItemType Directory -Path $postgresData -Force | Out-Null
    $passwordFile = "D:\qiwen-data\postgres-password.tmp"
    Set-Content -LiteralPath $passwordFile -Value "qiwen_local" -NoNewline -Encoding ascii
    try {
        & (Join-Path $binRoot "initdb.exe") -D $postgresData -U qiwen -A scram-sha-256 --pwfile=$passwordFile --encoding=UTF8 --locale=C
        if ($LASTEXITCODE -ne 0) { throw "initdb failed with exit code $LASTEXITCODE" }
    } finally {
        Remove-Item -LiteralPath $passwordFile -Force -ErrorAction SilentlyContinue
    }
}

$listener = Get-NetTCPConnection -State Listen -LocalPort $postgresPort -ErrorAction SilentlyContinue
if (-not $listener) {
    & (Join-Path $binRoot "pg_ctl.exe") -D $postgresData -l $postgresLog -o "-p $postgresPort -h 127.0.0.1" start
    if ($LASTEXITCODE -ne 0) { throw "PostgreSQL could not start." }
}

$env:PGPASSWORD = "qiwen_local"
foreach ($databaseName in @("qiwen", "qiwen_test")) {
    $exists = & (Join-Path $binRoot "psql.exe") -h 127.0.0.1 -p $postgresPort -U qiwen -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$databaseName'"
    if ($exists -ne "1") {
        & (Join-Path $binRoot "createdb.exe") -h 127.0.0.1 -p $postgresPort -U qiwen $databaseName
        if ($LASTEXITCODE -ne 0) { throw "Could not create database $databaseName." }
    }
}
Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
