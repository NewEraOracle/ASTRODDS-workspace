$ErrorActionPreference = "Continue"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$outCsv = Join-Path $astro "ASTRODDS-source-first-context-board-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-278-rebuild-source-board-quality-sources-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-278-rebuild-source-board-quality-sources-latest.json"

Write-Host ""
Write-Host "ASTRODDS 278 REBUILD SOURCE BOARD WITH QUALITY SOURCES" -ForegroundColor Cyan
Write-Host ""


function Ensure-Dir($path) {
    if (!(Test-Path $path)) { New-Item -ItemType Directory -Force -Path $path | Out-Null }
}

function Invoke-Json($url, $timeout = 25) {
    try { return Invoke-RestMethod -Uri $url -Method Get -TimeoutSec $timeout }
    catch { return $null }
}

function Write-Json($obj, $path) {
    $obj | ConvertTo-Json -Depth 25 | Set-Content -Encoding UTF8 $path
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

$schedule = Safe-Csv (Join-Path $astro "ASTRODDS-source-mlb-schedule-latest.csv")
$lineups = Safe-Csv (Join-Path $astro "ASTRODDS-source-live-lineups-latest.csv")
$weather = Safe-Csv (Join-Path $astro "ASTRODDS-weather-ballpark-context-latest.csv")
$injury = Safe-Csv (Join-Path $astro "ASTRODDS-free-injury-context-gate-latest.csv")
$pitcher = Safe-Csv (Join-Path $astro "ASTRODDS-lineup-pitcher-live-context-latest.csv")
$bullpen = Safe-Csv (Join-Path $astro "ASTRODDS-bullpen-fatigue-context-latest.csv")
$market = Safe-Csv (Join-Path $astro "ASTRODDS-market-moneyline-source-latest.csv")
$control = Safe-Csv (Join-Path $astro "ASTRODDS-schedule-first-full-slate-control-board-latest.csv")

$rows = @()

foreach ($g in $schedule) {
    $game = Get-Val $g @("Game")
    $l = Find-By-Game $lineups $game
    $w = Find-By-Game $weather $game
    $i = Find-By-Game $injury $game
    $p = Find-By-Game $pitcher $game
    $b = Find-By-Game $bullpen $game
    $c = Find-By-Game $control $game

    $marketRows = @($market | Where-Object { (Game-Key (Get-Val $_ @("Game"))) -eq (Game-Key $game) })
    $marketCount = $marketRows.Count

    $awayLineup = Get-Val $l @("AwayLineupStatus")
    $homeLineup = Get-Val $l @("HomeLineupStatus")
    if ($awayLineup -eq "") { $awayLineup = Get-Val $c @("AwayLineupStatus") }
    if ($homeLineup -eq "") { $homeLineup = Get-Val $c @("HomeLineupStatus") }

    $missing = @()
    if ($awayLineup -ne "confirmed" -or $homeLineup -ne "confirmed") { $missing += "lineup" }
    if ($null -eq $w) { $missing += "weather" }
    if ($null -eq $i) { $missing += "injury" }
    if ($null -eq $p) { $missing += "pitcher" }
    if ($null -eq $b) { $missing += "bullpen_rolling" }
    if ($marketCount -eq 0) { $missing += "market" }

    $full = if ($missing.Count -eq 0) { "YES" } else { "NO" }

    $rows += ,[pscustomobject]@{
        Source = "ASTRODDS_278_QUALITY_SOURCE_BOARD"
        ScheduleDate = Get-Date -Format "yyyy-MM-dd"
        GamePk = Get-Val $g @("GamePk")
        Game = $game
        AwayTeam = Get-Val $g @("AwayTeam")
        HomeTeam = Get-Val $g @("HomeTeam")
        Venue = Get-Val $g @("Venue")
        MlbStatus = Get-Val $g @("MlbStatus")
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
        AwayInjuredCount = Get-Val $i @("AwayInjuredCount")
        HomeInjuredCount = Get-Val $i @("HomeInjuredCount")
        AwayBullpenFatigue3d = Get-Val $b @("AwayBullpenFatigue3d")
        AwayBullpenFatigue7d = Get-Val $b @("AwayBullpenFatigue7d")
        HomeBullpenFatigue3d = Get-Val $b @("HomeBullpenFatigue3d")
        HomeBullpenFatigue7d = Get-Val $b @("HomeBullpenFatigue7d")
        MarketRowsFound = $marketCount
        FullContextConnected = $full
        MissingContext = ($missing -join "|")
        FetchedAt = (Get-Date).ToString("o")
    }
}

$rows | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$fullCount = @($rows | Where-Object { $_.FullContextConnected -eq "YES" }).Count
$marketCountRows = @($rows | Where-Object { [int]($_.MarketRowsFound) -gt 0 }).Count

$lines = @()
$lines += "ASTRODDS 278 REBUILD SOURCE BOARD WITH QUALITY SOURCES"
$lines += ""
$lines += "Rows: $($rows.Count)"
$lines += "Full context rows: $fullCount"
$lines += "Rows with market: $marketCountRows"
$lines += ""
foreach ($r in ($rows | Select-Object -First 12)) {
    $lines += "- $($r.Game) | full=$($r.FullContextConnected) | marketRows=$($r.MarketRowsFound) | missing=$($r.MissingContext)"
}
$lines += ""
$lines += "Output: $outCsv"

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    rows = $rows.Count
    fullContextRows = $fullCount
    rowsWithMarket = $marketCountRows
    outputCsv = $outCsv
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
exit 0
