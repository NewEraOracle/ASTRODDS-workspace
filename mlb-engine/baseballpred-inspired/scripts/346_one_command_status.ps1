$ErrorActionPreference = "Continue"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

Write-Host ""
Write-Host "ASTRODDS 346 ONE-COMMAND STATUS" -ForegroundColor Cyan
Write-Host ""

$files = @(
    "ASTRODDS-343-one-command-heartbeat-latest.txt",
    "ASTRODDS-338-heartbeat-latest.txt",
    "ASTRODDS-337-smart-scan-window-planner-latest.txt",
    "ASTRODDS-FINAL-client-summary-latest.txt",
    "ASTRODDS-FINAL-admin-report-latest.txt",
    "ASTRODDS-326-elite-gate-classification-audit-latest.txt"
)

foreach ($f in $files) {
    $p = Join-Path $astro $f
    Write-Host ""
    Write-Host "===== $f =====" -ForegroundColor Cyan
    if (Test-Path $p) {
        Get-Content $p -TotalCount 80
    } else {
        Write-Host "Missing: $p" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "Open reports with: npm run astrodds:reports" -ForegroundColor Green
exit 0
