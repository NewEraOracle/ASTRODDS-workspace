$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$smartGateCsv = Join-Path $astro "ASTRODDS-smart-live-client-gate-latest.csv"
$telegramFile = Join-Path $astro "ASTRODDS-telegram-selective-official-latest.txt"

$ledgerCsv = Join-Path $astro "ASTRODDS-official-picks-ledger-latest.csv"
$ledgerJson = Join-Path $astro "ASTRODDS-official-picks-ledger-latest.json"
$outTxt = Join-Path $astro "ASTRODDS-official-picks-ledger-update-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 231 LOG OFFICIAL PICKS TO LEDGER" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - TRACK RESULTS" -ForegroundColor Cyan
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

function Make-Key($r) {
    $gamePk = Get-Val $r @("GamePk")
    $pick = Get-Val $r @("Pick")
    $game = Get-Val $r @("Game")
    $entry = Get-Val $r @("Price")
    $date = Get-Val $r @("ScheduleDate")

    return "$date|$gamePk|$game|$pick|$entry".ToLower()
}

$gateRows = Safe-Csv $smartGateCsv

$sendOkRows = @($gateRows | Where-Object {
    (Get-Val $_ @("Decision")) -eq "CLIENT_OFFICIAL_SEND_OK"
})

$existingLedger = Safe-Csv $ledgerCsv

$seen = @{}
foreach ($old in $existingLedger) {
    $key = Get-Val $old @("LedgerKey")
    if ($key -ne "") {
        $seen[$key] = $true
    }
}

$newRows = @()

foreach ($r in $sendOkRows) {
    $key = Make-Key $r

    if ($seen.ContainsKey($key)) {
        continue
    }

    $newRows += ,[pscustomobject]@{
        LedgerKey = $key
        LoggedAt = (Get-Date).ToString("o")
        Status = "PENDING_RESULT"
        Sport = "MLB"
        MarketType = "MONEYLINE"
        Pick = Get-Val $r @("Pick")
        Game = Get-Val $r @("Game")
        ScheduleDate = Get-Val $r @("ScheduleDate")
        GamePk = Get-Val $r @("GamePk")
        MlbStatusAtLog = Get-Val $r @("MlbStatus")
        EntryPrice = Get-Val $r @("Price")
        PublicModel = Get-Val $r @("PublicModel")
        FullSlateModel = Get-Val $r @("FullSlateModel")
        Edge = Get-Val $r @("Edge")
        Stake = "5% bankroll max"
        AwayLineupStatus = Get-Val $r @("AwayLineupStatus")
        HomeLineupStatus = Get-Val $r @("HomeLineupStatus")
        PaperOnly = Get-Val $r @("PaperOnly")
        Result = ""
        Winner = ""
        FinalScore = ""
        ClosingPrice = ""
        CLV = ""
        ROI = ""
        BrierComponent = ""
        LogLossComponent = ""
        SourceGate = "ASTRODDS-smart-live-client-gate-latest.csv"
        TelegramFile = $telegramFile
    }

    $seen[$key] = $true
}

$combined = @()
$combined += @($existingLedger)
$combined += @($newRows)

$combined | Export-Csv -NoTypeInformation -Encoding UTF8 $ledgerCsv
$combined | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 $ledgerJson

$lines = @()
$lines += "ASTRODDS 231 OFFICIAL PICKS LEDGER UPDATE"
$lines += ""
$lines += "SEND_OK rows found: $($sendOkRows.Count)"
$lines += "New picks logged: $($newRows.Count)"
$lines += "Total ledger rows: $($combined.Count)"
$lines += ""

$lines += "NEW LOGGED PICKS"
if ($newRows.Count -eq 0) {
    $lines += "- None. Pick may already be logged."
} else {
    foreach ($n in $newRows) {
        $lines += "- $($n.Pick) | $($n.Game) | Entry=$($n.EntryPrice) | Model=$($n.PublicModel) | Edge=$($n.Edge) | Status=$($n.Status)"
    }
}

$lines += ""
$lines += "LEDGER FILES"
$lines += "CSV: $ledgerCsv"
$lines += "JSON: $ledgerJson"
$lines += ""
$lines += "NEXT STEP"
$lines += "After the game is final, run a settle script to mark WIN/LOSS, ROI, CLV, Brier, and log loss."

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Ledger CSV: $ledgerCsv"
Write-Host "Ledger JSON: $ledgerJson"
Write-Host ""
