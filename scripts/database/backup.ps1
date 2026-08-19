$ErrorActionPreference = "Stop"
$backupRoot = "D:\游戏agent\qiwen-verify\backups"
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupPath = Join-Path $backupRoot "qiwen-$timestamp.dump"
New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
$env:PGPASSWORD = "qiwen_local"
try {
    & "D:\qiwen-runtime\pgsql\bin\pg_dump.exe" -h 127.0.0.1 -p 55432 -U qiwen -d qiwen -Fc -f $backupPath
    if ($LASTEXITCODE -ne 0) { throw "Database backup failed." }
} finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
}
Write-Output $backupPath
