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

$scheduleCsv = Join-Path $astro "ASTRODDS-source-mlb-schedule-latest.csv"
$outCsv = Join-Path $astro "ASTRODDS-ballpark-advanced-factors-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-293-ballpark-advanced-factors-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-293-ballpark-advanced-factors-latest.json"

Write-Host ""
Write-Host "ASTRODDS 293 BALLPARK ADVANCED FACTORS" -ForegroundColor Cyan
Write-Host "Static park/elevation/roof baseline table. No API call." -ForegroundColor Cyan
Write-Host ""

$schedule = Safe-Csv $scheduleCsv

$parks = @{
    "Coors Field" = @{ElevationFt=5200; ParkRunFactor=1.15; Roof="open"; Orientation="varies"}
    "Chase Field" = @{ElevationFt=1086; ParkRunFactor=1.02; Roof="retractable"; Orientation="varies"}
    "Wrigley Field" = @{ElevationFt=600; ParkRunFactor=1.08; Roof="open"; Orientation="varies"}
    "Fenway Park" = @{ElevationFt=20; ParkRunFactor=1.05; Roof="open"; Orientation="varies"}
    "Yankee Stadium" = @{ElevationFt=55; ParkRunFactor=1.03; Roof="open"; Orientation="varies"}
    "Great American Ball Park" = @{ElevationFt=489; ParkRunFactor=1.08; Roof="open"; Orientation="varies"}
    "Citizens Bank Park" = @{ElevationFt=20; ParkRunFactor=1.04; Roof="open"; Orientation="varies"}
    "Dodger Stadium" = @{ElevationFt=522; ParkRunFactor=0.98; Roof="open"; Orientation="varies"}
    "T-Mobile Park" = @{ElevationFt=10; ParkRunFactor=0.96; Roof="retractable"; Orientation="varies"}
    "Busch Stadium" = @{ElevationFt=466; ParkRunFactor=0.98; Roof="open"; Orientation="varies"}
    "Minute Maid Park" = @{ElevationFt=50; ParkRunFactor=1.01; Roof="retractable"; Orientation="varies"}
    "American Family Field" = @{ElevationFt=617; ParkRunFactor=1.00; Roof="retractable"; Orientation="varies"}
    "Truist Park" = @{ElevationFt=1000; ParkRunFactor=1.01; Roof="open"; Orientation="varies"}
    "Nationals Park" = @{ElevationFt=25; ParkRunFactor=1.00; Roof="open"; Orientation="varies"}
    "Sutter Health Park" = @{ElevationFt=30; ParkRunFactor=1.00; Roof="open"; Orientation="varies"}
}

$out = @()
foreach ($g in $schedule) {
    $venue = Get-Val $g @("Venue")
    $p = $null
    if ($parks.ContainsKey($venue)) { $p = $parks[$venue] }
    $status = "CONNECTED_STATIC"
    if ($null -eq $p) {
        $p = @{ElevationFt=""; ParkRunFactor=""; Roof="unknown"; Orientation="unknown"}
        $status = "MISSING_STATIC_PARK"
    }

    $out += ,[pscustomobject]@{
        Source = "ASTRODDS_STATIC_BALLPARK_FACTORS"
        Game = Get-Val $g @("Game")
        GamePk = Get-Val $g @("GamePk")
        Venue = $venue
        ElevationFt = $p.ElevationFt
        ParkRunFactor = $p.ParkRunFactor
        RoofType = $p.Roof
        FieldOrientation = $p.Orientation
        BallparkFactorStatus = $status
        ImpactNote = "More important for totals; moderate for moneyline context."
    }
}

$out | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv
$out | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

$lines = @()
$lines += "ASTRODDS 293 BALLPARK ADVANCED FACTORS"
$lines += ""
$lines += "Rows: $($out.Count)"
foreach ($r in $out) {
    $lines += "- $($r.Game) | $($r.Venue) | elevation=$($r.ElevationFt) | parkFactor=$($r.ParkRunFactor) | roof=$($r.RoofType) | $($r.BallparkFactorStatus)"
}
($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
