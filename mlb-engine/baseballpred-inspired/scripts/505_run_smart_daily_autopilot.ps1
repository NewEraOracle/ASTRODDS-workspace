param(
  [string]$Workspace = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace",
  [switch]$AutoFreshScan,
  [switch]$FreshScanNow,
  [switch]$SendClientLeanTelegram,
  [switch]$NoServerStart
)

$ErrorActionPreference = "Continue"
Set-Location $Workspace

$ScriptDir = Join-Path $Workspace "mlb-engine\baseballpred-inspired\scripts"
$ReportsDir = Join-Path $Workspace "mlb-engine\baseballpred-inspired\reports"
$AstroDir = Join-Path $Workspace ".astrodds"

Write-Host "ASTRODDS 505 SMART DAILY AUTOPILOT"
Write-Host "Workspace: $Workspace"
Write-Host "AutoFreshScan: $AutoFreshScan"
Write-Host "FreshScanNow: $FreshScanNow"
Write-Host "SendClientLeanTelegram: $SendClientLeanTelegram"

function Test-LocalServer {
  try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:3000" -UseBasicParsing -TimeoutSec 3
    return $true
  } catch {
    return $false
  }
}

if (-not $NoServerStart) {
  if (Test-LocalServer) {
    Write-Host "Local server: OK"
  } else {
    Write-Host "Local server: not responding. Starting npm dev in background..."
    $pkg = Join-Path $Workspace "package.json"
    if (Test-Path $pkg) {
      Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location `"$Workspace`"; npm run dev" -WindowStyle Minimized
      Start-Sleep -Seconds 8
    } else {
      Write-Host "package.json not found at workspace root. Skipping server start."
    }
    if (Test-LocalServer) { Write-Host "Local server: OK after start" } else { Write-Host "Local server: still not confirmed" }
  }
}

$planner = Join-Path $ScriptDir "504_smart_scan_window_planner.py"
if (Test-Path $planner) {
  python $planner
} else {
  Write-Host "Planner missing: $planner"
}

$planJson = Join-Path $AstroDir "ASTRODDS-504-smart-scan-window-plan-latest.json"
$freshDue = $false
if (Test-Path $planJson) {
  try {
    $plan = Get-Content $planJson -Raw | ConvertFrom-Json
    $freshDue = [bool]$plan.freshScanDueNow
  } catch {}
}

if ($FreshScanNow -or ($AutoFreshScan -and $freshDue)) {
  Write-Host "Fresh odds scan selected. Running 31 auto daily engine runner..."
  $runner31 = Join-Path $ScriptDir "31_auto_daily_engine_runner.ps1"
  if (Test-Path $runner31) {
    powershell -ExecutionPolicy Bypass -File $runner31
  } else {
    Write-Host "Runner 31 missing: $runner31"
  }
} else {
  Write-Host "No fresh odds scan needed now. Running local 10/10 status cycle only."
  $cycle502 = Join-Path $ScriptDir "502_run_10_of_10_status_cycle.ps1"
  if (Test-Path $cycle502) {
    if ($SendClientLeanTelegram) {
      powershell -ExecutionPolicy Bypass -File $cycle502 -Workspace $Workspace -SendClientLeanTelegram
    } else {
      powershell -ExecutionPolicy Bypass -File $cycle502 -Workspace $Workspace
    }
  } else {
    Write-Host "Cycle 502 missing: $cycle502"
  }
}

Write-Host ""
Write-Host "Planner report:"
Write-Host 'Get-Content ".\mlb-engine\baseballpred-inspired\reports\504_smart_scan_window_planner_report.txt" -Tail 180'
Write-Host ""
Write-Host "Status report:"
Write-Host 'Get-Content ".\mlb-engine\baseballpred-inspired\reports\500_astrodds_one_command_status_report.txt" -Tail 160'
