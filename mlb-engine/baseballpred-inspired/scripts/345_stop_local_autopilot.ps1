$ErrorActionPreference = "Continue"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
$pidFile = Join-Path $astro "ASTRODDS-343-one-command-pid-latest.txt"
$outTxt = Join-Path $astro "ASTRODDS-345-stop-local-autopilot-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 345 STOP LOCAL AUTOPILOT" -ForegroundColor Cyan
Write-Host ""

$status = "NO_PID_FILE"
$pidText = ""

if (Test-Path $pidFile) {
    $pidText = (Get-Content $pidFile -Raw).Trim()
    try {
        $p = Get-Process -Id ([int]$pidText) -ErrorAction SilentlyContinue
        if ($null -ne $p) {
            Stop-Process -Id ([int]$pidText) -Force
            $status = "STOPPED_PID_$pidText"
        } else {
            $status = "PID_NOT_RUNNING_$pidText"
        }
    } catch {
        $status = "ERROR_STOPPING_PID_$pidText : $($_.Exception.Message)"
    }
}

$lines = @()
$lines += "ASTRODDS 345 STOP LOCAL AUTOPILOT"
$lines += ""
$lines += "Status: $status"
$lines += "PID file: $pidFile"
$lines += ""
$lines += "Note: this stops the autopilot PowerShell. It does not stop your npm dev server window."
($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
