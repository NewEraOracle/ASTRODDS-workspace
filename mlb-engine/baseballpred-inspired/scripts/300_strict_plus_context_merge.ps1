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

$outCsv = Join-Path $astro "ASTRODDS-baseballpred-plus-context-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-300-strict-plus-context-merge-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-300-strict-plus-context-merge-latest.json"

Write-Host ""
Write-Host "ASTRODDS 300 STRICT BASEBALLPRED++ CONTEXT MERGE" -ForegroundColor Cyan
Write-Host "Fix: empty advanced fields count as missing." -ForegroundColor Cyan
Write-Host ""

$source = Safe-Csv (Join-Path $astro "ASTRODDS-source-first-context-board-latest.csv")
$lineShop = Safe-Csv (Join-Path $astro "ASTRODDS-289-best-price-line-shopping-latest.csv")
$park = Safe-Csv (Join-Path $astro "ASTRODDS-ballpark-advanced-factors-latest.csv")
$travel = Safe-Csv (Join-Path $astro "ASTRODDS-travel-rest-timezone-context-latest.csv")
$cal = Safe-Csv (Join-Path $astro "ASTRODDS-292-calibrated-candidate-board-latest.csv")

$out = @()
foreach ($g in $source) {
    $game = Get-Val $g @("Game")
    $ls = Find-By-Game $lineShop $game
    $pk = Find-By-Game $park $game
    $tr = Find-By-Game $travel $game
    $ca = Find-By-Game $cal $game

    $missing = @()
    if ($null -eq $ls) { $missing += "line_shopping" }
    else {
        if ((Get-Val $ls @("BestEntry")) -eq "") { $missing += "best_price" }
        if ((Get-Val $ls @("MarketSourceMode")) -ne "EXTERNAL_BOOKS") { $missing += "external_market" }
    }

    if ($null -eq $pk) { $missing += "park_factor" }
    else {
        if ((Get-Val $pk @("ParkRunFactor")) -eq "") { $missing += "park_factor_value" }
        if ((Get-Val $pk @("ElevationFt")) -eq "") { $missing += "elevation" }
        if ((Get-Val $pk @("RoofType")) -eq "" -or (Get-Val $pk @("RoofType")) -eq "unknown") { $missing += "roof_type" }
    }

    if ($null -eq $tr) { $missing += "travel_rest" }
    else {
        if ((Get-Val $tr @("AwayTravelStress")) -eq "" -or (Get-Val $tr @("HomeTravelStress")) -eq "") { $missing += "travel_stress" }
    }

    if ($null -eq $ca) { $missing += "calibration" }
    else {
        if ((Get-Val $ca @("CalibratedConfidence")) -eq "") { $missing += "calibrated_confidence" }
    }

    $plusStatus = if ($missing.Count -eq 0) { "BASEBALLPRED_PLUS_CONNECTED" } else { "BASEBALLPRED_PLUS_PARTIAL" }

    $out += ,[pscustomobject]@{
        PlusStatus = $plusStatus
        Game = $game
        Pick = Get-Val $ls @("Pick")
        MlbStatus = Get-Val $g @("MlbStatus")
        ModelProbability = Get-Val $ca @("ModelProbability")
        CalibratedConfidence = Get-Val $ca @("CalibratedConfidence")
        BestEntry = Get-Val $ls @("BestEntry")
        BestBook = Get-Val $ls @("BestBook")
        MarketSourceMode = Get-Val $ls @("MarketSourceMode")
        EdgeVsBest = Get-Val $ls @("EdgeVsBest")
        EdgeVsAverage = Get-Val $ls @("EdgeVsAverage")
        Venue = Get-Val $pk @("Venue")
        ElevationFt = Get-Val $pk @("ElevationFt")
        ParkRunFactor = Get-Val $pk @("ParkRunFactor")
        RoofType = Get-Val $pk @("RoofType")
        AwayTravelStress = Get-Val $tr @("AwayTravelStress")
        HomeTravelStress = Get-Val $tr @("HomeTravelStress")
        MissingPlusContext = ($missing -join "|")
    }
}

$out | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv
$out | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

$connected = @($out | Where-Object { $_.PlusStatus -eq "BASEBALLPRED_PLUS_CONNECTED" }).Count
$partial = @($out | Where-Object { $_.PlusStatus -ne "BASEBALLPRED_PLUS_CONNECTED" }).Count

$lines = @()
$lines += "ASTRODDS 300 STRICT BASEBALLPRED++ CONTEXT MERGE"
$lines += ""
$lines += "Rows: $($out.Count)"
$lines += "Fully connected plus rows: $connected"
$lines += "Partial plus rows: $partial"
foreach ($r in $out) {
    $lines += "- $($r.PlusStatus) | $($r.Pick) | $($r.Game) | best=$($r.BestEntry) $($r.BestBook) | edgeBest=$($r.EdgeVsBest) | park=$($r.ParkRunFactor) | missing=$($r.MissingPlusContext)"
}

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
