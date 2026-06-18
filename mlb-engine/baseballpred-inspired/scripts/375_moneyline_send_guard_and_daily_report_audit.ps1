$ErrorActionPreference = "Continue"


function Ensure-Dir($path) {
    if (!(Test-Path $path)) { New-Item -ItemType Directory -Force -Path $path | Out-Null }
}

function Safe-Csv($path) {
    if (!(Test-Path $path)) { return @() }
    try { return @(Import-Csv $path) } catch { return @() }
}

function Get-Val($row, $names) {
    if ($null -eq $row) { return "" }
    foreach ($n in @($names)) {
        try {
            $p = $row.PSObject.Properties[$n]
            if ($null -ne $p -and $null -ne $p.Value) {
                $v = "$($p.Value)".Trim()
                if ($v -ne "") { return $v }
            }
        } catch {}
    }
    return ""
}

function Num($v) {
    if ($null -eq $v) { return $null }
    $s = "$v".Trim()
    if ($s -eq "") { return $null }
    $s = $s.Replace("%","").Replace("¢","").Replace(",", ".")
    $n = 0.0
    $culture = [System.Globalization.CultureInfo]::InvariantCulture
    if ([double]::TryParse($s, [System.Globalization.NumberStyles]::Any, $culture, [ref]$n)) { return $n }
    return $null
}

function Normalize-Name($s) {
    $x = "$s".ToLower().Trim()
    $x = $x -replace "[^a-z0-9 ]", ""
    $x = $x -replace "\s+", " "
    return $x
}

function Read-JsonSafe($path) {
    if (!(Test-Path $path)) { return $null }
    try { return Get-Content $path -Raw | ConvertFrom-Json } catch { return $null }
}

function Run-Step($name, $path, [ref]$childLog) {
    $start = Get-Date
    Write-Host "Running $name..." -ForegroundColor Cyan

    if (!(Test-Path $path)) {
        Write-Host "MISSING: $path" -ForegroundColor Yellow
        return [pscustomobject]@{Name=$name;Status="MISSING";ExitCode="";DurationSec=0}
    }

    try {
        $output = & powershell -ExecutionPolicy Bypass -File $path 2>&1
        $exit = $LASTEXITCODE
        $dur = [math]::Round(((Get-Date)-$start).TotalSeconds,2)

        $childLog.Value += ""
        $childLog.Value += "============================================================"
        $childLog.Value += "STEP: $name"
        $childLog.Value += "PATH: $path"
        $childLog.Value += "EXIT: $exit"
        $childLog.Value += "DURATION: $dur sec"
        $childLog.Value += "============================================================"
        $childLog.Value += @($output | ForEach-Object { "$_" })

        if ($exit -eq 0 -or $null -eq $exit) {
            Write-Host "OK: $name ($dur sec)" -ForegroundColor Green
            return [pscustomobject]@{Name=$name;Status="OK";ExitCode="0";DurationSec=$dur}
        } else {
            Write-Host "ERROR: $name ($exit)" -ForegroundColor Red
            return [pscustomobject]@{Name=$name;Status="ERROR";ExitCode="$exit";DurationSec=$dur}
        }
    } catch {
        $dur = [math]::Round(((Get-Date)-$start).TotalSeconds,2)
        $childLog.Value += ""
        $childLog.Value += "ERROR STEP: $name"
        $childLog.Value += "$($_.Exception.Message)"
        return [pscustomobject]@{Name=$name;Status="ERROR";ExitCode="1";DurationSec=$dur}
    }
}

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$productionTelegram = Join-Path $astro "ASTRODDS-telegram-PRODUCTION-final-latest.txt"
$plannerJson = Join-Path $astro "ASTRODDS-337-smart-scan-window-planner-latest.json"
$outTxt = Join-Path $astro "ASTRODDS-375-moneyline-send-guard-and-daily-report-audit-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-375-moneyline-send-guard-and-daily-report-audit-latest.json"

Write-Host ""
Write-Host "ASTRODDS 375 MONEYLINE SEND GUARD + DAILY REPORT AUDIT" -ForegroundColor Cyan
Write-Host "Audits that Moneyline send is pre-game only; 2:30AM is report only." -ForegroundColor Cyan
Write-Host ""

$telegram = ""
if (Test-Path $productionTelegram) { $telegram = Get-Content $productionTelegram -Raw }

$planner = Read-JsonSafe $plannerJson
$globalAction = ""
try { $globalAction = "$($planner.globalAction)" } catch {}

$hasOfficialPick = ($telegram -match "OFFICIAL PICKS|STRONG BUY|VALUE BUY")
$blockedMessage = ($telegram -match "No new official picks|NEW CLIENT DROP BLOCKED|No new picks")
$sendMode = if ($env:ASTRODDS_TELEGRAM_SEND -eq "YES") { "SEND" } else { "DRYRUN_OR_NOT_SET" }

$auditStatus = "SAFE"
$warnings = @()

if ($hasOfficialPick -and $globalAction -ne "RUN_FULL_PRODUCTION_SCAN") {
    $auditStatus = "REVIEW"
    $warnings += "Official pick text exists while planner globalAction is not RUN_FULL_PRODUCTION_SCAN."
}

$lines = @()
$lines += "ASTRODDS 375 MONEYLINE SEND GUARD + DAILY REPORT AUDIT"
$lines += ""
$lines += "Status: $auditStatus"
$lines += "Telegram mode: $sendMode"
$lines += "Planner global action: $globalAction"
$lines += "Production message has official pick text: $hasOfficialPick"
$lines += "Production message blocked/no-pick: $blockedMessage"
$lines += ""
$lines += "RULES"
$lines += "- Moneyline can send only through production pre-game scan gates."
$lines += "- 2:30 AM is daily report/settlement only."
$lines += "- No picks after game start."
$lines += "- Dry-run remains recommended until 1-2 clean slates."
$lines += ""
$lines += "WARNINGS"
if ($warnings.Count -eq 0) { $lines += "- none" } else { foreach ($w in $warnings) { $lines += "- $w" } }

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    status=$auditStatus
    telegramMode=$sendMode
    plannerGlobalAction=$globalAction
    productionMessageHasOfficialPickText=$hasOfficialPick
    productionMessageBlockedNoPick=$blockedMessage
    warnings=@($warnings)
    moneylineAt230am=$false
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
