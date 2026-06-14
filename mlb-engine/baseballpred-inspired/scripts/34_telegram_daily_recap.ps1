param()

$ErrorActionPreference = "Stop"

function Get-Workspace {
  return "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
}

function Read-JsonFile {
  param([string]$Path, $Fallback)
  if (-not (Test-Path $Path)) { return $Fallback }
  try {
    return Get-Content $Path -Raw -Encoding UTF8 | ConvertFrom-Json
  } catch {
    return $Fallback
  }
}

function Write-JsonFile {
  param([string]$Path, $Object)
  $Dir = Split-Path -Parent $Path
  if ($Dir -and -not (Test-Path $Dir)) {
    New-Item -ItemType Directory -Path $Dir -Force | Out-Null
  }
  $Json = $Object | ConvertTo-Json -Depth 25
  $Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($Path, $Json, $Utf8NoBom)
}

function Get-EnvMap {
  param([string]$EnvPath)
  $Map = @{}
  if (-not (Test-Path $EnvPath)) { return $Map }
  foreach ($Line in Get-Content $EnvPath -Encoding UTF8) {
    if (-not $Line) { continue }
    $T = $Line.Trim()
    if ($T -eq "" -or $T.StartsWith("#")) { continue }
    $Idx = $T.IndexOf("=")
    if ($Idx -lt 1) { continue }
    $K = $T.Substring(0, $Idx).Trim()
    $V = $T.Substring($Idx + 1).Trim().Trim('"').Trim("'")
    $Map[$K] = $V
  }
  return $Map
}

function To-Number {
  param($Value)
  if ($null -eq $Value -or "$Value" -eq "") { return $null }
  $S = "$Value".Replace(",", ".")
  $N = 0.0
  if ([double]::TryParse($S, [System.Globalization.NumberStyles]::Any, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$N)) {
    return $N
  }
  return $null
}

function Format-Percent {
  param($Value)
  $N = To-Number $Value
  if ($null -eq $N) { return "N/A" }
  if ($N -le 1) { return "{0:N1}%" -f ($N * 100.0) }
  return "{0:N1}%" -f $N
}

function Format-Units {
  param($Value)
  $N = To-Number $Value
  if ($null -eq $N) { $N = 0 }
  return "{0:N3}u" -f $N
}

function Send-TelegramMessage {
  param([string]$Token, [string]$ChatId, [string]$Text)
  if (-not $Token -or -not $ChatId) {
    throw "Missing Telegram token/chat"
  }
  $Uri = "https://api.telegram.org/bot$Token/sendMessage"
  $Body = @{
    chat_id = $ChatId
    text = $Text
    disable_web_page_preview = "true"
  }
  Invoke-RestMethod -Method Post -Uri $Uri -Body $Body | Out-Null
}

function Send-TelegramDocument {
  param([string]$Token, [string]$ChatId, [string]$FilePath, [string]$Caption)
  if (-not $Token -or -not $ChatId) {
    throw "Missing Telegram token/chat"
  }
  $Uri = "https://api.telegram.org/bot$Token/sendDocument"
  & curl.exe -s -X POST $Uri `
    -F "chat_id=$ChatId" `
    -F "caption=$Caption" `
    -F "document=@$FilePath" | Out-Null
}

function Get-MontrealDateString {
  $Tz = [System.TimeZoneInfo]::FindSystemTimeZoneById("Eastern Standard Time")
  $Local = [System.TimeZoneInfo]::ConvertTime([DateTimeOffset]::UtcNow, $Tz)
  return $Local.ToString("yyyy-MM-dd")
}

function Get-MontrealDateFromUtcString {
  param([string]$UtcValue)
  if (-not $UtcValue) { return $null }
  try {
    $Dto = [DateTimeOffset]::Parse($UtcValue, [System.Globalization.CultureInfo]::InvariantCulture)
    $Tz = [System.TimeZoneInfo]::FindSystemTimeZoneById("Eastern Standard Time")
    $Local = [System.TimeZoneInfo]::ConvertTime($Dto, $Tz)
    return $Local.Date
  } catch {
    return $null
  }
}

$Workspace = Get-Workspace
$EnvMap = Get-EnvMap (Join-Path $Workspace ".env.local")
$Token = $EnvMap["TELEGRAM_BOT_TOKEN"]
$ChatId = $EnvMap["TELEGRAM_CHAT_ID"]

$DailyPath = Join-Path $Workspace ".astrodds\ASTRODDS-daily-performance-latest.json"
$LedgerPath = Join-Path $Workspace ".astrodds\ASTRODDS-engine-signal-ledger.json"

$Daily = Read-JsonFile $DailyPath $null
$Ledger = @(Read-JsonFile $LedgerPath @())

if ($null -eq $Daily) {
  throw "Missing daily performance JSON: $DailyPath"
}

$Wins = if ($null -ne $Daily.wins) { [int]$Daily.wins } else { 0 }
$Losses = if ($null -ne $Daily.losses) { [int]$Daily.losses } else { 0 }
$Pending = if ($null -ne $Daily.pending) { [int]$Daily.pending } else { 0 }
$Signals = if ($null -ne $Daily.totalSignals) { [int]$Daily.totalSignals } else { 0 }
$Resolved = $Wins + $Losses
$OfficialBuys = if ($null -ne $Daily.engineBuyCount) { [int]$Daily.engineBuyCount } else { 0 }

$Best = $null
$BestEdge = -999999.0
foreach ($Row in $Ledger) {
  $Edge = To-Number $Row.calibratedEdgePct
  if ($null -eq $Edge) { continue }
  if ($Edge -gt $BestEdge) {
    $BestEdge = $Edge
    $Best = $Row
  }
}

$Lines = New-Object System.Collections.Generic.List[string]
$Lines.Add("ASTRODDS DAILY RECAP")
$Lines.Add("")
$Lines.Add("Signals: $Signals")
$Lines.Add("Resolved: $Resolved")
$Lines.Add("Wins: $Wins")
$Lines.Add("Losses: $Losses")
$Lines.Add("Pending: $Pending")
$Lines.Add("Win rate: $(Format-Percent $Daily.winRate)")
$Lines.Add("Paper units: $(Format-Units $Daily.paperProfitUnits)")
$Lines.Add("Official buys: $OfficialBuys")

if ($Best) {
  $Lines.Add("")
  $Lines.Add("Best signal:")
  $Lines.Add("Pick: $($Best.pick)")
  $Lines.Add("Game: $($Best.game)")
  $Lines.Add("Result: $($Best.result)")
}

$Lines.Add("")
$Lines.Add("Proof log updated.")
$Lines.Add("Paper/manual only. No real-money automation.")

$Message = ($Lines -join "`n")
Send-TelegramMessage -Token $Token -ChatId $ChatId -Text $Message

Write-Host "ASTRODDS 34 CLEAN DAILY RECAP"
Write-Host "Status: OK"
Write-Host ""
Write-Host $Message