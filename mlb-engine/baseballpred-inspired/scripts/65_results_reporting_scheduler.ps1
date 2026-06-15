$Workspace = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
Set-Location $Workspace

$ReportsDir = Join-Path $Workspace "mlb-engine\baseballpred-inspired\reports"
$Report = Join-Path $ReportsDir "65_results_reporting_scheduler_report.txt"

$DailyScript = Join-Path $Workspace "mlb-engine\baseballpred-inspired\scripts\63_daily_12pm_results_alert.py"
$WeeklyScript = Join-Path $Workspace "mlb-engine\baseballpred-inspired\scripts\64_weekly_investor_results_report.py"

$DailyTask = "ASTRODDS Daily Results 12PM"
$WeeklyTask = "ASTRODDS Weekly Investor Results"

$DailyAction = "powershell.exe -ExecutionPolicy Bypass -Command `"cd '$Workspace'; python '$DailyScript'`""
$WeeklyAction = "powershell.exe -ExecutionPolicy Bypass -Command `"cd '$Workspace'; python '$WeeklyScript'`""

$Lines = New-Object System.Collections.Generic.List[string]
$Lines.Add("ASTRODDS 65 RESULTS REPORTING SCHEDULER REPORT")
$Lines.Add("================================================")
$Lines.Add("Generated: $(Get-Date -Format o)")
$Lines.Add("")
$Lines.Add("Workspace: $Workspace")
$Lines.Add("")

try {
  schtasks /Create /TN $DailyTask /TR $DailyAction /SC DAILY /ST 12:00 /F | Out-Null
  $Lines.Add("OK: scheduled daily results alert at 12:00 local Montreal/PC time")
} catch {
  $Lines.Add("ERROR: daily task schedule failed: $($_.Exception.Message)")
}

try {
  schtasks /Create /TN $WeeklyTask /TR $WeeklyAction /SC WEEKLY /D SUN /ST 23:10 /F | Out-Null
  $Lines.Add("OK: scheduled weekly investor report every Sunday at 23:10 local Montreal/PC time")
} catch {
  $Lines.Add("ERROR: weekly task schedule failed: $($_.Exception.Message)")
}

$Lines.Add("")
$Lines.Add("Verify tasks:")
foreach ($Task in @($DailyTask, $WeeklyTask)) {
  $Lines.Add("- $Task")
  $Info = schtasks /Query /TN $Task /FO LIST 2>$null
  if ($Info) {
    ($Info | Select-String "Prochaine exÃ©cution|Next Run Time|Statut|Status|TÃ¢che Ã  exÃ©cuter|Task To Run") | ForEach-Object {
      $Lines.Add("  $($_.Line)")
    }
  } else {
    $Lines.Add("  NOT FOUND")
  }
}

$Lines.Add("")
$Lines.Add("Rule: scheduler only. No odds scan. No betting automation.")

$Lines | Set-Content $Report -Encoding UTF8
$Lines | ForEach-Object { Write-Host $_ }
Write-Host ""
Write-Host "Saved: $Report"


