param(
  [string]$Workspace = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
)

$ErrorActionPreference = "Continue"
Set-Location $Workspace
$ScriptDir = Join-Path $Workspace "mlb-engine\baseballpred-inspired\scripts"

function Run-Step($Label, $FileName) {
  $path = Join-Path $ScriptDir $FileName
  Write-Host "Running $Label..."
  if (-not (Test-Path $path)) {
    Write-Host "$Label skipped: script not found."
    return 1
  }
  $p = Start-Process python -ArgumentList "`"$path`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Write-Host "$Label exit code: $($p.ExitCode)"
  return $p.ExitCode
}

$codes = @()
$codes += Run-Step "Moneyline board 213" "213_moneyline_only_today_board.py"
$codes += Run-Step "Authoritative MLB schedule filter 238" "238_authoritative_mlb_schedule_filter.py"
$codes += Run-Step "Official schedule price coverage audit 240" "240_official_schedule_price_coverage_audit.py"
$codes += Run-Step "Moneyline model bridge 216" "216_moneyline_model_bridge_from_292.py"
$codes += Run-Step "Moneyline two-side model coverage 234" "234_moneyline_two_side_model_coverage.py"
$codes += Run-Step "Moneyline current edge 219" "219_moneyline_recompute_current_edge.py"
$codes += Run-Step "Moneyline strict/fallback confirmation 229" "229_moneyline_strict_live_confirmation_guard.py"
$codes += Run-Step "Moneyline two-side health audit 236" "236_moneyline_two_side_health_audit.py"
$codes += Run-Step "Schedule locked health audit 242" "242_moneyline_schedule_locked_health_audit.py"

if ($codes | Where-Object { $_ -ne 0 }) { exit 1 }
exit 0
