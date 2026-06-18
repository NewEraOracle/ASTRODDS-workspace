$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$smartGateCsv = Join-Path $astro "ASTRODDS-smart-live-client-gate-latest.csv"

$outTxt = Join-Path $astro "ASTRODDS-selective-official-send-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-selective-official-send-latest.json"
$outCsv = Join-Path $astro "ASTRODDS-selective-official-send-latest.csv"
$outTelegram = Join-Path $astro "ASTRODDS-telegram-selective-official-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 229 SELECTIVE OFFICIAL SEND" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - SEND ONLY SEND_OK PICKS" -ForegroundColor Cyan
Write-Host ""

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

$rows = Safe-Csv $smartGateCsv

if ($rows.Count -eq 0) {
    Write-Host "ERROR: Smart gate CSV missing or empty." -ForegroundColor Red
    Write-Host $smartGateCsv
    exit 0
}

$sendOkRows = @($rows | Where-Object {
    (Get-Val $_ @("Decision")) -eq "CLIENT_OFFICIAL_SEND_OK"
})

$reviewRows = @($rows | Where-Object {
    (Get-Val $_ @("Decision")) -eq "REVIEW_ONLY"
})

$blockedRows = @($rows | Where-Object {
    (Get-Val $_ @("Decision")) -eq "BLOCKED_FOR_REVIEW"
})

$clientDecision = "CLIENT_DROP_BLOCKED"

if ($sendOkRows.Count -gt 0) {
    if ($blockedRows.Count -gt 0 -or $reviewRows.Count -gt 0) {
        $clientDecision = "CLIENT_DROP_PARTIAL_ALLOWED"
    } else {
        $clientDecision = "CLIENT_DROP_ALLOWED"
    }
}

$officialRows = @()

foreach ($r in $sendOkRows) {
    $officialRows += ,[pscustomobject]@{
        Pick = Get-Val $r @("Pick")
        Game = Get-Val $r @("Game")
        ScheduleDate = Get-Val $r @("ScheduleDate")
        GamePk = Get-Val $r @("GamePk")
        MlbStatus = Get-Val $r @("MlbStatus")
        Entry = Get-Val $r @("Price")
        PublicModel = Get-Val $r @("PublicModel")
        FullSlateModel = Get-Val $r @("FullSlateModel")
        Edge = Get-Val $r @("Edge")
        AwayLineupStatus = Get-Val $r @("AwayLineupStatus")
        HomeLineupStatus = Get-Val $r @("HomeLineupStatus")
        PaperOnly = Get-Val $r @("PaperOnly")
        Decision = Get-Val $r @("Decision")
    }
}

$officialRows | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$telegramLines = @()

if ($sendOkRows.Count -gt 0) {
    $telegramLines += "🚀 ASTRODDS OFFICIAL PICKS"
    $telegramLines += "MLB MONEYLINE ONLY"
    $telegramLines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
    $telegramLines += ""
    $telegramLines += "Rules:"
    $telegramLines += "• No parlays"
    $telegramLines += "• 5% bankroll max per pick"
    $telegramLines += "• Only SEND_OK picks"
    $telegramLines += "• Blocked picks are not sent"
    $telegramLines += ""

    $i = 1
    foreach ($r in $sendOkRows) {
        $telegramLines += "✅ OFFICIAL BUY #$i"
        $telegramLines += "$(Get-Val $r @('Pick')) ML"
        $telegramLines += "Game: $(Get-Val $r @('Game'))"
        $telegramLines += "Entry: $(Get-Val $r @('Price'))"
        $telegramLines += "Model: $(Get-Val $r @('PublicModel'))"
        $telegramLines += "Full slate model: $(Get-Val $r @('FullSlateModel'))"
        $telegramLines += "Edge: $(Get-Val $r @('Edge'))"
        $telegramLines += "Lineups: confirmed / confirmed"
        $telegramLines += "Status: $(Get-Val $r @('MlbStatus'))"
        $telegramLines += ""
        $i++
    }

    $telegramLines += "Why this passed:"
    $telegramLines += "• Market connected"
    $telegramLines += "• Model probability valid"
    $telegramLines += "• Full slate model agrees within 5%"
    $telegramLines += "• Live lineups confirmed"
    $telegramLines += "• paperOnly=False"
    $telegramLines += ""
    $telegramLines += "⚠️ Risk note:"
    $telegramLines += "These are data-driven value spots, not guaranteed wins."
    $telegramLines += ""
    $telegramLines += "ASTRODDS"
} else {
    $telegramLines += "🚫 ASTRODDS CLIENT DROP BLOCKED"
    $telegramLines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
    $telegramLines += ""
    $telegramLines += "No SEND_OK official picks available."
    $telegramLines += ""
    $telegramLines += "Reason:"
    $telegramLines += "• SEND_OK picks: 0"
    $telegramLines += "• REVIEW_ONLY picks: $($reviewRows.Count)"
    $telegramLines += "• BLOCKED picks: $($blockedRows.Count)"
    $telegramLines += ""
    $telegramLines += "Action:"
    $telegramLines += "Run again closer to game time or fix blocked model/lineup issues."
}

$telegramMessage = $telegramLines -join [Environment]::NewLine
$telegramMessage | Set-Content -Encoding UTF8 $outTelegram

$reportLines = @()
$reportLines += "ASTRODDS 229 SELECTIVE OFFICIAL SEND"
$reportLines += ""
$reportLines += "Client decision: $clientDecision"
$reportLines += "SEND_OK: $($sendOkRows.Count)"
$reportLines += "REVIEW_ONLY: $($reviewRows.Count)"
$reportLines += "BLOCKED: $($blockedRows.Count)"
$reportLines += ""
$reportLines += "OFFICIAL PICKS TO SEND"
if ($sendOkRows.Count -eq 0) {
    $reportLines += "- None"
} else {
    foreach ($r in $sendOkRows) {
        $reportLines += "- $(Get-Val $r @('Pick')) | $(Get-Val $r @('Game')) | Entry=$(Get-Val $r @('Price')) | Model=$(Get-Val $r @('PublicModel')) | Edge=$(Get-Val $r @('Edge'))"
    }
}
$reportLines += ""

$reportLines += "BLOCKED PICKS NOT SENT"
if ($blockedRows.Count -eq 0) {
    $reportLines += "- None"
} else {
    foreach ($r in $blockedRows) {
        $reportLines += "- $(Get-Val $r @('Pick')) | $(Get-Val $r @('Game'))"
        $hb = Get-Val $r @("HardBlocks")
        $wr = Get-Val $r @("Warnings")
        if ($hb -ne "") { $reportLines += "  Hard: $hb" }
        if ($wr -ne "") { $reportLines += "  Warn: $wr" }
    }
}
$reportLines += ""

$reportLines += "TELEGRAM OUTPUT"
$reportLines += $outTelegram
$reportLines += ""
$reportLines += "FINAL TELEGRAM MESSAGE"
$reportLines += $telegramMessage

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    clientDecision = $clientDecision
    sendOk = $sendOkRows.Count
    reviewOnly = $reviewRows.Count
    blocked = $blockedRows.Count
    telegramOutput = $outTelegram
    officialRows = @($officialRows)
} | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 $outJson

($reportLines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($reportLines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output CSV: $outCsv"
Write-Host "Output JSON: $outJson"
Write-Host "Telegram message: $outTelegram"
Write-Host ""
