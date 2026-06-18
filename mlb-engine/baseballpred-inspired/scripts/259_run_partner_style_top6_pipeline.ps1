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

# If complement price fill exists, use it first. Otherwise use current board.
if (Test-Path (Join-Path $ScriptDir "255_moneyline_complement_price_fill.py")) {
  $codes += Run-Step "Complement price fill 255" "255_moneyline_complement_price_fill.py"
}

$codes += Run-Step "Moneyline strict/fallback confirmation 229" "229_moneyline_strict_live_confirmation_guard.py"
$codes += Run-Step "Partner style top 6 board 258" "258_partner_style_top6_moneyline_board.py"
$codes += Run-Step "Partner style top 6 health 260" "260_partner_style_top6_health_audit.py"

if ($codes | Where-Object { $_ -ne 0 }) { exit 1 }
exit 0
