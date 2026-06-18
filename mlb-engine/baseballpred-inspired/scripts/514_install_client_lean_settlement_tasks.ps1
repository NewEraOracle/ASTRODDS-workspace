param(
  [string]$Workspace = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace",
  [string]$SettleTaskName = "ASTRODDS Client Lean Auto Settlement",
  [string]$ReportTaskName = "ASTRODDS 230AM Client Lean Results"
)

$ErrorActionPreference = "Continue"

$settleScript = Join-Path $Workspace "mlb-engine\baseballpred-inspired\scripts\512_auto_settle_client_leans_loop.ps1"
$reportScript = Join-Path $Workspace "mlb-engine\baseballpred-inspired\scripts\513_send_230am_client_lean_results_telegram.ps1"

if (!(Test-Path $settleScript)) { throw "Missing: $settleScript" }
if (!(Test-Path $reportScript)) { throw "Missing: $reportScript" }

# Settlement checker: every 30 minutes from 22:00 to 04:00.
$settleAction = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -File `"$settleScript`" -Workspace `"$Workspace`""
$settleTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddHours(22) -RepetitionInterval (New-TimeSpan -Minutes 30) -RepetitionDuration (New-TimeSpan -Hours 6)
$settleSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName $SettleTaskName -Action $settleAction -Trigger $settleTrigger -Settings $settleSettings -Force | Out-Null

# 2:30 AM report: run settlement first, then send report.
$wrapper = Join-Path $Workspace "mlb-engine\baseballpred-inspired\scripts\513b_run_230am_results_with_settlement.ps1"

@"
param(
  [string]`$Workspace = "$Workspace"
)

powershell -ExecutionPolicy Bypass -File "$settleScript" -Workspace "`$Workspace"
powershell -ExecutionPolicy Bypass -File "$reportScript" -Workspace "`$Workspace"
"@ | Set-Content $wrapper -Encoding UTF8

$reportAction = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -File `"$wrapper`" -Workspace `"$Workspace`""
$reportTrigger = New-ScheduledTaskTrigger -Daily -At "02:30"
$reportSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName $ReportTaskName -Action $reportAction -Trigger $reportTrigger -Settings $reportSettings -Force | Out-Null

Write-Host "Installed/updated:"
Write-Host "- ${SettleTaskName}: every 30 minutes from 22:00 for 6 hours"
Write-Host "- ${ReportTaskName}: daily at 02:30"
Write-Host ""
Write-Host "Check:"
Write-Host "Get-ScheduledTask -TaskName `"$SettleTaskName`""
Write-Host "Get-ScheduledTask -TaskName `"$ReportTaskName`""

