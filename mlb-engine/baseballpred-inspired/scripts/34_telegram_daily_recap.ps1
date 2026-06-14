param()

$ErrorActionPreference = "Stop"

$Workspace = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$DailyPath = Join-Path $Workspace ".astrodds\ASTRODDS-daily-performance-latest.json"
$Report = Join-Path $Workspace "mlb-engine\baseballpred-inspired\reports\34_telegram_daily_recap_report.txt"

function Read-JsonFile {
  param([string]$Path, $Fallback)
  if (-not (Test-Path $Path)) { return $Fallback }
  try {
    return Get-Content $Path -Raw -Encoding UTF8 | ConvertFrom-Json
  } catch {
    return $Fallback
  }
}

function To-Number {
  param($Value)
  if ($null -eq $Value -or "$Value" -eq "") { return 0 }
  $S = "$Value".Replace(",", ".")
  $N = 0.0
  if ([double]::TryParse($S, [System.Globalization.NumberStyles]::Any, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$N)) {
    return $N
  }
  return 0
}

function Format-Units {
  param($Value)
  return "{0:N3}u" -f (To-Number $Value)
}

function Format-Percent {
  param($Value)
  if ($null -eq $Value -or "$Value" -eq "") { return "N/A" }
  $N = To-Number $Value
  if ($N -le 1) { $N = $N * 100 }
  return "{0:N1}%" -f $N
}

$Daily = Read-JsonFile $DailyPath $null

$Wins = 0
$Losses = 0
$Pending = 0
$Signals = 0
$WinRate = "N/A"
$Units = "0.000u"
$OfficialBuys = 0

if ($null -ne $Daily) {
  if ($null -ne $Daily.wins) { $Wins = [int]$Daily.wins }
  if ($null -ne $Daily.losses) { $Losses = [int]$Daily.losses }
  if ($null -ne $Daily.pending) { $Pending = [int]$Daily.pending }
  if ($null -ne $Daily.totalSignals) { $Signals = [int]$Daily.totalSignals }
  $WinRate = Format-Percent $Daily.winRate
  $Units = Format-Units $Daily.paperProfitUnits
  if ($null -ne $Daily.engineBuyCount) { $OfficialBuys = [int]$Daily.engineBuyCount }
}

$Lines = New-Object System.Collections.Generic.List[string]
$Lines.Add("ASTRODDS 34 DAILY RECAP REPORT")
$Lines.Add("==============================")
$Lines.Add("Generated: $(Get-Date -Format o)")
$Lines.Add("")
$Lines.Add("Status: REPORT_ONLY")
$Lines.Add("")
$Lines.Add("Telegram sending disabled here.")
$Lines.Add("Reason: public Telegram should only receive OFFICIAL BUY alerts and scheduled 11PM results.")
$Lines.Add("")
$Lines.Add("Signals: $Signals")
$Lines.Add("Wins: $Wins")
$Lines.Add("Losses: $Losses")
$Lines.Add("Pending: $Pending")
$Lines.Add("Win rate: $WinRate")
$Lines.Add("Paper units: $Units")
$Lines.Add("Official buys: $OfficialBuys")
$Lines.Add("")
$Lines.Add("Rule: report only. No Telegram send. No odds scan. No betting automation.")

$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($Report, ($Lines -join "`n"), $Utf8NoBom)

$Lines | ForEach-Object { Write-Host $_ }