param(
  [string]$Workspace = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace",
  [switch]$DryRun
)

$ErrorActionPreference = "Continue"
Set-Location $Workspace

$AstroDir = Join-Path $Workspace ".astrodds"
$ReportDir = Join-Path $Workspace "mlb-engine\baseballpred-inspired\reports"
New-Item -ItemType Directory -Force $ReportDir | Out-Null

$MessageJson = Join-Path $AstroDir "ASTRODDS-client-lean-telegram-message-latest.json"
$Report = Join-Path $ReportDir "410_send_client_lean_telegram_safe_report.txt"

$lines = @()
$lines += "ASTRODDS 410 SEND CLIENT LEAN TELEGRAM SAFE"
$lines += "========================================================================"
$lines += "Generated UTC: $((Get-Date).ToUniversalTime().ToString('o'))"
$lines += ""
$lines += "DryRun: $DryRun"

if (!(Test-Path $MessageJson)) {
  $lines += "Status: NO_MESSAGE_JSON"
  Set-Content $Report ($lines -join "`n") -Encoding UTF8
  Write-Host ($lines -join "`n")
  exit 1
}

$msgObj = Get-Content $MessageJson -Raw | ConvertFrom-Json
$shouldSend = [bool]$msgObj.shouldSend
$message = [string]$msgObj.telegramMessage

$lines += "ShouldSend: $shouldSend"
$lines += "Reason: $($msgObj.reason)"
$lines += ""

if (-not $shouldSend) {
  $lines += "Status: SKIPPED_NO_ELIGIBLE_CLIENT_LEAN"
  Set-Content $Report ($lines -join "`n") -Encoding UTF8
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

$chatId = $env:TELEGRAM_CLIENT_LEAN_CHAT_ID
if (-not $chatId) { $chatId = $env:TELEGRAM_CHAT_ID }
if (-not $chatId) { $chatId = $env:ASTRODDS_TELEGRAM_CHAT_ID }

if ($DryRun) {
  $lines += "Status: DRY_RUN_NO_SEND"
  $lines += ""
  $lines += "Message:"
  $lines += $message
  Set-Content $Report ($lines -join "`n") -Encoding UTF8
  Write-Host ($lines -join "`n")
  exit 0
}

if (-not $token -or -not $chatId) {
  $lines += "Status: SKIPPED_MISSING_TELEGRAM_ENV"
  $lines += "Need TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID in .env.local or environment."
  $lines += ""
  $lines += "Message preview:"
  $lines += $message
  Set-Content $Report ($lines -join "`n") -Encoding UTF8
  Write-Host ($lines -join "`n")
  exit 0
}

$dedupePath = Join-Path $AstroDir "ASTRODDS-client-lean-telegram-dedupe-latest.txt"
$msgHash = [System.BitConverter]::ToString([System.Security.Cryptography.SHA256]::Create().ComputeHash([System.Text.Encoding]::UTF8.GetBytes($message))).Replace("-", "")

if (Test-Path $dedupePath) {
  $lastHash = (Get-Content $dedupePath -Raw).Trim()
  if ($lastHash -eq $msgHash) {
    $lines += "Status: SKIPPED_DUPLICATE_MESSAGE"
    Set-Content $Report ($lines -join "`n") -Encoding UTF8
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

Set-Content $Report ($lines -join "`n") -Encoding UTF8
Write-Host ($lines -join "`n")
