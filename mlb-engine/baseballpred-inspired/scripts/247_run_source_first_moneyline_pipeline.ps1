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
$codes += Run-Step "Source-first official moneyline board 246" "246_source_first_official_moneyline_board.py"
$codes += Run-Step "Moneyline strict/fallback confirmation 229" "229_moneyline_strict_live_confirmation_guard.py"
$codes += Run-Step "Schedule locked health audit 242" "242_moneyline_schedule_locked_health_audit.py"
$codes += Run-Step "Source-first health audit 248" "248_source_first_moneyline_health_audit.py"

if ($codes | Where-Object { $_ -ne 0 }) { exit 1 }
exit 0
