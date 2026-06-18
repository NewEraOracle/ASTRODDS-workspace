param(
  [string]$Workspace = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace",
  [switch]$DryRun
)

$ErrorActionPreference = "Continue"
Set-Location $Workspace

$ScriptDir = Join-Path $Workspace "mlb-engine\baseballpred-inspired\scripts"

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

if (Test-Path (Join-Path $ScriptDir "400_market_pm_exact_team_join.py")) {
  Run-Py "Market PM exact team join 400" "400_market_pm_exact_team_join.py" | Out-Null
}
if (Test-Path (Join-Path $ScriptDir "403_pm_join_complement_finalizer.py")) {
  Run-Py "PM complement finalizer 403" "403_pm_join_complement_finalizer.py" | Out-Null
}
if (Test-Path (Join-Path $ScriptDir "261_positive_partner_top6_board.py")) {
  Run-Py "Positive partner Top 6 261" "261_positive_partner_top6_board.py" | Out-Null
}

Run-Py "Build client lean Telegram 409" "409_build_client_lean_telegram_message.py" | Out-Null

$sendScript = Join-Path $ScriptDir "410_send_client_lean_telegram_safe.ps1"
if (Test-Path $sendScript) {
  if ($DryRun) {
    powershell -ExecutionPolicy Bypass -File $sendScript -Workspace $Workspace -DryRun
  } else {
    powershell -ExecutionPolicy Bypass -File $sendScript -Workspace $Workspace
  }
} else {
  Write-Host "Send script missing: $sendScript"
  exit 1
}
