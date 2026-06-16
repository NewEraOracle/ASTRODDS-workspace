$ErrorActionPreference = "Continue"

$Workspace = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
Set-Location $Workspace

$Report = Join-Path $Workspace "mlb-engine\baseballpred-inspired\reports\133_clean_daily_results_runner_report.txt"

function Add-Line($msg) {
  $line = "[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + "] " + $msg
  Add-Content $Report $line
  Write-Host $line
}

Remove-Item $Report -Force -ErrorAction SilentlyContinue

Add-Line "ASTRODDS clean daily results runner started"

Get-Content ".\.env.local" | ForEach-Object {
  if ($_ -match "^\s*([^#][^=]+)=(.*)$") {
    [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
  }
}

Add-Line "Running 132 resolver..."
python ".\mlb-engine\baseballpred-inspired\scripts\132_resolve_clean_moneyline_results_from_mlb.py"
Add-Line "132 resolver exit code: $LASTEXITCODE"

Add-Line "Running 131 Telegram clean report..."
python ".\mlb-engine\baseballpred-inspired\scripts\131_send_clean_moneyline_daily_results.py"
Add-Line "131 report exit code: $LASTEXITCODE"


Add-Line "Running 145 O/U resolver..."
python ".\mlb-engine\baseballpred-inspired\scripts\145_resolve_clean_ou_results_from_mlb.py"
Add-Line "145 O/U resolver exit code: $LASTEXITCODE"

Add-Line "Running 146 O/U Telegram clean report..."
python ".\mlb-engine\baseballpred-inspired\scripts\146_send_clean_ou_daily_results.py"
Add-Line "146 O/U report exit code: $LASTEXITCODE"

Add-Line "ASTRODDS clean daily results runner finished"

