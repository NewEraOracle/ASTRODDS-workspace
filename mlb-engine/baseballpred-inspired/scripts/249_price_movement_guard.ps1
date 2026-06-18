$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$contextCsv = Join-Path $astro "ASTRODDS-248-context-merged-confidence-latest.csv"
$ledgerCsv = Join-Path $astro "ASTRODDS-official-picks-ledger-latest.csv"

$outCsv = Join-Path $astro "ASTRODDS-249-price-guard-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-249-price-guard-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-249-price-guard-latest.json"
$outTelegram = Join-Path $astro "ASTRODDS-telegram-price-guarded-final-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 249 PRICE MOVEMENT GUARD" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - BLOCK PICKS IF ENTRY PRICE MOVED TOO MUCH" -ForegroundColor Cyan
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

function Num-Cents($v) {
    if ($null -eq $v) { return $null }
    $s = "$v".Trim()
    if ($s -eq "") { return $null }
    $s = $s.Replace("¢","").Replace("%","").Replace(",", ".")
    $n = 0.0
    $culture = [System.Globalization.CultureInfo]::InvariantCulture
    if ([double]::TryParse($s, [System.Globalization.NumberStyles]::Any, $culture, [ref]$n)) {
        if ($n -le 1) { $n = $n * 100.0 }
        return $n
    }
    return $null
}

function Find-Ledger($rows, $game, $pick) {
    $target = Clean-KeyPart "$game|$pick"
    foreach ($r in $rows) {
        $g = Get-Val $r @("Game")
        $p = Get-Val $r @("Pick")
        if ((Clean-KeyPart "$g|$p") -eq $target) { return $r }
    }
    return $null
}

$rows = Safe-Csv $contextCsv
$ledger = Safe-Csv $ledgerCsv

if ($rows.Count -eq 0) {
    Write-Host "ERROR: Missing 248 context-merged confidence CSV. Run 248 first." -ForegroundColor Red
    Write-Host $contextCsv
    exit 0
}

$outRows = @()

foreach ($r in $rows) {
    $game = Get-Val $r @("Game")
    $pick = Get-Val $r @("Pick")
    $grade = Get-Val $r @("Grade")
    $currentEntryText = Get-Val $r @("Entry")
    $confidence = Get-Val $r @("Confidence")
    $stake = Get-Val $r @("Stake")
    $status = Get-Val $r @("Status")

    $ledgerRow = Find-Ledger $ledger $game $pick
    $originalEntryText = ""
    if ($null -ne $ledgerRow) { $originalEntryText = Get-Val $ledgerRow @("EntryPrice") }
    if ($originalEntryText -eq "") { $originalEntryText = $currentEntryText }

    $current = Num-Cents $currentEntryText
    $original = Num-Cents $originalEntryText

    $maxMove = 3.0
    if ($grade -eq "STRONG BUY") { $maxMove = 4.0 }
    if ($grade -eq "VALUE BUY") { $maxMove = 3.0 }

    $decision = "SEND_OK"
    $reason = "Price within allowed movement."

    if ($null -eq $current -or $null -eq $original) {
        $decision = "BLOCKED_PRICE_UNKNOWN"
        $reason = "Could not parse current or original entry price."
    } else {
        $move = $current - $original

        if ($move -gt $maxMove) {
            $decision = "BLOCKED_PRICE_MOVED"
            $reason = "Current price moved +$([math]::Round($move,1))¢ above original entry. Max allowed for $grade is +$maxMove¢."
        } elseif ($move -lt -10) {
            $decision = "REVIEW_PRICE_DROPPED"
            $reason = "Price dropped sharply. Could be value or injury/news risk; manual review."
        }
    }

    $outRows += ,[pscustomobject]@{
        Decision = $decision
        Grade = $grade
        Pick = $pick
        Game = $game
        OriginalEntry = $originalEntryText
        CurrentEntry = $currentEntryText
        PriceMoveCents = if ($null -ne $current -and $null -ne $original) { [math]::Round(($current - $original), 1) } else { "" }
        MaxAllowedMoveCents = $maxMove
        Confidence = $confidence
        Stake = $stake
        Status = $status
        Reason = $reason
    }
}

$sendRows = @($outRows | Where-Object { $_.Decision -eq "SEND_OK" })
$blockedRows = @($outRows | Where-Object { $_.Decision -ne "SEND_OK" })

$outRows | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$telegram = @()

if ($sendRows.Count -gt 0) {
    $telegram += "🚀 ASTRODDS OFFICIAL PICKS"
    $telegram += "MLB MONEYLINE ONLY"
    $telegram += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
    $telegram += ""
    $telegram += "Rules:"
    $telegram += "• No parlays"
    $telegram += "• Confidence is ASTRODDS score /100"
    $telegram += "• Context checked: lineups, model, market, weather, injuries, pitcher, bullpen"
    $telegram += "• Price movement guard passed"
    $telegram += "• 5% bankroll max per pick"
    $telegram += ""

    $i = 1
    foreach ($r in $sendRows) {
        $telegram += "✅ $($r.Grade) #$i"
        $telegram += "$($r.Pick) ML"
        $telegram += "Game: $($r.Game)"
        $telegram += "Entry: $($r.CurrentEntry)"
        $telegram += "Confidence: $($r.Confidence)/100"
        $telegram += "Stake: $($r.Stake)"
        $telegram += "Status: $($r.Status)"
        $telegram += ""
        $i++
    }

    $telegram += "⚠️ Risk note:"
    $telegram += "Confidence is not a guaranteed win rate. It is a simplified score based on ASTRODDS internal model, market value, live lineups, context and safety gates."
    $telegram += ""
    $telegram += "ASTRODDS"
} else {
    $telegram += "🚫 ASTRODDS CLIENT DROP BLOCKED"
    $telegram += "No official picks passed the price movement guard."
}

($telegram -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTelegram

$lines = @()
$lines += "ASTRODDS 249 PRICE MOVEMENT GUARD"
$lines += ""
$lines += "Total official picks checked: $($outRows.Count)"
$lines += "SEND_OK after price guard: $($sendRows.Count)"
$lines += "Blocked/review after price guard: $($blockedRows.Count)"
$lines += ""

$lines += "PRICE GUARD RESULTS"
foreach ($r in $outRows) {
    $lines += "- $($r.Decision) | $($r.Pick) | $($r.Game)"
    $lines += "  Original=$($r.OriginalEntry) | Current=$($r.CurrentEntry) | Move=$($r.PriceMoveCents)¢ | Max=$($r.MaxAllowedMoveCents)¢ | Confidence=$($r.Confidence)/100"
    $lines += "  Reason=$($r.Reason)"
}
$lines += ""

$lines += "TELEGRAM"
$lines += $outTelegram

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    totalChecked = $outRows.Count
    sendOk = $sendRows.Count
    blockedOrReview = $blockedRows.Count
    telegram = $outTelegram
    rows = @($outRows)
} | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output CSV: $outCsv"
Write-Host "Output JSON: $outJson"
Write-Host "Telegram: $outTelegram"
Write-Host ""
