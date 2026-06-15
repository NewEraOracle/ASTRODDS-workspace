$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
Set-Location "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
python ".\mlb-engine\baseballpred-inspired\scripts\63_daily_12pm_results_alert.py"


Write-Host "Running ASTRODDS 121 verified results document Telegram update..."
$Script121 = Join-Path $PSScriptRoot "121_send_verified_results_documents_telegram.py"

if (Test-Path $Script121) {
  python $Script121
  Write-Host "ASTRODDS 121 completed."
} else {
  Write-Host "ASTRODDS 121 skipped: script not found."
}

