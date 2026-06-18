$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
$scripts = Join-Path $root "mlb-engine\baseballpred-inspired\scripts"

$outTxt = Join-Path $astro "ASTRODDS-smart-official-daily-run-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-smart-official-daily-run-latest.json"
$outChildLog = Join-Path $astro "ASTRODDS-smart-official-daily-child-log-latest.txt"

$smartGateScript = Join-Path $scripts "228_smart_live_lineup_gate_active_date.ps1"
$selectiveScript = Join-Path $scripts "229_selective_official_send_from_smart_gate.ps1"

$finalTelegram = Join-Path $astro "ASTRODDS-telegram-selective-official-latest.txt"
$selectiveJson = Join-Path $astro "ASTRODDS-selective-official-send-latest.json"
$smartGateCsv = Join-Path $astro "ASTRODDS-smart-live-client-gate-latest.csv"

Write-Host ""
Write-Host "ASTRODDS 230 SMART OFFICIAL DAILY RUNNER" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - LIVE LINEUPS + SELECTIVE SEND" -ForegroundColor Cyan
Write-Host ""

$childLog = @()

function Run-StepClean($name, $path) {
    $started = Get-Date

    Write-Host "Running $name..." -ForegroundColor Cyan

    if (!(Test-Path $path)) {
        Write-Host "MISSING: $path" -ForegroundColor Yellow

        return [pscustomobject]@{
            Name = $name
            Status = "MISSING"
            ExitCode = ""
            DurationSec = 0
        }
    }

    try {
        $output = & powershell -ExecutionPolicy Bypass -File $path 2>&1
        $exitCode = $LASTEXITCODE

        $script:childLog += ""
        $script:childLog += "============================================================"
        $script:childLog += "STEP: $name"
        $script:childLog += "PATH: $path"
        $script:childLog += "EXIT: $exitCode"
        $script:childLog += "============================================================"
        $script:childLog += @($output | ForEach-Object { "$_" })

        $ended = Get-Date
        $duration = [math]::Round(($ended - $started).TotalSeconds, 2)

        if ($exitCode -eq 0 -or $null -eq $exitCode) {
            Write-Host "OK: $name ($duration sec)" -ForegroundColor Green
            return [pscustomobject]@{
                Name = $name
                Status = "OK"
                ExitCode = "0"
                DurationSec = $duration
            }
        } else {
            Write-Host "ERROR: $name exit $exitCode" -ForegroundColor Red
            return [pscustomobject]@{
                Name = $name
                Status = "ERROR"
                ExitCode = "$exitCode"
                DurationSec = $duration
            }
        }
    } catch {
        $ended = Get-Date
        $duration = [math]::Round(($ended - $started).TotalSeconds, 2)

        $script:childLog += ""
        $script:childLog += "ERROR STEP: $name"
        $script:childLog += "$($_.Exception.Message)"

        Write-Host "ERROR: $name" -ForegroundColor Red
        Write-Host $_.Exception.Message

        return [pscustomobject]@{
            Name = $name
            Status = "ERROR"
            ExitCode = "1"
            DurationSec = $duration
        }
    }
}

function Read-JsonSafe($path) {
    if (!(Test-Path $path)) { return $null }
    try { return Get-Content $path -Raw | ConvertFrom-Json }
    catch { return $null }
}

function Safe-Csv($path) {
    if (!(Test-Path $path)) { return @() }
    try { return @(Import-Csv $path) }
    catch { return @() }
}

function Get-Val($row, $names) {
    if ($null -eq $row) { return "" }

    foreach ($n in @($names)) {
        $p = $row.PSObject.Properties[$n]
        if ($null -ne $p -and $null -ne $p.Value -and "$($p.Value)".Trim() -ne "") {
            return "$($p.Value)".Trim()
        }
    }

    return ""
}

$steps = @()
$steps += ,(Run-StepClean "228 smart live lineup gate" $smartGateScript)
$steps += ,(Run-StepClean "229 selective official sender" $selectiveScript)

$childLog | Set-Content -Encoding UTF8 $outChildLog

$selective = Read-JsonSafe $selectiveJson
$gateRows = Safe-Csv $smartGateCsv

$sendOk = 0
$review = 0
$blocked = 0
$clientDecision = "UNKNOWN"

if ($null -ne $selective) {
    $sendOk = [int]$selective.sendOk
    $review = [int]$selective.reviewOnly
    $blocked = [int]$selective.blocked
    $clientDecision = "$($selective.clientDecision)"
}

$officialRows = @($gateRows | Where-Object {
    (Get-Val $_ @("Decision")) -eq "CLIENT_OFFICIAL_SEND_OK"
})

$blockedRows = @($gateRows | Where-Object {
    (Get-Val $_ @("Decision")) -eq "BLOCKED_FOR_REVIEW"
})

$telegramText = ""
if (Test-Path $finalTelegram) {
    $telegramText = Get-Content $finalTelegram -Raw
}

$lines = @()
$lines += "ASTRODDS 230 SMART OFFICIAL DAILY RUNNER"
$lines += ""
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$lines += "Client decision: $clientDecision"
$lines += "SEND_OK: $sendOk"
$lines += "REVIEW_ONLY: $review"
$lines += "BLOCKED: $blocked"
$lines += ""

$lines += "STEPS"
foreach ($s in $steps) {
    $lines += "- $($s.Name): $($s.Status) | Exit=$($s.ExitCode) | Duration=$($s.DurationSec)s"
}
$lines += ""

$lines += "OFFICIAL PICKS READY TO SEND"
if ($officialRows.Count -eq 0) {
    $lines += "- None"
} else {
    foreach ($r in $officialRows) {
        $lines += "- $(Get-Val $r @('Pick')) | $(Get-Val $r @('Game')) | Entry=$(Get-Val $r @('Price')) | Model=$(Get-Val $r @('PublicModel')) | Edge=$(Get-Val $r @('Edge')) | Lineups=$(Get-Val $r @('AwayLineupStatus'))/$(Get-Val $r @('HomeLineupStatus'))"
    }
}
$lines += ""

$lines += "BLOCKED PICKS"
if ($blockedRows.Count -eq 0) {
    $lines += "- None"
} else {
    foreach ($r in $blockedRows) {
        $lines += "- $(Get-Val $r @('Pick')) | $(Get-Val $r @('Game'))"
        $hb = Get-Val $r @("HardBlocks")
        $wr = Get-Val $r @("Warnings")
        if ($hb -ne "") { $lines += "  Hard: $hb" }
        if ($wr -ne "") { $lines += "  Warn: $wr" }
    }
}
$lines += ""

$lines += "TELEGRAM FILE"
$lines += $finalTelegram
$lines += ""

$lines += "FINAL TELEGRAM MESSAGE"
$lines += $telegramText

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    clientDecision = $clientDecision
    sendOk = $sendOk
    reviewOnly = $review
    blocked = $blocked
    steps = @($steps)
    officialPickCount = $officialRows.Count
    blockedPickCount = $blockedRows.Count
    telegramFile = $finalTelegram
    childLog = $outChildLog
} | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output JSON: $outJson"
Write-Host "Child log: $outChildLog"
Write-Host "Telegram file: $finalTelegram"
Write-Host ""
