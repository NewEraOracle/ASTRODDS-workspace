param(
  [string]$Workspace = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace",
  [switch]$SendClientLeanTelegram
)

$ErrorActionPreference = "Continue"
Set-Location $Workspace

$ScriptDir = Join-Path $Workspace "mlb-engine\baseballpred-inspired\scripts"
$ReportsDir = Join-Path $Workspace "mlb-engine\baseballpred-inspired\reports"

function Run-Py($Label, $Name) {
  $path = Join-Path $ScriptDir $Name
  Write-Host "Running $Label..."
  if (!(Test-Path $path)) {
    Write-Host "$Label missing: $path"
    return 1
  }
  $p = Start-Process python -ArgumentList "`"$path`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Write-Host "$Label exit code: $($p.ExitCode)"
  return $p.ExitCode
}

$codes = @()

# Refresh local PM/Fair/Edge board without spending odds credits.
$codes += Run-Py "Market PM exact team join 400" "400_market_pm_exact_team_join.py"
$codes += Run-Py "PM complement finalizer 403" "403_pm_join_complement_finalizer.py"
$codes += Run-Py "Moneyline live/status guard 229" "229_moneyline_strict_live_confirmation_guard.py"
$codes += Run-Py "Positive partner Top 6 261" "261_positive_partner_top6_board.py"
$codes += Run-Py "PM health audit 405" "405_pm_join_complement_health_audit.py"
$codes += Run-Py "Build client lean Telegram 409" "409_build_client_lean_telegram_message.py"

if ($SendClientLeanTelegram) {
  $send = Join-Path $ScriptDir "410_send_client_lean_telegram_safe.ps1"
  if (Test-Path $send) {
    powershell -ExecutionPolicy Bypass -File $send -Workspace $Workspace
  }
}

$codes += Run-Py "One-command status 500" "500_astrodds_one_command_status.py"
$codes += Run-Py "Clean client report 501" "501_clean_client_moneyline_report.py"

if ($codes | Where-Object { $_ -ne 0 }) {
  Write-Host "10/10 status cycle completed with warnings." -ForegroundColor Yellow
  exit 1
}

Write-Host "10/10 status cycle OK." -ForegroundColor Green
Write-Host ""
Write-Host "Status:"
Write-Host 'Get-Content ".\mlb-engine\baseballpred-inspired\reports\500_astrodds_one_command_status_report.txt" -Tail 160'
Write-Host ""
Write-Host "Client report:"
Write-Host 'Get-Content ".\mlb-engine\baseballpred-inspired\reports\501_clean_client_moneyline_report.txt" -Tail 160'
