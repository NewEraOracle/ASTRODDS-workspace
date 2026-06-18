param(
  [string]$Workspace = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
)

$ErrorActionPreference = "Continue"
Set-Location $Workspace

$ScriptDir = Join-Path $Workspace "mlb-engine\baseballpred-inspired\scripts"

$Script213 = Join-Path $ScriptDir "213_moneyline_only_today_board.py"
$Script216 = Join-Path $ScriptDir "216_moneyline_model_bridge_from_292.py"
$Script219 = Join-Path $ScriptDir "219_moneyline_recompute_current_edge.py"

Write-Host "Running Moneyline-only board 213..."
$p213 = Start-Process python -ArgumentList "`"$Script213`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
Write-Host "Moneyline-only board 213 exit code: $($p213.ExitCode)"
if ($p213.ExitCode -ne 0) { exit $p213.ExitCode }

Write-Host "Running Moneyline model bridge 216..."
$p216 = Start-Process python -ArgumentList "`"$Script216`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
Write-Host "Moneyline model bridge 216 exit code: $($p216.ExitCode)"
if ($p216.ExitCode -ne 0) { exit $p216.ExitCode }

Write-Host "Running Moneyline current edge recompute 219..."
$p219 = Start-Process python -ArgumentList "`"$Script219`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
Write-Host "Moneyline current edge recompute 219 exit code: $($p219.ExitCode)"
exit $p219.ExitCode
