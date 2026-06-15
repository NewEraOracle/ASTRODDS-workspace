$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
Set-Location "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
python ".\mlb-engine\baseballpred-inspired\scripts\63_daily_12pm_results_alert.py"

Write-Host "Running ASTRODDS 120 daily verified results Telegram update..."
$Script120 = Join-Path $PSScriptRoot "120_daily_12pm_verified_results_telegram.py"

if (Test-Path $Script120) {
  python $Script120
  Write-Host "ASTRODDS 120 completed."
} else {
  Write-Host "ASTRODDS 120 skipped: script not found."
}

