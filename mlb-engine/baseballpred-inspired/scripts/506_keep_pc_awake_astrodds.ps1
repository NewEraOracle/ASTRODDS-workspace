param(
  [string]$Workspace = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace",
  [switch]$SendClientLeanTelegram
)

$ErrorActionPreference = "Continue"
Set-Location $Workspace

Write-Host "ASTRODDS 506 KEEP PC AWAKE + SMART AUTOPILOT"
Write-Host "Leave this window open. Press CTRL+C to stop."
Write-Host "This does not force fresh odds scans unless planner says a scan window is due."

# Prevent sleep on AC power.
powercfg /change standby-timeout-ac 0 | Out-Null
powercfg /change hibernate-timeout-ac 0 | Out-Null
powercfg /change monitor-timeout-ac 0 | Out-Null

$autopilot = Join-Path $Workspace "mlb-engine\baseballpred-inspired\scripts\505_run_smart_daily_autopilot.ps1"

while ($true) {
  Write-Host ""
  Write-Host "============================================================"
  Write-Host "ASTRODDS autopilot tick: $(Get-Date)"
  Write-Host "============================================================"

  if (Test-Path $autopilot) {
    if ($SendClientLeanTelegram) {
      powershell -ExecutionPolicy Bypass -File $autopilot -Workspace $Workspace -AutoFreshScan -SendClientLeanTelegram
    } else {
      powershell -ExecutionPolicy Bypass -File $autopilot -Workspace $Workspace -AutoFreshScan
    }
  } else {
    Write-Host "Autopilot script missing: $autopilot"
  }

  Write-Host "Sleeping 20 minutes..."
  Start-Sleep -Seconds 1200
}
