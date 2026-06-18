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

# Ensure price complement is applied first when available.
if (Test-Path (Join-Path $ScriptDir "255_moneyline_complement_price_fill.py")) {
  $codes += Run-Step "Complement price fill 255" "255_moneyline_complement_price_fill.py"
}

$codes += Run-Step "Positive partner top6 board 261" "261_positive_partner_top6_board.py"
$codes += Run-Step "Partner parity debug 262" "262_partner_parity_debug_board.py"

if ($codes | Where-Object { $_ -ne 0 }) { exit 1 }
exit 0
