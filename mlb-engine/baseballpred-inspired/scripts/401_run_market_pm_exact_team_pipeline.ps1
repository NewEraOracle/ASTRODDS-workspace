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
$codes += Run-Step "Market PM exact team join 400" "400_market_pm_exact_team_join.py"
$codes += Run-Step "Moneyline strict/fallback confirmation 229" "229_moneyline_strict_live_confirmation_guard.py"

if (Test-Path (Join-Path $ScriptDir "261_positive_partner_top6_board.py")) {
  $codes += Run-Step "Positive partner top6 board 261" "261_positive_partner_top6_board.py"
}

if (Test-Path (Join-Path $ScriptDir "262_partner_parity_debug_board.py")) {
  $codes += Run-Step "Partner parity debug 262" "262_partner_parity_debug_board.py"
}

$codes += Run-Step "Market PM join health audit 402" "402_market_pm_join_health_audit.py"

if ($codes | Where-Object { $_ -ne 0 }) { exit 1 }
exit 0
