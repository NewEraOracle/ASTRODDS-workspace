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

function Clamp($x, $lo, $hi) {
    if ($x -lt $lo) { return $lo }
    if ($x -gt $hi) { return $hi }
    return $x
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

function Avg($arr) {
    $vals = @()
    foreach ($x in @($arr)) {
        $n = Num $x
        if ($null -ne $n) {
            if ($n -gt 1) { $n = $n / 100.0 }
            if ($n -gt 0 -and $n -lt 1) { $vals += $n }
        }
    }
    if ($vals.Count -eq 0) { return $null }
    return (($vals | Measure-Object -Average).Average)
}

function Load-EnvLocal($root) {
    $envFile = Join-Path $root ".env.local"
    if (Test-Path $envFile) {
        Get-Content $envFile | ForEach-Object {
            if ($_ -match "^\s*([^#][A-Za-z0-9_]+)\s*=\s*(.+)\s*$") {
                $name = $matches[1].Trim()
                $value = $matches[2].Trim().Trim('"').Trim("'")
                [Environment]::SetEnvironmentVariable($name, $value, "Process")
            }
        }
    }
    if ($env:THE_ODDS_API_KEY -and -not $env:ODDS_API_KEY) { $env:ODDS_API_KEY = $env:THE_ODDS_API_KEY }
    if ($env:ASTRODDS_ODDS_API_KEY -and -not $env:ODDS_API_KEY) { $env:ODDS_API_KEY = $env:ASTRODDS_ODDS_API_KEY }
}

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$modelCsv = Join-Path $astro "ASTRODDS-265-source-first-baseline-model-latest.csv"
$marketCsv = Join-Path $astro "ASTRODDS-market-moneyline-source-latest.csv"
$outCsv = Join-Path $astro "ASTRODDS-289-best-price-line-shopping-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-289-best-price-line-shopping-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-289-best-price-line-shopping-latest.json"

Write-Host ""
Write-Host "ASTRODDS 289 BEST PRICE / LINE SHOPPING BOARD" -ForegroundColor Cyan
Write-Host "Finds best book entry and edge vs average market. Does not call Odds API." -ForegroundColor Cyan
Write-Host ""

$model = Safe-Csv $modelCsv
$markets = Safe-Csv $marketCsv
$out = @()

foreach ($m in @($model)) {
    $game = Get-Val $m @("Game")
    $pick = Get-Val $m @("Pick")
    if ($game -eq "" -or $pick -eq "") { continue }

    $modelProb = Num (Get-Val $m @("ModelProbabilityRaw","ModelProbability"))
    if ($null -eq $modelProb) { continue }
    if ($modelProb -gt 1) { $modelProb = $modelProb / 100.0 }

    $gamePickMarkets = @($markets | Where-Object {
        (Game-Key (Get-Val $_ @("Game"))) -eq (Game-Key $game) -and
        (Normalize-Team (Get-Val $_ @("Pick"))) -eq (Normalize-Team $pick)
    })

    $prices = @()
    foreach ($r in $gamePickMarkets) {
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

    if ($null -ne $best) {
        $edgeBestNum = ($modelProb - $best.MarketProbability) * 100
        $edgeAvgNum = ($modelProb - $avg) * 100
        $edgeBest = ([math]::Round($edgeBestNum,1)).ToString() + "%"
        $edgeAvg = ([math]::Round($edgeAvgNum,1)).ToString() + "%"
        $book = $best.Bookmaker
        $bestEntry = $best.Entry
        $avgEntry = ([math]::Round($avg*100,1)).ToString() + "¢"

        if ($edgeBestNum -ge 5) { $lineShopDecision = "BEST_PRICE_OFFICIAL_CANDIDATE" }
        elseif ($edgeBestNum -ge 3) { $lineShopDecision = "BEST_PRICE_REVIEW_CANDIDATE" }
        elseif ($edgeBestNum -gt 0) { $lineShopDecision = "SMALL_EDGE_WATCHLIST" }
        else { $lineShopDecision = "NO_VALUE_AT_CURRENT_PRICES" }
    }

    $out += ,[pscustomobject]@{
        LineShopDecision = $lineShopDecision
        Pick = $pick
        Game = $game
        MlbStatus = Get-Val $m @("MlbStatus")
        ModelProbability = Get-Val $m @("ModelProbability")
        BestEntry = $bestEntry
        BestBook = $book
        AvgEntry = $avgEntry
        EdgeVsBest = $edgeBest
        EdgeVsAverage = $edgeAvg
        MarketRows = $prices.Count
        Confidence = Get-Val $m @("SourceFirstConfidence")
        Lineups = (Get-Val $m @("AwayLineupStatus")) + "/" + (Get-Val $m @("HomeLineupStatus"))
        FullContextConnected = Get-Val $m @("FullContextConnected")
        ModelStatus = Get-Val $m @("ModelStatus")
    }
}

$out | Sort-Object LineShopDecision, EdgeVsBest -Descending | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$official = @($out | Where-Object { $_.LineShopDecision -eq "BEST_PRICE_OFFICIAL_CANDIDATE" }).Count
$review = @($out | Where-Object { $_.LineShopDecision -eq "BEST_PRICE_REVIEW_CANDIDATE" }).Count

$lines = @()
$lines += "ASTRODDS 289 BEST PRICE / LINE SHOPPING BOARD"
$lines += ""
$lines += "Rows: $($out.Count)"
$lines += "Official candidates by best price: $official"
$lines += "Review candidates by best price: $review"
$lines += ""
$lines += "BOARD"
foreach ($r in ($out | Select-Object -First 20)) {
    $lines += "- $($r.LineShopDecision) | $($r.Pick) | $($r.Game) | Model=$($r.ModelProbability) | Best=$($r.BestEntry) $($r.BestBook) | Avg=$($r.AvgEntry) | EdgeBest=$($r.EdgeVsBest) | EdgeAvg=$($r.EdgeVsAverage)"
}
$lines += ""
$lines += "IMPORTANT"
$lines += "- Best price can turn average-market negative edge into real value."
$lines += "- Still not official unless production gate, pregame, lineups and no late drop pass."

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    rows = $out.Count
    officialCandidates = $official
    reviewCandidates = $review
    outputCsv = $outCsv
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
