param(
  [string]$Workspace = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
)

$ErrorActionPreference = "Continue"
Set-Location $Workspace

$ScriptDir = Join-Path $Workspace "mlb-engine\baseballpred-inspired\scripts"
$ReportDir = Join-Path $Workspace "mlb-engine\baseballpred-inspired\reports"
$RunReport = Join-Path $ReportDir "512_auto_settle_client_leans_loop_report.txt"

$lines = @()
$lines += "ASTRODDS 512 AUTO SETTLE CLIENT LEANS LOOP"
$lines += "========================================================================"
$lines += "Generated UTC: $((Get-Date).ToUniversalTime().ToString('o'))"
$lines += "Workspace: $Workspace"
$lines += ""

$settle = Join-Path $ScriptDir "511_run_client_lean_settlement.ps1"
if (!(Test-Path $settle)) {
  $lines += "Status: MISSING_511_SETTLEMENT_RUNNER"
  $lines += "Path: $settle"
  Set-Content $RunReport ($lines -join "`n") -Encoding UTF8
  Write-Host ($lines -join "`n")
  exit 1
}

$lines += "Running 511 settlement cycle..."
Set-Content $RunReport ($lines -join "`n") -Encoding UTF8

powershell -ExecutionPolicy Bypass -File $settle -Workspace $Workspace

$resultsReport = Join-Path $ReportDir "510_client_lean_results_report.txt"
if (Test-Path $resultsReport) {
  $tail = Get-Content $resultsReport -Tail 80
  $lines += ""
  $lines += "Latest 510 report tail:"
  $lines += $tail
} else {
  $lines += "510 report not found after settlement run."
}

$lines += ""
$lines += "Status: DONE"
$lines += "Rule: resolves only games that MLB marks Final/Game Over. Pending stays pending."

Set-Content $RunReport ($lines -join "`n") -Encoding UTF8
Write-Host ($lines -join "`n")
