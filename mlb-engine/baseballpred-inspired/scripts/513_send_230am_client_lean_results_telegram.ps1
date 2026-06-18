param(
  [string]$Workspace = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace",
  [switch]$DryRun
)

$ErrorActionPreference = "Continue"
Set-Location $Workspace

$AstroDir = Join-Path $Workspace ".astrodds"
$ReportDir = Join-Path $Workspace "mlb-engine\baseballpred-inspired\reports"
New-Item -ItemType Directory -Force $ReportDir | Out-Null

$SummaryJson = Join-Path $AstroDir "ASTRODDS-client-lean-results-summary-latest.json"
$SendReport = Join-Path $ReportDir "513_send_230am_client_lean_results_telegram_report.txt"

$lines = @()
$lines += "ASTRODDS 513 SEND 2:30AM CLIENT LEAN RESULTS TELEGRAM"
$lines += "========================================================================"
$lines += "Generated UTC: $((Get-Date).ToUniversalTime().ToString('o'))"
$lines += "DryRun: $DryRun"
$lines += ""

if (!(Test-Path $SummaryJson)) {
  $lines += "Status: NO_RESULTS_SUMMARY_JSON"
  Set-Content $SendReport ($lines -join "`n") -Encoding UTF8
  Write-Host ($lines -join "`n")
  exit 1
}

$summary = Get-Content $SummaryJson -Raw | ConvertFrom-Json

$total = [int]$summary.totalClientLeans
$settled = [int]$summary.settled
$pending = [int]$summary.pending
$wins = [int]$summary.wins
$losses = [int]$summary.losses
$winRate = $summary.winRate

$msg = @()
$msg += "ASTRODDS 2:30AM RESULTS REPORT"
$msg += ""
$msg += "Client leans:"
$msg += "Total: $total"
$msg += "Settled: $settled"
$msg += "Pending: $pending"
$msg += "Wins: $wins"
$msg += "Losses: $losses"
if ($null -ne $winRate) {
  $msg += "Win rate: $winRate%"
} else {
  $msg += "Win rate: N/A"
}
$msg += ""

if ($summary.rows) {
  foreach ($r in $summary.rows) {
    $status = $r.status
    $result = if ($r.result) { $r.result } else { "PENDING" }
    $pick = $r.pick
    $game = $r.game
    $edge = $r.edgePct
    $stake = $r.suggestedStake
    $msg += "$status / $result - $pick ML"
    $msg += "Game: $game"
    $msg += "Edge: +$edge%"
    $msg += "Stake: $stake"
    if ($r.winner) { $msg += "Winner: $($r.winner)" }
    if ($r.awayScore -ne $null -and $r.homeScore -ne $null) { $msg += "Score: $($r.awayScore)-$($r.homeScore)" }
    $msg += ""
  }
} else {
  $msg += "No client leans logged yet."
  $msg += ""
}

$msg += "Rule: client leans are separate from official A_PICKs."
$msg += "Paper/manual only. No real-money automation."

$message = ($msg -join "`n")

$lines += "Message preview:"
$lines += $message
$lines += ""

if ($DryRun) {
  $lines += "Status: DRY_RUN_NO_SEND"
  Set-Content $SendReport ($lines -join "`n") -Encoding UTF8
  Write-Host ($lines -join "`n")
  exit 0
}

$envPath = Join-Path $Workspace ".env.local"
if (Test-Path $envPath) {
  Get-Content $envPath | ForEach-Object {
    if ($_ -match '^\s*([^#][A-Za-z0-9_]+)\s*=\s*(.+)\s*$') {
      $name = $matches[1]
      $value = $matches[2].Trim('"').Trim("'")
      [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
  }
}

$token = $env:TELEGRAM_BOT_TOKEN
if (-not $token) { $token = $env:ASTRODDS_TELEGRAM_BOT_TOKEN }

$chatId = $env:TELEGRAM_RESULTS_CHAT_ID
if (-not $chatId) { $chatId = $env:TELEGRAM_CLIENT_LEAN_CHAT_ID }
if (-not $chatId) { $chatId = $env:TELEGRAM_CHAT_ID }
if (-not $chatId) { $chatId = $env:ASTRODDS_TELEGRAM_CHAT_ID }

if (-not $token -or -not $chatId) {
  $lines += "Status: SKIPPED_MISSING_TELEGRAM_ENV"
  $lines += "Need TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID or TELEGRAM_RESULTS_CHAT_ID."
  Set-Content $SendReport ($lines -join "`n") -Encoding UTF8
  Write-Host ($lines -join "`n")
  exit 0
}

# Dedupe by date + message hash.
$today = (Get-Date).ToString("yyyy-MM-dd")
$dedupePath = Join-Path $AstroDir "ASTRODDS-230am-client-lean-results-dedupe-$today.txt"
$msgHash = [System.BitConverter]::ToString([System.Security.Cryptography.SHA256]::Create().ComputeHash([System.Text.Encoding]::UTF8.GetBytes($message))).Replace("-", "")

if (Test-Path $dedupePath) {
  $lastHash = (Get-Content $dedupePath -Raw).Trim()
  if ($lastHash -eq $msgHash) {
    $lines += "Status: SKIPPED_DUPLICATE_RESULTS_MESSAGE"
    Set-Content $SendReport ($lines -join "`n") -Encoding UTF8
    Write-Host ($lines -join "`n")
    exit 0
  }
}

try {
  $uri = "https://api.telegram.org/bot$token/sendMessage"
  $body = @{
    chat_id = $chatId
    text = $message
    disable_web_page_preview = $true
  }
  $resp = Invoke-RestMethod -Method Post -Uri $uri -Body $body -TimeoutSec 20
  Set-Content $dedupePath $msgHash -Encoding UTF8
  $lines += "Status: SENT"
  $lines += "TelegramOK: $($resp.ok)"
} catch {
  $lines += "Status: SEND_FAILED"
  $lines += "Error: $($_.Exception.Message)"
}

Set-Content $SendReport ($lines -join "`n") -Encoding UTF8
Write-Host ($lines -join "`n")
