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


Add-Line "Running 154 O/U V1/V2 A-B report..."
python ".\mlb-engine\baseballpred-inspired\scripts\154_ou_v1_v2_ab_test_report.py"
Add-Line "154 O/U A-B report exit code: $LASTEXITCODE"

Add-Line "Running 158 postponed/suspended safety audit..."
python ".\mlb-engine\baseballpred-inspired\scripts\158_postponed_suspended_safety_audit.py"
Add-Line "158 postponed/suspended safety exit code: $LASTEXITCODE"


Add-Line "Running 164 full build validation..."
python ".\mlb-engine\baseballpred-inspired\scripts\164_full_build_validation_report.py"
Add-Line "164 full build validation exit code: $LASTEXITCODE"

Add-Line "Running 165 tomorrow review commands..."
python ".\mlb-engine\baseballpred-inspired\scripts\165_tomorrow_review_commands.py"
Add-Line "165 tomorrow review commands exit code: $LASTEXITCODE"


Add-Line "Running BaseballPred ROI/CLV backtest..."
python ".\mlb-engine\baseballpred-inspired\scripts\171_roi_clv_backtest_from_market_lines.py"
Add-Line "171 ROI/CLV backtest exit code: $LASTEXITCODE"

Add-Line "Running full BaseballPred gap report..."
python ".\mlb-engine\baseballpred-inspired\scripts\172_full_baseballpred_gap_report.py"
Add-Line "172 gap report exit code: $LASTEXITCODE"

Add-Line "ASTRODDS clean daily results runner finished"

