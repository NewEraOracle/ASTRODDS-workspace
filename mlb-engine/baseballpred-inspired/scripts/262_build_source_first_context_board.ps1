$ErrorActionPreference = "Continue"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$outCsv = Join-Path $astro "ASTRODDS-source-first-context-board-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-262-source-first-context-board-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-262-source-first-context-board-latest.json"

Write-Host ""
Write-Host "ASTRODDS 262 BUILD SOURCE-FIRST CONTEXT BOARD" -ForegroundColor Cyan
Write-Host "Merges MLB schedule/lineups/pitchers/weather/injuries/bullpen into one board" -ForegroundColor Cyan
Write-Host ""


function Ensure-Dir($path) {
    if (!(Test-Path $path)) { New-Item -ItemType Directory -Force -Path $path | Out-Null }
}

function Invoke-Json($url, $timeout = 20) {
    try {
        return Invoke-RestMethod -Uri $url -Method Get -TimeoutSec $timeout
    } catch {
        return $null
    }
}

function Write-Json($obj, $path) {
    $obj | ConvertTo-Json -Depth 20 | Set-Content -Encoding UTF8 $path
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

function Normalize-Team($s) {
    $x = "$s".ToLower().Trim()
    $x = $x -replace "[^a-z0-9 ]", ""
    $x = $x -replace "\s+", " "
    return $x
}

function Game-Key($game) {
    $g = "$game"
    $away = ""
    $home = ""
    if ($g -match "\s@\s") {
        $parts = $g -split "\s@\s", 2
        $away = "$($parts[0])".Trim()
        $home = "$($parts[1])".Trim()
    } elseif ($g -match "\svs\s") {
        $parts = $g -split "\svs\s", 2
        $away = "$($parts[0])".Trim()
        $home = "$($parts[1])".Trim()
    } else {
        return (Normalize-Team $g)
    }
    return (Normalize-Team $away) + " @ " + (Normalize-Team $home)
}

$schedule = Safe-Csv (Join-Path $astro "ASTRODDS-source-mlb-schedule-latest.csv")
$lineups = Safe-Csv (Join-Path $astro "ASTRODDS-source-live-lineups-latest.csv")
$weather = Safe-Csv (Join-Path $astro "ASTRODDS-weather-ballpark-context-latest.csv")
$injury = Safe-Csv (Join-Path $astro "ASTRODDS-free-injury-context-gate-latest.csv")
$pitcher = Safe-Csv (Join-Path $astro "ASTRODDS-lineup-pitcher-live-context-latest.csv")
$bullpen = Safe-Csv (Join-Path $astro "ASTRODDS-bpen-game-relief-stats-latest.csv")
$control = Safe-Csv (Join-Path $astro "ASTRODDS-schedule-first-full-slate-control-board-latest.csv")

function Find-By-Game($rows, $game) {
    $k = Game-Key $game
    foreach ($r in $rows) {
        if ((Game-Key (Get-Val $r @("Game"))) -eq $k) { return $r }
    }
    return $null
}

$rows = @()

foreach ($g in $schedule) {
    $game = Get-Val $g @("Game")
    $l = Find-By-Game $lineups $game
    $w = Find-By-Game $weather $game
    $i = Find-By-Game $injury $game
    $p = Find-By-Game $pitcher $game
    $b = Find-By-Game $bullpen $game
    $c = Find-By-Game $control $game

    $pick = Get-Val $c @("Pick")
    $model = Get-Val $c @("ModelProbability")
    $market = Get-Val $c @("MarketProbability","Price")
    $edge = Get-Val $c @("Edge","EdgePct")
    $coverage = Get-Val $c @("CoverageStatus")
    $decision = Get-Val $c @("Decision")

    $awayLineup = Get-Val $l @("AwayLineupStatus")
    $homeLineup = Get-Val $l @("HomeLineupStatus")
    if ($awayLineup -eq "") { $awayLineup = Get-Val $c @("AwayLineupStatus") }
    if ($homeLineup -eq "") { $homeLineup = Get-Val $c @("HomeLineupStatus") }

    $fullContext = "YES"
    $missing = @()

    if ($awayLineup -ne "confirmed" -or $homeLineup -ne "confirmed") { $fullContext = "NO"; $missing += "lineup" }
    if ($null -eq $w) { $fullContext = "NO"; $missing += "weather" }
    if ($null -eq $i) { $fullContext = "NO"; $missing += "injury" }
    if ($null -eq $p) { $fullContext = "NO"; $missing += "pitcher" }
    if ($null -eq $b) { $fullContext = "NO"; $missing += "bullpen" }
    if ($model -eq "") { $fullContext = "NO"; $missing += "model" }
    if ($market -eq "") { $fullContext = "NO"; $missing += "market" }

    $rows += ,[pscustomobject]@{
        Source = "ASTRODDS_SOURCE_FIRST_BOARD"
        ScheduleDate = Get-Date -Format "yyyy-MM-dd"
        GamePk = Get-Val $g @("GamePk")
        Game = $game
        AwayTeam = Get-Val $g @("AwayTeam")
        HomeTeam = Get-Val $g @("HomeTeam")
        Venue = Get-Val $g @("Venue")
        MlbStatus = Get-Val $g @("MlbStatus")
        Pick = $pick
        ModelProbability = $model
        MarketProbability = $market
        Edge = $edge
        CoverageStatus = $coverage
        Decision = $decision
        AwayLineupStatus = $awayLineup
        HomeLineupStatus = $homeLineup
        AwayProbablePitcher = Get-Val $p @("AwayProbablePitcher")
        HomeProbablePitcher = Get-Val $p @("HomeProbablePitcher")
        WeatherRisk = Get-Val $w @("WeatherRisk")
        TemperatureF = Get-Val $w @("TemperatureF")
        WindMph = Get-Val $w @("WindMph")
        PrecipitationMm = Get-Val $w @("PrecipitationMm")
        AwayInjuryRisk = Get-Val $i @("AwayInjuryRisk")
        HomeInjuryRisk = Get-Val $i @("HomeInjuryRisk")
        AwayBullpenFatigueProxy = Get-Val $b @("AwayBullpenFatigueProxy")
        HomeBullpenFatigueProxy = Get-Val $b @("HomeBullpenFatigueProxy")
        FullContextConnected = $fullContext
        MissingContext = ($missing -join "|")
        FetchedAt = (Get-Date).ToString("o")
    }
}

$rows | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$full = @($rows | Where-Object { $_.FullContextConnected -eq "YES" }).Count
$partial = @($rows | Where-Object { $_.FullContextConnected -ne "YES" }).Count
$noModel = @($rows | Where-Object { $_.MissingContext -like "*model*" }).Count

$lines = @()
$lines += "ASTRODDS 262 BUILD SOURCE-FIRST CONTEXT BOARD"
$lines += ""
$lines += "Rows: $($rows.Count)"
$lines += "Full context connected: $full"
$lines += "Partial context: $partial"
$lines += "Missing model rows: $noModel"
$lines += ""
$lines += "BOARD"
foreach ($r in $rows) {
    $lines += "- $($r.Game) | status=$($r.MlbStatus) | pick=$($r.Pick) | model=$($r.ModelProbability) | market=$($r.MarketProbability) | edge=$($r.Edge) | fullContext=$($r.FullContextConnected)"
    if ($r.MissingContext -ne "") { $lines += "  Missing: $($r.MissingContext)" }
}
$lines += ""
$lines += "Output: $outCsv"

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    rows = $rows.Count
    fullContextConnected = $full
    partialContext = $partial
    missingModelRows = $noModel
    outputCsv = $outCsv
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
