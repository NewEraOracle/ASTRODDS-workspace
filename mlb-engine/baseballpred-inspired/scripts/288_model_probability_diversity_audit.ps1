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

$modelCsv = Join-Path $astro "ASTRODDS-265-source-first-baseline-model-latest.csv"
$candidateCsv = Join-Path $astro "ASTRODDS-potential-candidate-board-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-288-model-probability-diversity-audit-latest.txt"
$outCsv = Join-Path $astro "ASTRODDS-288-model-probability-diversity-audit-latest.csv"
$outJson = Join-Path $astro "ASTRODDS-288-model-probability-diversity-audit-latest.json"

Write-Host ""
Write-Host "ASTRODDS 288 MODEL PROBABILITY DIVERSITY AUDIT" -ForegroundColor Cyan
Write-Host ""

$model = Safe-Csv $modelCsv
$candidates = Safe-Csv $candidateCsv

$uniqueProbs = @($model | Select-Object -ExpandProperty ModelProbability -Unique)
$flat = "NO"
if ($uniqueProbs.Count -le 2 -and $model.Count -gt 5) { $flat = "YES" }

$auditRows = @()
foreach ($r in $model) {
    $auditRows += ,[pscustomobject]@{
        Pick = Get-Val $r @("Pick")
        Game = Get-Val $r @("Game")
        MlbStatus = Get-Val $r @("MlbStatus")
        ModelProbability = Get-Val $r @("ModelProbability")
        Edge = Get-Val $r @("Edge")
        AwayModelProbability = Get-Val $r @("AwayModelProbability")
        HomeModelProbability = Get-Val $r @("HomeModelProbability")
        AwayMarketAvg = Get-Val $r @("AwayMarketAvg")
        HomeMarketAvg = Get-Val $r @("HomeMarketAvg")
        MarketRowsFound = Get-Val $r @("MarketRowsFound")
        ModelStatus = Get-Val $r @("ModelStatus")
        MarketPriorStatus = Get-Val $r @("MarketPriorStatus")
    }
}
$auditRows | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$lines = @()
$lines += "ASTRODDS 288 MODEL PROBABILITY DIVERSITY AUDIT"
$lines += ""
$lines += "Model rows: $($model.Count)"
$lines += "Unique model probabilities: $($uniqueProbs.Count)"
$lines += "Flat probability problem: $flat"
$lines += ""
$lines += "UNIQUE PROBABILITIES"
foreach ($p in $uniqueProbs) { $lines += "- $p" }
$lines += ""
$lines += "MODEL BOARD"
foreach ($r in ($auditRows | Sort-Object ModelProbability -Descending)) {
    $lines += "- $($r.Pick) | $($r.Game) | Model=$($r.ModelProbability) | Edge=$($r.Edge) | Away=$($r.AwayModelProbability) Home=$($r.HomeModelProbability) | MarketRows=$($r.MarketRowsFound)"
}
$lines += ""
$lines += "WHY IT WAS FLAT BEFORE"
$lines += "- Old 265 started with the same home-field score for almost every game."
$lines += "- When lineups/context were similar, every home pick received almost the same probability, around 56.8%."
$lines += ""
$lines += "WHAT 265G CHANGED"
$lines += "- Uses cached sportsbook market as a prior."
$lines += "- Adds context adjustments for lineup, pitcher, injury, bullpen, weather."
$lines += "- Does not call Odds API."
$lines += "- Still blocks official picks unless production gate passes."

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    modelRows = $model.Count
    uniqueModelProbabilities = $uniqueProbs.Count
    flatProbabilityProblem = $flat
    outputCsv = $outCsv
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
