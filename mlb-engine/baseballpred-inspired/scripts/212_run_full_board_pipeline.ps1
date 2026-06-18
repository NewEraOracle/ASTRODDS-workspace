param(
  [string]$Workspace = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
)

$ErrorActionPreference = "Continue"
Set-Location $Workspace

$ScriptDir = Join-Path $Workspace "mlb-engine\baseballpred-inspired\scripts"

function Run-BoardStep($Label, $FileName) {
  $path = Join-Path $ScriptDir $FileName
  Write-Host "Running $Label..."

  if (-not (Test-Path $path)) {
    Write-Host "$Label skipped: script not found."
    return 0
  }

  $p = Start-Process python -ArgumentList "`"$path`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Write-Host "$Label exit code: $($p.ExitCode)"
  return $p.ExitCode
}

$codes = @()
$codes += Run-BoardStep "O/U batting match audit" "199_fix_ou_batting_game_match_audit.py"
$codes += Run-BoardStep "BaseballPred full slate ranker" "198_baseballpred_full_slate_ranker.py"
$codes += Run-BoardStep "Full slate game board report" "200_astrodds_full_slate_game_board_report.py"
$codes += Run-BoardStep "Expanded Moneyline full slate board" "202_expand_moneyline_full_slate_board.py"
$codes += Run-BoardStep "Dedupe full slate game board" "203_dedupe_full_slate_game_board.py"
$codes += Run-BoardStep "Fixed Moneyline BaseballPred full slate board" "206_moneyline_baseballpred_full_slate_fixed.py"
$codes += Run-BoardStep "Moneyline-first full slate board report" "207_full_slate_game_board_moneyline_first_report.py"

if ($codes | Where-Object { $_ -ne 0 }) {
  exit 1
}

exit 0
