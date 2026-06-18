$ErrorActionPreference = "Continue"
$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$files = @(
    "ASTRODDS-FINAL-client-summary-latest.txt",
    "ASTRODDS-FINAL-admin-report-latest.txt",
    "ASTRODDS-312-final-readiness-gate-latest.txt",
    "ASTRODDS-325-elite-factors-report-latest.txt",
    "ASTRODDS-326-elite-gate-classification-audit-latest.txt",
    "ASTRODDS-330-autopilot-heartbeat-latest.txt"
)

foreach ($f in $files) {
    $p = Join-Path $astro $f
    if (Test-Path $p) { Start-Process notepad $p }
}
exit 0
