$ErrorActionPreference = "Continue"
$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$files = @(
    "ASTRODDS-337-smart-scan-window-planner-latest.txt",
    "ASTRODDS-338-AUTOPILOT-SERVER-SCAN-CYCLE-latest.txt",
    "ASTRODDS-339-autopilot-loop-heartbeat-latest.txt",
    "ASTRODDS-FINAL-client-summary-latest.txt",
    "ASTRODDS-FINAL-admin-report-latest.txt",
    "ASTRODDS-326-elite-gate-classification-audit-latest.txt"
)

foreach ($f in $files) {
    $p = Join-Path $astro $f
    if (Test-Path $p) { Start-Process notepad $p }
}
exit 0
