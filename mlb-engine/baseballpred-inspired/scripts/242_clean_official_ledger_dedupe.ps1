$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$ledgerCsv = Join-Path $astro "ASTRODDS-official-picks-ledger-latest.csv"
$ledgerJson = Join-Path $astro "ASTRODDS-official-picks-ledger-latest.json"
$gate240 = Join-Path $astro "ASTRODDS-final-trusted-full-slate-gate-latest.csv"
$telegram240 = Join-Path $astro "ASTRODDS-telegram-final-trusted-full-slate-latest.txt"

$backupCsv = Join-Path $astro ("ASTRODDS-official-picks-ledger-backup-before-dedupe-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".csv")
$outTxt = Join-Path $astro "ASTRODDS-official-ledger-dedupe-clean-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 242 CLEAN OFFICIAL LEDGER DEDUPE" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - REMOVE DUPLICATE MIAMI / NORMALIZE FIELDS" -ForegroundColor Cyan
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

function Clean-KeyPart($s) {
    $x = "$s".ToLower().Trim()
    $x = $x -replace "\s+", " "
    return $x
}

function Date-From-Row($r) {
    $d = Get-Val $r @("ScheduleDate","Date")
    if ($d -ne "") { return $d }

    $key = Get-Val $r @("LedgerKey")
    if ($key -match "^\d{4}-\d{2}-\d{2}") { return $matches[0] }

    $logged = Get-Val $r @("LoggedAt")
    if ($logged -match "^\d{4}-\d{2}-\d{2}") { return $matches[0] }

    return (Get-Date -Format "yyyy-MM-dd")
}

function Make-DedupKey($r) {
    $date = Date-From-Row $r
    $game = Get-Val $r @("Game")
    $pick = Get-Val $r @("Pick")
    return (Clean-KeyPart "$date|$game|$pick")
}

function Normalize-LedgerRow($r, $sourceLabel) {
    $date = Date-From-Row $r
    $game = Get-Val $r @("Game")
    $pick = Get-Val $r @("Pick")
    $entry = Get-Val $r @("EntryPrice","Price")

    return [pscustomobject]@{
        DedupKey = Clean-KeyPart "$date|$game|$pick"
        LedgerKey = Clean-KeyPart "$date|$game|$pick|$entry"
        LoggedAt = Get-Val $r @("LoggedAt")
        Status = Get-Val $r @("Status")
        Sport = Get-Val $r @("Sport")
        MarketType = Get-Val $r @("MarketType")
        Pick = $pick
        Game = $game
        ScheduleDate = $date
        GamePk = Get-Val $r @("GamePk")
        MlbStatusAtLog = Get-Val $r @("MlbStatusAtLog","MlbStatus")
        EntryPrice = $entry
        ModelProbability = Get-Val $r @("ModelProbability","PublicModel")
        FullSlateModel = Get-Val $r @("FullSlateModel")
        MarketProbability = Get-Val $r @("MarketProbability")
        Edge = Get-Val $r @("Edge")
        Stake = Get-Val $r @("Stake")
        AwayLineupStatus = Get-Val $r @("AwayLineupStatus")
        HomeLineupStatus = Get-Val $r @("HomeLineupStatus")
        PaperOnly = Get-Val $r @("PaperOnly")
        Result = Get-Val $r @("Result")
        Winner = Get-Val $r @("Winner")
        FinalScore = Get-Val $r @("FinalScore")
        ClosingPrice = Get-Val $r @("ClosingPrice")
        CLV = Get-Val $r @("CLV")
        ROI = Get-Val $r @("ROI")
        BrierComponent = Get-Val $r @("BrierComponent")
        LogLossComponent = Get-Val $r @("LogLossComponent")
        SourceGate = Get-Val $r @("SourceGate")
        TelegramFile = Get-Val $r @("TelegramFile")
        NormalizeSource = $sourceLabel
    }
}

function Normalize-Gate240Row($r) {
    $date = Get-Date -Format "yyyy-MM-dd"
    $game = Get-Val $r @("Game")
    $pick = Get-Val $r @("Pick")
    $entry = Get-Val $r @("Price")

    return [pscustomobject]@{
        DedupKey = Clean-KeyPart "$date|$game|$pick"
        LedgerKey = Clean-KeyPart "$date|$game|$pick|$entry"
        LoggedAt = (Get-Date).ToString("o")
        Status = "PENDING_RESULT"
        Sport = "MLB"
        MarketType = "MONEYLINE"
        Pick = $pick
        Game = $game
        ScheduleDate = $date
        GamePk = ""
        MlbStatusAtLog = Get-Val $r @("MlbStatus")
        EntryPrice = $entry
        ModelProbability = Get-Val $r @("ModelProbability")
        FullSlateModel = ""
        MarketProbability = Get-Val $r @("MarketProbability")
        Edge = Get-Val $r @("Edge")
        Stake = "5% bankroll max"
        AwayLineupStatus = Get-Val $r @("AwayLineupStatus")
        HomeLineupStatus = Get-Val $r @("HomeLineupStatus")
        PaperOnly = ""
        Result = ""
        Winner = ""
        FinalScore = ""
        ClosingPrice = ""
        CLV = ""
        ROI = ""
        BrierComponent = ""
        LogLossComponent = ""
        SourceGate = "ASTRODDS-final-trusted-full-slate-gate-latest.csv"
        TelegramFile = $telegram240
        NormalizeSource = "gate240"
    }
}

function First-NonEmpty($rows, $field) {
    foreach ($r in $rows) {
        $v = Get-Val $r @($field)
        if ($v -ne "") { return $v }
    }
    return ""
}

if (Test-Path $ledgerCsv) {
    Copy-Item $ledgerCsv $backupCsv -Force
}

$oldRows = Safe-Csv $ledgerCsv
$gateRows = Safe-Csv $gate240

$all = @()

foreach ($r in $oldRows) {
    $all += ,(Normalize-LedgerRow $r "existing")
}

foreach ($r in ($gateRows | Where-Object { (Get-Val $_ @("FinalDecision")) -eq "CLIENT_OFFICIAL_SEND_OK" })) {
    $all += ,(Normalize-Gate240Row $r)
}

$groups = $all | Group-Object DedupKey

$clean = @()

foreach ($g in $groups) {
    $rows = @($g.Group)

    # Prefer gate240 values first, then existing values.
    $preferred = @()
    $preferred += @($rows | Where-Object { $_.NormalizeSource -eq "gate240" })
    $preferred += @($rows | Where-Object { $_.NormalizeSource -ne "gate240" })

    $date = First-NonEmpty $preferred "ScheduleDate"
    $game = First-NonEmpty $preferred "Game"
    $pick = First-NonEmpty $preferred "Pick"
    $entry = First-NonEmpty $preferred "EntryPrice"

    $clean += ,[pscustomobject]@{
        LedgerKey = Clean-KeyPart "$date|$game|$pick|$entry"
        LoggedAt = First-NonEmpty $preferred "LoggedAt"
        Status = if ((First-NonEmpty $preferred "Status") -ne "") { First-NonEmpty $preferred "Status" } else { "PENDING_RESULT" }
        Sport = if ((First-NonEmpty $preferred "Sport") -ne "") { First-NonEmpty $preferred "Sport" } else { "MLB" }
        MarketType = if ((First-NonEmpty $preferred "MarketType") -ne "") { First-NonEmpty $preferred "MarketType" } else { "MONEYLINE" }
        Pick = $pick
        Game = $game
        ScheduleDate = $date
        GamePk = First-NonEmpty $preferred "GamePk"
        MlbStatusAtLog = First-NonEmpty $preferred "MlbStatusAtLog"
        EntryPrice = $entry
        ModelProbability = First-NonEmpty $preferred "ModelProbability"
        FullSlateModel = First-NonEmpty $preferred "FullSlateModel"
        MarketProbability = First-NonEmpty $preferred "MarketProbability"
        Edge = First-NonEmpty $preferred "Edge"
        Stake = if ((First-NonEmpty $preferred "Stake") -ne "") { First-NonEmpty $preferred "Stake" } else { "5% bankroll max" }
        AwayLineupStatus = First-NonEmpty $preferred "AwayLineupStatus"
        HomeLineupStatus = First-NonEmpty $preferred "HomeLineupStatus"
        PaperOnly = First-NonEmpty $preferred "PaperOnly"
        Result = First-NonEmpty $preferred "Result"
        Winner = First-NonEmpty $preferred "Winner"
        FinalScore = First-NonEmpty $preferred "FinalScore"
        ClosingPrice = First-NonEmpty $preferred "ClosingPrice"
        CLV = First-NonEmpty $preferred "CLV"
        ROI = First-NonEmpty $preferred "ROI"
        BrierComponent = First-NonEmpty $preferred "BrierComponent"
        LogLossComponent = First-NonEmpty $preferred "LogLossComponent"
        SourceGate = First-NonEmpty $preferred "SourceGate"
        TelegramFile = First-NonEmpty $preferred "TelegramFile"
    }
}

$clean = @($clean | Sort-Object ScheduleDate, Game, Pick)

$clean | Export-Csv -NoTypeInformation -Encoding UTF8 $ledgerCsv
$clean | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 $ledgerJson

$lines = @()
$lines += "ASTRODDS 242 CLEAN OFFICIAL LEDGER DEDUPE"
$lines += ""
$lines += "Old rows: $($oldRows.Count)"
$lines += "Gate 240 official rows: $(($gateRows | Where-Object { (Get-Val $_ @('FinalDecision')) -eq 'CLIENT_OFFICIAL_SEND_OK' }).Count)"
$lines += "Clean rows: $($clean.Count)"
$lines += "Backup created: $backupCsv"
$lines += ""

$lines += "CLEAN LEDGER"
foreach ($r in $clean) {
    $lines += "- $($r.Pick) | $($r.Game) | Entry=$($r.EntryPrice) | Model=$($r.ModelProbability) | Edge=$($r.Edge) | Status=$($r.Status)"
}

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
