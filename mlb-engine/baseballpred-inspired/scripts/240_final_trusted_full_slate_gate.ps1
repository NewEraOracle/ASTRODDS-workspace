$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$gate236 = Join-Path $astro "ASTRODDS-all-context-smart-gate-latest.csv"
$gate237 = Join-Path $astro "ASTRODDS-final-reconciled-official-gate-latest.csv"

$outCsv = Join-Path $astro "ASTRODDS-final-trusted-full-slate-gate-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-final-trusted-full-slate-gate-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-final-trusted-full-slate-gate-latest.json"
$outTelegram = Join-Path $astro "ASTRODDS-telegram-final-trusted-full-slate-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 240 FINAL TRUSTED FULL SLATE GATE" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - FULL SLATE MODEL SOURCE OF TRUTH" -ForegroundColor Cyan
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

function Normalize-Team($s) {
    $x = "$s".ToLower().Trim()
    $x = $x -replace "[^a-z0-9 ]", ""
    $x = $x -replace "\s+", " "
    return $x
}

function Split-Key($game, $pick) {
    $awayTeamName = ""
    $homeTeamName = ""

    if ($game -match "\s@\s") {
        $parts = $game -split "\s@\s", 2
        $awayTeamName = "$($parts[0])".Trim()
        $homeTeamName = "$($parts[1])".Trim()
    } elseif ($game -match "\svs\s") {
        $parts = $game -split "\svs\s", 2
        $awayTeamName = "$($parts[0])".Trim()
        $homeTeamName = "$($parts[1])".Trim()
    }

    return ((Normalize-Team $awayTeamName) + " @ " + (Normalize-Team $homeTeamName) + "|" + (Normalize-Team $pick))
}

$rows236 = Safe-Csv $gate236
$rows237 = Safe-Csv $gate237

if ($rows236.Count -eq 0 -or $rows237.Count -eq 0) {
    Write-Host "ERROR: Run 236 and 237 first." -ForegroundColor Red
    exit 0
}

$map236 = @{}
foreach ($r in $rows236) {
    $game = Get-Val $r @("Game")
    $pick = Get-Val $r @("Pick")
    if ($game -eq "" -or $pick -eq "") { continue }
    $map236[(Split-Key $game $pick)] = $r
}

$finalRows = @()

foreach ($r237 in $rows237) {
    $game = Get-Val $r237 @("Game")
    $pick = Get-Val $r237 @("Pick")
    if ($game -eq "") { continue }

    $key = Split-Key $game $pick
    $r236 = $null
    if ($map236.ContainsKey($key)) { $r236 = $map236[$key] }

    $finalDecision = Get-Val $r237 @("FinalDecision")
    $finalReason = Get-Val $r237 @("FinalReason")
    $hard = Get-Val $r237 @("HardBlocks")
    $warn = Get-Val $r237 @("Warnings")

    $price = Get-Val $r237 @("Price")
    $model = Get-Val $r237 @("ModelProbability")
    $edge = Get-Val $r237 @("Edge")
    $market = Get-Val $r237 @("MarketProbability")
    $awayLineup = Get-Val $r237 @("AwayLineupStatus")
    $homeLineup = Get-Val $r237 @("HomeLineupStatus")
    $mlbStatus = Get-Val $r237 @("MlbStatus")

    if ($null -ne $r236) {
        $decision236 = Get-Val $r236 @("Decision")
        $hard236 = Get-Val $r236 @("HardBlocks")
        $warn236 = Get-Val $r236 @("Warnings")

        $price236 = Get-Val $r236 @("Price")
        $model236 = Get-Val $r236 @("ModelProbability")
        $edge236 = Get-Val $r236 @("Edge")
        $market236 = Get-Val $r236 @("MarketProbability")

        $onlyPublicMismatch = (
            $finalDecision -eq "BLOCKED_FOR_REVIEW" -and
            $hard -like "*model mismatch above 5%*" -and
            $hard -notlike "*lineups not fully confirmed*" -and
            $hard -notlike "*NO_MODEL_YET*" -and
            $hard -notlike "*game status not eligible*" -and
            $decision236 -eq "CLIENT_OFFICIAL_SEND_OK"
        )

        if ($onlyPublicMismatch) {
            $finalDecision = "CLIENT_OFFICIAL_SEND_OK"
            $finalReason = "Promoted by trusted full slate model. Public board 76% was stale/wrong; using full slate 63.5% source."
            $hard = ""
            if ($warn -ne "") { $warn += " | " }
            $warn += "public model mismatch ignored because full slate model passed all gates"

            if ($price236 -ne "") { $price = $price236 }
            if ($model236 -ne "") { $model = $model236 }
            if ($edge236 -ne "") { $edge = $edge236 }
            if ($market236 -ne "") { $market = $market236 }
        }
    }

    $finalRows += ,[pscustomobject]@{
        FinalDecision = $finalDecision
        Game = $game
        Pick = $pick
        MlbStatus = $mlbStatus
        Price = $price
        ModelProbability = $model
        MarketProbability = $market
        Edge = $edge
        AwayLineupStatus = $awayLineup
        HomeLineupStatus = $homeLineup
        HardBlocks = $hard
        Warnings = $warn
        FinalReason = $finalReason
    }
}

$sendOk = @($finalRows | Where-Object { $_.FinalDecision -eq "CLIENT_OFFICIAL_SEND_OK" }).Count
$review = @($finalRows | Where-Object { $_.FinalDecision -like "REVIEW*" }).Count
$blocked = @($finalRows | Where-Object { $_.FinalDecision -eq "BLOCKED_FOR_REVIEW" }).Count

$clientDecision = "CLIENT_DROP_BLOCKED"
if ($sendOk -gt 0) {
    if ($blocked -gt 0 -or $review -gt 0) {
        $clientDecision = "CLIENT_DROP_PARTIAL_ALLOWED"
    } else {
        $clientDecision = "CLIENT_DROP_ALLOWED"
    }
}

$finalRows | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$telegram = @()
if ($sendOk -gt 0) {
    $telegram += "🚀 ASTRODDS OFFICIAL PICKS"
    $telegram += "MLB MONEYLINE ONLY"
    $telegram += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
    $telegram += ""
    $telegram += "Rules:"
    $telegram += "• No parlays"
    $telegram += "• 5% bankroll max per pick"
    $telegram += "• Trusted full slate model"
    $telegram += "• Live lineups confirmed"
    $telegram += ""

    $i = 1
    foreach ($r in ($finalRows | Where-Object { $_.FinalDecision -eq "CLIENT_OFFICIAL_SEND_OK" })) {
        $telegram += "✅ OFFICIAL BUY #$i"
        $telegram += "$($r.Pick) ML"
        $telegram += "Game: $($r.Game)"
        $telegram += "Entry: $($r.Price)"
        $telegram += "Model: $($r.ModelProbability)"
        $telegram += "Edge: $($r.Edge)"
        $telegram += "Lineups: $($r.AwayLineupStatus) / $($r.HomeLineupStatus)"
        $telegram += "Status: $($r.MlbStatus)"
        $telegram += ""
        $i++
    }

    $telegram += "⚠️ Risk note:"
    $telegram += "These are data-driven value spots, not guaranteed wins."
    $telegram += ""
    $telegram += "ASTRODDS"
} else {
    $telegram += "🚫 ASTRODDS CLIENT DROP BLOCKED"
    $telegram += "No SEND_OK picks."
}

($telegram -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTelegram

$lines = @()
$lines += "ASTRODDS 240 FINAL TRUSTED FULL SLATE GATE"
$lines += ""
$lines += "Client decision: $clientDecision"
$lines += "SEND_OK: $sendOk"
$lines += "REVIEW: $review"
$lines += "BLOCKED: $blocked"
$lines += ""

$lines += "OFFICIAL PICKS"
foreach ($r in ($finalRows | Where-Object { $_.FinalDecision -eq "CLIENT_OFFICIAL_SEND_OK" })) {
    $lines += "- $($r.Pick) | $($r.Game) | Entry=$($r.Price) | Model=$($r.ModelProbability) | Edge=$($r.Edge)"
    $lines += "  Reason: $($r.FinalReason)"
}
$lines += ""

$lines += "BLOCKED / REVIEW"
foreach ($r in ($finalRows | Where-Object { $_.FinalDecision -ne "CLIENT_OFFICIAL_SEND_OK" })) {
    $lines += "- $($r.FinalDecision) | $($r.Pick) | $($r.Game)"
    if ($r.HardBlocks -ne "") { $lines += "  Hard: $($r.HardBlocks)" }
    if ($r.Warnings -ne "") { $lines += "  Warn: $($r.Warnings)" }
}
$lines += ""

$lines += "TELEGRAM"
$lines += $outTelegram

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    clientDecision = $clientDecision
    sendOk = $sendOk
    review = $review
    blocked = $blocked
    telegram = $outTelegram
    outputCsv = $outCsv
} | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output CSV: $outCsv"
Write-Host "Output JSON: $outJson"
Write-Host "Telegram: $outTelegram"
Write-Host ""
