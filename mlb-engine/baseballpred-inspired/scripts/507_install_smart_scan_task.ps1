param(
  [string]$Workspace = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace",
  [string]$TaskName = "ASTRODDS Smart Scan Autopilot"
)

$ErrorActionPreference = "Continue"

$script = Join-Path $Workspace "mlb-engine\baseballpred-inspired\scripts\505_run_smart_daily_autopilot.ps1"
if (!(Test-Path $script)) {
  throw "Autopilot script missing: $script"
}

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -File `"$script`" -Workspace `"$Workspace`" -AutoFreshScan -SendClientLeanTelegram"
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddHours(9) -RepetitionInterval (New-TimeSpan -Minutes 20) -RepetitionDuration (New-TimeSpan -Hours 14)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null

Write-Host "Installed/updated task: $TaskName"
Write-Host "Runs every 20 minutes between roughly 9:00 and 23:00 local time."
Write-Host "The planner decides whether to do fresh odds scan or local status only."
Write-Host ""
Write-Host "Check task:"
Write-Host "Get-ScheduledTask -TaskName `"$TaskName`""
