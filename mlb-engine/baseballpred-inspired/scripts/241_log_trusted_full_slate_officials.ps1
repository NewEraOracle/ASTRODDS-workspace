$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$gateCsv = Join-Path $astro "ASTRODDS-final-trusted-full-slate-gate-latest.csv"
$telegramFile = Join-Path $astro "ASTRODDS-telegram-final-trusted-full-slate-latest.txt"

$ledgerCsv = Join-Path $astro "ASTRODDS-official-picks-ledger-latest.csv"
$ledgerJson = Join-Path $astro "ASTRODDS-official-picks-ledger-latest.json"
$outTxt = Join-Path $astro "ASTRODDS-trusted-full-slate-ledger-update-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 241 LOG TRUSTED FULL SLATE OFFICIALS" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - LOG 240 OFFICIAL PICKS" -ForegroundColor Cyan
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
    $date = Get-Date -Format "yyyy-MM-dd"
    $game = Get-Val $r @("Game")
    $pick = Get-Val $r @("Pick")
    $entry = Get-Val $r @("Price")
    return "$date|$game|$pick|$entry".ToLower()
}

$gateRows = Safe-Csv $gateCsv
$officialRows = @($gateRows | Where-Object {
    (Get-Val $_ @("FinalDecision")) -eq "CLIENT_OFFICIAL_SEND_OK"
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

foreach ($r in $officialRows) {
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
        MlbStatusAtLog = Get-Val $r @("MlbStatus")
        EntryPrice = Get-Val $r @("Price")
        ModelProbability = Get-Val $r @("ModelProbability")
        MarketProbability = Get-Val $r @("MarketProbability")
        Edge = Get-Val $r @("Edge")
        Stake = "5% bankroll max"
        AwayLineupStatus = Get-Val $r @("AwayLineupStatus")
        HomeLineupStatus = Get-Val $r @("HomeLineupStatus")
        Result = ""
        Winner = ""
        FinalScore = ""
        ClosingPrice = ""
        CLV = ""
        ROI = ""
        BrierComponent = ""
        LogLossComponent = ""
        SourceGate = "ASTRODDS-final-trusted-full-slate-gate-latest.csv"
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
$lines += "ASTRODDS 241 TRUSTED FULL SLATE LEDGER UPDATE"
$lines += ""
$lines += "Official rows from 240: $($officialRows.Count)"
$lines += "New rows logged: $($newRows.Count)"
$lines += "Total ledger rows: $($combined.Count)"
$lines += ""

$lines += "OFFICIAL PICKS LOGGED"
if ($newRows.Count -eq 0) {
    $lines += "- None new. They may already be logged."
} else {
    foreach ($n in $newRows) {
        $lines += "- $($n.Pick) | $($n.Game) | Entry=$($n.EntryPrice) | Model=$($n.ModelProbability) | Edge=$($n.Edge)"
    }
}

$lines += ""
$lines += "TELEGRAM FILE"
$lines += $telegramFile
$lines += ""
$lines += "LEDGER CSV"
$lines += $ledgerCsv

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Ledger CSV: $ledgerCsv"
Write-Host "Ledger JSON: $ledgerJson"
Write-Host ""
