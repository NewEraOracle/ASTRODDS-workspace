param(
  [string]$Workspace = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
)

$ErrorActionPreference = "Continue"
Set-Location $Workspace

Write-Host "ASTRODDS 515 CLIENT LEAN SETTLEMENT STATUS"
Write-Host "========================================================================"

$ledger = ".\.astrodds\ASTRODDS-client-lean-ledger.json"
$summary = ".\.astrodds\ASTRODDS-client-lean-results-summary-latest.json"

if (Test-Path $summary) {
  Get-Content $summary | ConvertFrom-Json | Select-Object totalClientLeans,settled,pending,wins,losses,winRate | Format-List
} else {
  Write-Host "No summary JSON yet."
}

Write-Host ""
Write-Host "Pending rows:"
if (Test-Path $ledger) {
  Get-Content $ledger | ConvertFrom-Json | Select-Object -ExpandProperty clientLeans |
    Where-Object { $_.status -eq "PENDING" } |
    Select-Object pick,game,edgePct,suggestedStake,status,result,mlbStatus |
    Format-Table -Wrap
} else {
  Write-Host "No ledger yet."
}

Write-Host ""
Write-Host "Latest reports:"
Write-Host 'Get-Content ".\mlb-engine\baseballpred-inspired\reports\510_client_lean_results_report.txt" -Tail 120'
Write-Host 'Get-Content ".\mlb-engine\baseballpred-inspired\reports\513_send_230am_client_lean_results_telegram_report.txt" -Tail 140'
