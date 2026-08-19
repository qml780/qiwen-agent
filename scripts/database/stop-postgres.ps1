$postgresData = "D:\qiwen-data\postgres18"
$pgCtl = "D:\qiwen-runtime\pgsql\bin\pg_ctl.exe"

if ((Test-Path -LiteralPath $pgCtl) -and (Test-Path -LiteralPath (Join-Path $postgresData "postmaster.pid"))) {
    & $pgCtl -D $postgresData stop -m fast
}
