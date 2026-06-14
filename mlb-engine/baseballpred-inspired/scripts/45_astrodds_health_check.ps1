$Workspace = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$Report = Join-Path $Workspace "mlb-engine\baseballpred-inspired\reports\45_astrodds_health_check_report.txt"

function Add-Line($text = "") {
  $script:Lines += $text
}

function Test-JsonCount($path) {
  if (!(Test-Path $path)) { return "MISSING" }
  try {
    $data = Get-Content $path -Raw | ConvertFrom-Json
    if ($null -eq $data) { return 0 }
    if ($data -is [array]) { return $data.Count }
    if ($data.PSObject.Properties.Name -contains "totalSignals") { return $data.totalSignals }
    return "OK_OBJECT"
  } catch {
    return "BAD_JSON"
  }
}

$Lines = @()
Add-Line "ASTRODDS 45 HEALTH CHECK REPORT"
Add-Line "===================================="
Add-Line "Generated: $(Get-Date -Format o)"
Add-Line ""
Add-Line "Workspace: $Workspace"
Add-Line ""

Set-Location $Workspace

Add-Line "Git status:"
$gitStatus = git status --short
if ($gitStatus) {
  Add-Line "DIRTY"
  $gitStatus | ForEach-Object { Add-Line "- $_" }
} else {
  Add-Line "CLEAN"
}

Add-Line ""
Add-Line "Core files:"
$files = @(
  ".env.local",
  "mlb-engine\baseballpred-inspired\scripts\31_auto_daily_engine_runner.ps1",
  "mlb-engine\baseballpred-inspired\scripts\44_telegram_review_recap.py",
  "mlb-engine\scripts\42_threshold_context_gate.py",
  "mlb-engine\baseballpred-inspired\models\ASTRODDS_ENGINE_V2_THRESHOLD_RULES.json",
  "public\astrodds-proof-log.html",
  "public\astrodds-proof-log.json"
)

foreach ($f in $files) {
  $p = Join-Path $Workspace $f
  if (Test-Path $p) {
    Add-Line "OK: $f"
  } else {
    Add-Line "MISSING: $f"
  }
}

Add-Line ""
Add-Line "Runtime JSON counts:"
$vvs = Test-JsonCount (Join-Path $Workspace ".astrodds\VVS-clean-final-latest.json")
$ledger = Test-JsonCount (Join-Path $Workspace ".astrodds\ASTRODDS-engine-signal-ledger.json")
$daily = Test-JsonCount (Join-Path $Workspace ".astrodds\ASTRODDS-daily-performance-latest.json")
$threshold = Test-JsonCount (Join-Path $Workspace ".astrodds\ASTRODDS-full-slate-context-threshold-final-latest.json")
$reviewLedger = Test-JsonCount (Join-Path $Workspace ".astrodds\ASTRODDS-telegram-review-recap-ledger.json")

Add-Line "VVS rows: $vvs"
Add-Line "Signal ledger rows: $ledger"
Add-Line "Daily total signals: $daily"
Add-Line "Threshold context rows: $threshold"
Add-Line "Telegram review recap ledger rows: $reviewLedger"

Add-Line ""
Add-Line "Scheduled tasks:"
$tasks = @(
  "ASTRODDS Engine V2 Morning",
  "ASTRODDS Engine V2 Afternoon",
  "ASTRODDS Engine V2 Evening"
)

foreach ($t in $tasks) {
  $result = schtasks /Query /TN $t /FO LIST 2>$null
  if ($LASTEXITCODE -eq 0) {
    $next = ($result | Select-String "Prochaine exécution|Next Run Time" | Select-Object -First 1).ToString()
    $status = ($result | Select-String "Statut:|Status:" | Select-Object -First 1).ToString()
    Add-Line "OK: $t"
    Add-Line "  $next"
    Add-Line "  $status"
  } else {
    Add-Line "MISSING: $t"
  }
}

Add-Line ""
Add-Line "Health conclusion:"
if (!$gitStatus -and "$vvs" -eq "5" -and "$ledger" -eq "5" -and "$daily" -eq "5") {
  Add-Line "STATUS: HEALTHY"
  Add-Line "ASTRODDS runner, ledger, daily report, and VVS input are clean."
} else {
  Add-Line "STATUS: REVIEW_NEEDED"
  Add-Line "Check git status or runtime counts."
}

Add-Line ""
Add-Line "Rule: health check only. No real-money automation."

$Lines | Set-Content $Report -Encoding UTF8
$Lines
"`nSaved: $Report"
