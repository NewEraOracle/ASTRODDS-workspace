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
$codes += Run-Step "Column inspection 252" "252_inspect_moneyline_source_columns.py"
$codes += Run-Step "Strict team-side board 249" "249_source_first_strict_team_side_board.py"
$codes += Run-Step "Strict price extraction upgrade 253" "253_strict_price_extraction_upgrade.py"
$codes += Run-Step "Moneyline strict/fallback confirmation 229" "229_moneyline_strict_live_confirmation_guard.py"
$codes += Run-Step "Strict team-side health audit 251" "251_strict_team_side_health_audit.py"

if ($codes | Where-Object { $_ -ne 0 }) { exit 1 }
exit 0
