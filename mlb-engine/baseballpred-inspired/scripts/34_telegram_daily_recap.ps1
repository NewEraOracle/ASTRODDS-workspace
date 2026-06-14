$ErrorActionPreference = "Continue"

$Root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$EnvFile = Join-Path $Root ".env.local"
$PerfFile = Join-Path $Root ".astrodds\ASTRODDS-daily-performance-latest.json"
$LedgerFile = Join-Path $Root ".astrodds\ASTRODDS-telegram-recap-ledger.json"
$ReportFile = Join-Path $Root "mlb-engine\baseballpred-inspired\reports\34_telegram_daily_recap_report.txt"

function Get-EnvValue($name) {
  $line = Get-Content $EnvFile | Where-Object { $_ -match "^\s*$name\s*=" } | Select-Object -First 1
  if (-not $line) { return $null }
  return ($line -split "=", 2)[1].Trim().Trim('"').Trim("'")
}

function Mask($v) {
  if (-not $v) { return "" }
  if ($v.Length -le 8) { return "***" }
  return $v.Substring(0,4) + "***" + $v.Substring($v.Length - 4)
}

$token = Get-EnvValue "TELEGRAM_BOT_TOKEN"
$chat = Get-EnvValue "TELEGRAM_DEV_CHAT_ID"
if (-not $chat) { $chat = Get-EnvValue "TELEGRAM_CHAT_ID" }
if (-not $chat) { $chat = Get-EnvValue "TELEGRAM_SIGNALS_CHAT_ID" }

$perf = Get-Content $PerfFile -Raw | ConvertFrom-Json
$generatedAt = $perf.generatedAt
$recapKey = "daily_recap|$generatedAt"

if (Test-Path $LedgerFile) {
  $ledger = Get-Content $LedgerFile -Raw | ConvertFrom-Json
  if ($null -eq $ledger) { $ledger = @() }
  if ($ledger -isnot [System.Array]) { $ledger = @($ledger) }
} else {
  $ledger = @()
}

$alreadySent = $false
foreach ($item in $ledger) {
  if ($item.recapKey -eq $recapKey) {
    $alreadySent = $true
  }
}

$sent = 0
$skipped = 0
$errorText = ""

if ($alreadySent) {
  $skipped = 1
} else {
  $best = $perf.bestSignal

  $msg = @"
ASTRODDS DAILY RECAP

Signals: $($perf.totalSignals)
Resolved: $($perf.resolved)
Wins: $($perf.wins)
Losses: $($perf.losses)
Pending: $($perf.pending)
Paper units: $($perf.paperProfitUnits)u
ENGINE_BUY: $($perf.engineBuyCount)

Best signal:
$($best.game)
Pick: $($best.pick)
Decision: $($best.finalEngineDecision)
Grade: $($best.finalGrade)
Edge: $($best.calibratedEdgePct)%
Result: $($best.result)

Proof log updated.
Paper/manual only. No real-money automation.
"@

  try {
    $response = Invoke-RestMethod -Uri "https://api.telegram.org/bot$token/sendMessage" -Method Post -Body @{
      chat_id = $chat
      text = $msg
      disable_web_page_preview = "true"
    }

    $newItem = [PSCustomObject]@{
      sentAt = (Get-Date).ToUniversalTime().ToString("o")
      recapKey = $recapKey
      generatedAt = $generatedAt
      telegramOk = $response.ok
      paperOnly = $true
    }

    $ledger = @($ledger) + $newItem
    $ledger | ConvertTo-Json -Depth 10 | Set-Content $LedgerFile -Encoding UTF8
    $sent = 1
  } catch {
    $errorText = $_.Exception.Message
  }
}

$lines = @()
$lines += "ASTRODDS 34 TELEGRAM DAILY RECAP REPORT"
$lines += "================================================"
$lines += "Status: OK"
$lines += "Token: $(Mask $token)"
$lines += "Chat: $(Mask $chat)"
$lines += ""
$lines += "Performance generatedAt: $generatedAt"
$lines += "Sent this run: $sent"
$lines += "Skipped duplicate: $skipped"
$lines += "Ledger rows: $(@($ledger).Count)"
$lines += ""
$lines += "Signals: $($perf.totalSignals)"
$lines += "Resolved: $($perf.resolved)"
$lines += "Wins: $($perf.wins)"
$lines += "Losses: $($perf.losses)"
$lines += "Pending: $($perf.pending)"
$lines += "Paper units: $($perf.paperProfitUnits)u"
$lines += "ENGINE_BUY: $($perf.engineBuyCount)"
$lines += ""
$lines += "Rule: recap only. Paper/manual only. No real-money automation."

if ($errorText) {
  $lines += ""
  $lines += "Error:"
  $lines += $errorText
}

$lines += ""
$lines += "Recap ledger: $LedgerFile"

$lines | Set-Content $ReportFile -Encoding UTF8
$lines
