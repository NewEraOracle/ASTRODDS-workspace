$Workspace = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$Report = Join-Path $Workspace "mlb-engine\baseballpred-inspired\reports\46_harden_tasks_gitignore_report.txt"
$GitIgnore = Join-Path $Workspace ".gitignore"

function Add-Line($text = "") {
  $script:Lines += $text
}

$Lines = @()
Add-Line "ASTRODDS 46 HARDEN TASKS + GITIGNORE REPORT"
Add-Line "================================================"
Add-Line "Generated: $(Get-Date -Format o)"
Add-Line ""
Add-Line "Workspace: $Workspace"
Add-Line ""

Set-Location $Workspace

Add-Line "STEP 1 — Harden Windows scheduled tasks"
Add-Line "----------------------------------------"

$taskNames = @(
  "ASTRODDS Engine V2 Morning",
  "ASTRODDS Engine V2 Afternoon",
  "ASTRODDS Engine V2 Evening"
)

foreach ($taskName in $taskNames) {
  try {
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction Stop

    $settings = New-ScheduledTaskSettingsSet `
      -StartWhenAvailable `
      -AllowStartIfOnBatteries `
      -DontStopIfGoingOnBatteries `
      -MultipleInstances IgnoreNew `
      -ExecutionTimeLimit (New-TimeSpan -Hours 2)

    Set-ScheduledTask -TaskName $taskName -Settings $settings | Out-Null

    Add-Line "OK: hardened $taskName"
  } catch {
    Add-Line "ERROR: could not harden $taskName"
    Add-Line "  $($_.Exception.Message)"
  }
}

Add-Line ""
Add-Line "STEP 2 — Verify scheduled tasks"
Add-Line "--------------------------------"

foreach ($taskName in $taskNames) {
  $result = schtasks /Query /TN $taskName /V /FO LIST 2>$null

  if ($LASTEXITCODE -eq 0) {
    Add-Line "OK: $taskName"
    $result | Select-String "Prochaine exécution|Next Run Time|Statut:|Status:|Gestion de l’alimentation|Power Management|Tâche à exécuter|Task To Run" | ForEach-Object {
      Add-Line "  $($_.ToString().Trim())"
    }
  } else {
    Add-Line "MISSING: $taskName"
  }
}

Add-Line ""
Add-Line "STEP 3 — Update .gitignore"
Add-Line "---------------------------"

if (!(Test-Path $GitIgnore)) {
  New-Item -ItemType File -Path $GitIgnore | Out-Null
  Add-Line "Created .gitignore"
}

$current = Get-Content $GitIgnore -ErrorAction SilentlyContinue

$patterns = @(
  "",
  "# ASTRODDS local secrets / runtime",
  ".env",
  ".env.*",
  "!.env.example",
  ".astrodds/",
  "",
  "# Python runtime",
  "**/__pycache__/",
  "*.pyc",
  "",
  "# Next.js / Node runtime",
  ".next/",
  "node_modules/",
  "",
  "# Local backup patches",
  "*.patch"
)

$added = 0

foreach ($pattern in $patterns) {
  if ($pattern -eq "") {
    continue
  }

  if ($current -notcontains $pattern) {
    Add-Content $GitIgnore $pattern
    $current += $pattern
    $added += 1
  }
}

Add-Line "Gitignore patterns added: $added"

Add-Line ""
Add-Line "STEP 4 — Git status after hardening"
Add-Line "------------------------------------"

$gitStatus = git status --short

if ($gitStatus) {
  Add-Line "DIRTY:"
  $gitStatus | ForEach-Object { Add-Line "- $_" }
} else {
  Add-Line "CLEAN"
}

Add-Line ""
Add-Line "Conclusion:"
Add-Line "46 completed. If scheduled task hardening shows errors, run PowerShell as Administrator later."
Add-Line "Rule: system hardening only. No real-money automation."

$Lines | Set-Content $Report -Encoding UTF8
$Lines
"`nSaved: $Report"
