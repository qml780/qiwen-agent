param([Parameter(Mandatory = $true)][string]$BackupPath)

$ErrorActionPreference = "Stop"
$resolvedBackup = (Resolve-Path -LiteralPath $BackupPath).Path
if (-not $resolvedBackup.StartsWith("D:\游戏agent\qiwen-verify\backups\", [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Only backups inside D:\游戏agent\qiwen-verify\backups may be restored."
}
$env:PGPASSWORD = "qiwen_local"
try {
    & "D:\qiwen-runtime\pgsql\bin\pg_restore.exe" -h 127.0.0.1 -p 55432 -U qiwen -d qiwen --clean --if-exists --no-owner $resolvedBackup
    if ($LASTEXITCODE -ne 0) { throw "Database restore failed." }
} finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
}
