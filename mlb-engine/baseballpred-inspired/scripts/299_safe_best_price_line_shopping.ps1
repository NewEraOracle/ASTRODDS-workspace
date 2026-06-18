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

function Normalize-Team($s) {
    $x = "$s".ToLower().Trim()
    $x = $x -replace "[^a-z0-9 ]", ""
    $x = $x -replace "\s+", " "
    return $x
}

function Game-Key($game) {
    $g = "$game"
    $awayTeamName = ""
    $homeTeamName = ""
    if ($g -match "\s@\s") {
        $parts = $g -split "\s@\s", 2
        $awayTeamName = "$($parts[0])".Trim()
        $homeTeamName = "$($parts[1])".Trim()
    } elseif ($g -match "\svs\s") {
        $parts = $g -split "\svs\s", 2
        $awayTeamName = "$($parts[0])".Trim()
        $homeTeamName = "$($parts[1])".Trim()
    } else {
        return (Normalize-Team $g)
    }
    return (Normalize-Team $awayTeamName) + " @ " + (Normalize-Team $homeTeamName)
}

function Find-By-Game($rows, $game) {
    $k = Game-Key $game
    foreach ($r in @($rows)) {
        $g = Get-Val $r @("Game","game")
        if ($g -eq "") { continue }
        if ((Game-Key $g) -eq $k) { return $r }
    }
    return $null
}

function Clamp($x, $lo, $hi) {
    if ($x -lt $lo) { return $lo }
    if ($x -gt $hi) { return $hi }
    return $x
}

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$modelCsv = Join-Path $astro "ASTRODDS-265-source-first-baseline-model-latest.csv"
$marketCsv = Join-Path $astro "ASTRODDS-market-moneyline-source-latest.csv"
$outCsv = Join-Path $astro "ASTRODDS-289-best-price-line-shopping-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-299-safe-best-price-line-shopping-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-299-safe-best-price-line-shopping-latest.json"

Write-Host ""
Write-Host "ASTRODDS 299 SAFE BEST PRICE / LINE SHOPPING" -ForegroundColor Cyan
Write-Host "Fix: external books preferred, internal stale guarded, in-progress blocked." -ForegroundColor Cyan
Write-Host ""

$model = Safe-Csv $modelCsv
$markets = Safe-Csv $marketCsv
$out = @()

foreach ($m in @($model)) {
    $game = Get-Val $m @("Game")
    $pick = Get-Val $m @("Pick")
    if ($game -eq "" -or $pick -eq "") { continue }

    $status = Get-Val $m @("MlbStatus")
    $modelProb = Num (Get-Val $m @("ModelProbabilityRaw","ModelProbability"))
    if ($null -eq $modelProb) { continue }
    if ($modelProb -gt 1) { $modelProb = $modelProb / 100.0 }

    $gamePickMarketsAll = @($markets | Where-Object {
        (Game-Key (Get-Val $_ @("Game"))) -eq (Game-Key $game) -and
        (Normalize-Team (Get-Val $_ @("Pick"))) -eq (Normalize-Team $pick)
    })

    $external = @($gamePickMarketsAll | Where-Object { (Get-Val $_ @("Source")) -like "THE_ODDS_API*" })
    $internal = @($gamePickMarketsAll | Where-Object { (Get-Val $_ @("Source")) -like "ASTRODDS*" })

    # Use external if present. Internal fallback is allowed for display/review only.
    $marketRowsUsed = if ($external.Count -gt 0) { $external } else { $internal }
    $sourceMode = if ($external.Count -gt 0) { "EXTERNAL_BOOKS" } elseif ($internal.Count -gt 0) { "INTERNAL_FALLBACK_ONLY" } else { "NO_MARKET" }

    $prices = @()
    foreach ($r in $marketRowsUsed) {
        $p = Num (Get-Val $r @("MarketProbability","Entry"))
        if ($null -ne $p) {
            if ($p -gt 1) { $p = $p / 100.0 }
            if ($p -gt 0 -and $p -lt 1) {
                $prices += ,[pscustomobject]@{
                    Bookmaker = Get-Val $r @("Bookmaker")
                    MarketProbability = $p
                    Entry = ([math]::Round($p*100,1)).ToString() + "¢"
                    Source = Get-Val $r @("Source")
                }
            }
        }
    }

    $best = $null
    $avg = $null
    if ($prices.Count -gt 0) {
        $best = $prices | Sort-Object MarketProbability | Select-Object -First 1
        $avg = (($prices | Select-Object -ExpandProperty MarketProbability) | Measure-Object -Average).Average
    }

    $edgeBest = ""
    $edgeAvg = ""
    $lineShopDecision = "NO_MARKET"
    $book = ""
    $bestEntry = ""
    $avgEntry = ""
    $hard = @()
    $warn = @()

    if ($status -match "In Progress|Final|Game Over|Delayed|Suspended") {
        $hard += "game status not eligible for new client drop: $status"
    }

    if ($sourceMode -eq "INTERNAL_FALLBACK_ONLY") {
        $warn += "internal fallback only; cannot be client official from line shopping"
    }

    if ($sourceMode -eq "NO_MARKET") {
        $hard += "no market price"
    }

    if ($null -ne $best) {
        $edgeBestNum = ($modelProb - $best.MarketProbability) * 100
        $edgeAvgNum = ($modelProb - $avg) * 100
        $edgeBest = ([math]::Round($edgeBestNum,1)).ToString() + "%"
        $edgeAvg = ([math]::Round($edgeAvgNum,1)).ToString() + "%"
        $book = $best.Bookmaker
        $bestEntry = $best.Entry
        $avgEntry = ([math]::Round($avg*100,1)).ToString() + "¢"

        if ($sourceMode -eq "EXTERNAL_BOOKS" -and $hard.Count -eq 0) {
            if ($edgeBestNum -ge 5) { $lineShopDecision = "BEST_PRICE_OFFICIAL_CANDIDATE" }
            elseif ($edgeBestNum -ge 3) { $lineShopDecision = "BEST_PRICE_REVIEW_CANDIDATE" }
            elseif ($edgeBestNum -gt 0) { $lineShopDecision = "SMALL_EDGE_WATCHLIST" }
            else { $lineShopDecision = "NO_VALUE_AT_CURRENT_PRICES" }
        } elseif ($sourceMode -eq "INTERNAL_FALLBACK_ONLY") {
            if ($edgeBestNum -ge 5) { $lineShopDecision = "INTERNAL_PRICE_REVIEW_ONLY" }
            else { $lineShopDecision = "NO_VALUE_AT_CURRENT_PRICES" }
        } else {
            $lineShopDecision = "BLOCKED_NOT_LIVE_SAFE"
        }
    }

    if ($hard.Count -gt 0 -and $lineShopDecision -eq "BEST_PRICE_OFFICIAL_CANDIDATE") {
        $lineShopDecision = "BLOCKED_NOT_LIVE_SAFE"
    }

    $out += ,[pscustomobject]@{
        LineShopDecision = $lineShopDecision
        Pick = $pick
        Game = $game
        MlbStatus = $status
        ModelProbability = Get-Val $m @("ModelProbability")
        BestEntry = $bestEntry
        BestBook = $book
        AvgEntry = $avgEntry
        EdgeVsBest = $edgeBest
        EdgeVsAverage = $edgeAvg
        MarketRows = $prices.Count
        ExternalMarketRows = $external.Count
        InternalMarketRows = $internal.Count
        MarketSourceMode = $sourceMode
        Confidence = Get-Val $m @("SourceFirstConfidence")
        Lineups = (Get-Val $m @("AwayLineupStatus")) + "/" + (Get-Val $m @("HomeLineupStatus"))
        FullContextConnected = Get-Val $m @("FullContextConnected")
        ModelStatus = Get-Val $m @("ModelStatus")
        HardBlocks = ($hard -join " | ")
        Warnings = ($warn -join " | ")
    }
}

$out | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$official = @($out | Where-Object { $_.LineShopDecision -eq "BEST_PRICE_OFFICIAL_CANDIDATE" }).Count
$review = @($out | Where-Object { $_.LineShopDecision -match "REVIEW" }).Count
$blocked = @($out | Where-Object { $_.HardBlocks -ne "" }).Count

$lines = @()
$lines += "ASTRODDS 299 SAFE BEST PRICE / LINE SHOPPING"
$lines += ""
$lines += "Rows: $($out.Count)"
$lines += "External official candidates: $official"
$lines += "Review candidates: $review"
$lines += "Rows with hard blocks: $blocked"
$lines += ""
$lines += "BOARD"
foreach ($r in ($out | Select-Object -First 20)) {
    $lines += "- $($r.LineShopDecision) | $($r.Pick) | $($r.Game) | status=$($r.MlbStatus) | Model=$($r.ModelProbability) | Best=$($r.BestEntry) $($r.BestBook) | EdgeBest=$($r.EdgeVsBest) | mode=$($r.MarketSourceMode)"
    if ($r.HardBlocks -ne "") { $lines += "  Hard=$($r.HardBlocks)" }
    if ($r.Warnings -ne "") { $lines += "  Warn=$($r.Warnings)" }
}
$lines += ""
$lines += "IMPORTANT"
$lines += "- Internal prices cannot create client official candidates."
$lines += "- In Progress / Delayed / Suspended / Final cannot become new drops."
$lines += "- External books are preferred over internal fallback."

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    rows = $out.Count
    externalOfficialCandidates = $official
    reviewCandidates = $review
    hardBlockedRows = $blocked
    outputCsv = $outCsv
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
