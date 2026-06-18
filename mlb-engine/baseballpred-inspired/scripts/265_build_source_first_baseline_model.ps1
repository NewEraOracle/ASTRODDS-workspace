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
    foreach ($x in $arr) {
        $n = Num $x
        if ($null -ne $n) {
            if ($n -gt 1) { $n = $n / 100.0 }
            if ($n -gt 0 -and $n -lt 1) { $vals += $n }
        }
    }
    if ($vals.Count -eq 0) { return $null }
    return (($vals | Measure-Object -Average).Average)
}

function Fatigue-Penalty($v) {
    $x = "$v".ToLower()
    if ($x -match "high") { return 2.5 }
    if ($x -match "medium") { return 1.2 }
    return 0.0
}

function Injury-Penalty($v) {
    $x = "$v".ToLower()
    if ($x -match "high") { return 3.0 }
    if ($x -match "medium") { return 1.5 }
    if ($x -match "low") { return 0.5 }
    return 0.0
}


$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$sourceBoard = Join-Path $astro "ASTRODDS-source-first-context-board-latest.csv"
$marketCsv = Join-Path $astro "ASTRODDS-market-moneyline-source-latest.csv"
$outCsv = Join-Path $astro "ASTRODDS-265-source-first-baseline-model-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-265-source-first-baseline-model-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-265-source-first-baseline-model-latest.json"

Write-Host ""
Write-Host "ASTRODDS 265G MARKET-AWARE SOURCE-FIRST MODEL" -ForegroundColor Cyan
Write-Host "Fix: probabilities now vary by game using cached odds + context. Does not call Odds API." -ForegroundColor Cyan
Write-Host ""

$rows = Safe-Csv $sourceBoard
$markets = Safe-Csv $marketCsv
$out = @()

foreach ($r in @($rows)) {
    $game = Get-Val $r @("Game")
    if ($game -eq "") { continue }

    $awayTeamName = Get-Val $r @("AwayTeam")
    $homeTeamName = Get-Val $r @("HomeTeam")

    $gameMarkets = @($markets | Where-Object { (Game-Key (Get-Val $_ @("Game"))) -eq (Game-Key $game) })
    $awayMarketVals = @()
    $homeMarketVals = @()

    foreach ($m in $gameMarkets) {
        $pick = Normalize-Team (Get-Val $m @("Pick"))
        $mp = Get-Val $m @("MarketProbability","Entry")
        if ($pick -eq (Normalize-Team $awayTeamName)) { $awayMarketVals += $mp }
        if ($pick -eq (Normalize-Team $homeTeamName)) { $homeMarketVals += $mp }
    }

    $awayMarket = Avg $awayMarketVals
    $homeMarket = Avg $homeMarketVals

    # If cached market exists, use it as prior; else neutral + home field.
    if ($null -ne $awayMarket -and $null -ne $homeMarket) {
        # Normalize overround roughly so away+home = 1.
        $sum = $awayMarket + $homeMarket
        if ($sum -gt 0) {
            $awayBase = ($awayMarket / $sum) * 100.0
            $homeBase = ($homeMarket / $sum) * 100.0
        } else {
            $awayBase = 48.5
            $homeBase = 51.5
        }
        $marketStatus = "MARKET_PRIOR_CONNECTED"
    } else {
        $awayBase = 48.5
        $homeBase = 51.5
        $marketStatus = "NO_MARKET_PRIOR_NEUTRAL_HOME"
    }

    $awayAdj = 0.0
    $homeAdj = 0.0
    $flags = @()

    $awayLineup = Get-Val $r @("AwayLineupStatus")
    $homeLineup = Get-Val $r @("HomeLineupStatus")
    if ($awayLineup -ne "confirmed") { $awayAdj -= 1.8; $flags += "away_lineup_missing" }
    if ($homeLineup -ne "confirmed") { $homeAdj -= 1.8; $flags += "home_lineup_missing" }

    $awayPitcher = Get-Val $r @("AwayProbablePitcher")
    $homePitcher = Get-Val $r @("HomeProbablePitcher")
    if ($awayPitcher -ne "") { $awayAdj += 0.7; $flags += "away_pitcher_known" } else { $awayAdj -= 0.7; $flags += "away_pitcher_missing" }
    if ($homePitcher -ne "") { $homeAdj += 0.7; $flags += "home_pitcher_known" } else { $homeAdj -= 0.7; $flags += "home_pitcher_missing" }

    $awayAdj -= Injury-Penalty (Get-Val $r @("AwayInjuryRisk"))
    $homeAdj -= Injury-Penalty (Get-Val $r @("HomeInjuryRisk"))

    $awayAdj -= [math]::Max((Fatigue-Penalty (Get-Val $r @("AwayBullpenFatigue3d"))), (Fatigue-Penalty (Get-Val $r @("AwayBullpenFatigue7d"))))
    $homeAdj -= [math]::Max((Fatigue-Penalty (Get-Val $r @("HomeBullpenFatigue3d"))), (Fatigue-Penalty (Get-Val $r @("HomeBullpenFatigue7d"))))

    $weatherRisk = Get-Val $r @("WeatherRisk")
    if ($weatherRisk -eq "high") { $awayAdj -= 0.3; $homeAdj -= 0.3; $flags += "weather_high" }
    elseif ($weatherRisk -eq "medium") { $awayAdj -= 0.15; $homeAdj -= 0.15; $flags += "weather_medium" }

    # Small home contextual advantage remains, but no longer dominates.
    $homeAdj += 0.6

    $awayProb = Clamp ($awayBase + $awayAdj - ($homeAdj * 0.15)) 20.0 80.0
    $homeProb = Clamp ($homeBase + $homeAdj - ($awayAdj * 0.15)) 20.0 80.0

    # Normalize after adjustments.
    $s = $awayProb + $homeProb
    if ($s -gt 0) {
        $awayProb = ($awayProb / $s) * 100.0
        $homeProb = ($homeProb / $s) * 100.0
    }

    if ($homeProb -ge $awayProb) {
        $pick = $homeTeamName
        $modelProb = $homeProb
        $oppProb = $awayProb
        $pickMarket = $homeMarket
    } else {
        $pick = $awayTeamName
        $modelProb = $awayProb
        $oppProb = $homeProb
        $pickMarket = $awayMarket
    }

    # Conservative clamp: no baseline model should claim crazy certainty.
    $modelProb = Clamp $modelProb 52.0 68.0

    $edge = ""
    if ($null -ne $pickMarket) {
        $edgeVal = $modelProb - ($pickMarket * 100.0)
        $edge = ([math]::Round($edgeVal, 1)).ToString() + "%"
    }

    $confidence = 55.0 + (($modelProb - 50.0) * 1.15)
    if ((Get-Val $r @("FullContextConnected")) -eq "YES") { $confidence += 5.0 }
    if ($awayLineup -eq "confirmed" -and $homeLineup -eq "confirmed") { $confidence += 4.0 }
    if ($marketStatus -eq "MARKET_PRIOR_CONNECTED") { $confidence += 4.0 }
    $confidence = Clamp $confidence 50.0 90.0

    $modelStatus = "MODEL_READY_REVIEW"
    if ((Get-Val $r @("FullContextConnected")) -eq "YES" -and $awayLineup -eq "confirmed" -and $homeLineup -eq "confirmed" -and $marketStatus -eq "MARKET_PRIOR_CONNECTED") {
        $modelStatus = "MODEL_READY_FULL_CONTEXT_MARKET_AWARE"
    }

    $out += ,[pscustomobject]@{
        Source = "ASTRODDS_265G_MARKET_AWARE_SOURCE_FIRST_MODEL"
        ScheduleDate = Get-Date -Format "yyyy-MM-dd"
        GamePk = Get-Val $r @("GamePk")
        Game = $game
        AwayTeam = $awayTeamName
        HomeTeam = $homeTeamName
        MlbStatus = Get-Val $r @("MlbStatus")
        Pick = $pick
        ModelProbability = ([math]::Round($modelProb, 1)).ToString() + "%"
        ModelProbabilityRaw = [math]::Round(($modelProb / 100.0), 6)
        AwayModelProbability = ([math]::Round($awayProb, 1)).ToString() + "%"
        HomeModelProbability = ([math]::Round($homeProb, 1)).ToString() + "%"
        AwayMarketAvg = if ($null -ne $awayMarket) { ([math]::Round($awayMarket*100,1)).ToString() + "%" } else { "" }
        HomeMarketAvg = if ($null -ne $homeMarket) { ([math]::Round($homeMarket*100,1)).ToString() + "%" } else { "" }
        Edge = $edge
        SourceFirstConfidence = [int][math]::Round($confidence, 0)
        ModelType = "MARKET_AWARE_SOURCE_FIRST_BASELINE_UNCALIBRATED"
        ModelStatus = $modelStatus
        MarketPriorStatus = $marketStatus
        MarketRowsFound = $gameMarkets.Count
        AwayLineupStatus = $awayLineup
        HomeLineupStatus = $homeLineup
        WeatherRisk = $weatherRisk
        AwayInjuryRisk = Get-Val $r @("AwayInjuryRisk")
        HomeInjuryRisk = Get-Val $r @("HomeInjuryRisk")
        AwayBullpenFatigue3d = Get-Val $r @("AwayBullpenFatigue3d")
        AwayBullpenFatigue7d = Get-Val $r @("AwayBullpenFatigue7d")
        HomeBullpenFatigue3d = Get-Val $r @("HomeBullpenFatigue3d")
        HomeBullpenFatigue7d = Get-Val $r @("HomeBullpenFatigue7d")
        FullContextConnected = Get-Val $r @("FullContextConnected")
        MissingContext = Get-Val $r @("MissingContext")
        ModelFlags = ($flags -join "|")
        FetchedAt = (Get-Date).ToString("o")
    }
}

$out | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$uniqueProb = @($out | Select-Object -ExpandProperty ModelProbability -Unique).Count
$marketConnected = @($out | Where-Object { $_.MarketPriorStatus -eq "MARKET_PRIOR_CONNECTED" }).Count

$lines = @()
$lines += "ASTRODDS 265G MARKET-AWARE SOURCE-FIRST MODEL"
$lines += ""
$lines += "Rows scored: $($out.Count)"
$lines += "Unique model probabilities: $uniqueProb"
$lines += "Market-prior connected rows: $marketConnected"
$lines += ""
$lines += "MODEL BOARD"
foreach ($r in ($out | Sort-Object ModelProbability -Descending)) {
    $lines += "- $($r.Pick) | $($r.Game) | Model=$($r.ModelProbability) | Edge=$($r.Edge) | Away=$($r.AwayModelProbability) Home=$($r.HomeModelProbability) | MarketRows=$($r.MarketRowsFound) | Status=$($r.MlbStatus)"
}
$lines += ""
$lines += "IMPORTANT"
$lines += "- This model uses cached market as prior, so probabilities now vary by game."
$lines += "- It does not call Odds API."
$lines += "- It remains uncalibrated until enough results settle."

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    rowsScored = $out.Count
    uniqueModelProbabilities = $uniqueProb
    marketPriorConnectedRows = $marketConnected
    outputCsv = $outCsv
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
exit 0
