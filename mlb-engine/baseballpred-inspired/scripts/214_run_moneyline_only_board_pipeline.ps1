param(
  [string]$Workspace = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
)

$ErrorActionPreference = "Continue"
Set-Location $Workspace

$ScriptDir = Join-Path $Workspace "mlb-engine\baseballpred-inspired\scripts"
$Path213 = Join-Path $ScriptDir "213_moneyline_only_today_board.py"

Write-Host "Running Moneyline-only today board..."

if (-not (Test-Path $Path213)) {
  Write-Host "Moneyline-only board skipped: 213 script not found."
  exit 1
}

$p = Start-Process python -ArgumentList "`"$Path213`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
Write-Host "Moneyline-only today board exit code: $($p.ExitCode)"
exit $p.ExitCode
