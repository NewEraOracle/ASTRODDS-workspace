$Workspace = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$Runner = "$Workspace\mlb-engine\baseballpred-inspired\scripts\31_auto_daily_engine_runner.ps1"

$TaskPrefix = "ASTRODDS Engine V2"

$Times = @(
  @{ Name = "Morning"; Time = "11:00" },
  @{ Name = "Afternoon"; Time = "15:00" },
  @{ Name = "Evening"; Time = "19:00" }
)

foreach ($item in $Times) {
  $taskName = "$TaskPrefix $($item.Name)"

  schtasks /Delete /TN "$taskName" /F 2>$null

  schtasks /Create `
    /TN "$taskName" `
    /SC DAILY `
    /ST $item.Time `
    /TR "powershell.exe -ExecutionPolicy Bypass -File `"$Runner`"" `
    /RL LIMITED `
    /F

  Write-Host "Created task: $taskName at $($item.Time)"
}

Write-Host ""
Write-Host "ASTRODDS scheduled tasks created."
Write-Host "Runner:"
Write-Host $Runner
Write-Host ""
Write-Host "Check tasks with:"
Write-Host 'schtasks /Query /TN "ASTRODDS Engine V2 Morning" /V /FO LIST'
