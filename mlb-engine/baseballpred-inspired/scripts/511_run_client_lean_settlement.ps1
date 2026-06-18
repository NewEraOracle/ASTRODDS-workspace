param([string]$Workspace = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace")
$ErrorActionPreference = "Continue"
Set-Location $Workspace
$ScriptDir = Join-Path $Workspace "mlb-engine\baseballpred-inspired\scripts"
function Run-Py($Label, $Name) {
  $path = Join-Path $ScriptDir $Name
  Write-Host "Running $Label..."
  if (!(Test-Path $path)) { Write-Host "$Label missing: $path"; return 1 }
  $p = Start-Process python -ArgumentList "`"$path`"" -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru
  Write-Host "$Label exit code: $($p.ExitCode)"; return $p.ExitCode
}
Run-Py "Log client leans to ledger 508" "508_log_client_leans_to_ledger.py" | Out-Null
Run-Py "Resolve client lean results 509" "509_resolve_client_lean_results_from_mlb.py" | Out-Null
Run-Py "Client lean results report 510" "510_client_lean_results_report.py" | Out-Null
Write-Host ""
Write-Host "Reports:"
Write-Host 'Get-Content ".\mlb-engine\baseballpred-inspired\reports\508_log_client_leans_to_ledger_report.txt" -Tail 120'
Write-Host 'Get-Content ".\mlb-engine\baseballpred-inspired\reports\509_resolve_client_lean_results_from_mlb_report.txt" -Tail 160'
Write-Host 'Get-Content ".\mlb-engine\baseballpred-inspired\reports\510_client_lean_results_report.txt" -Tail 160'
