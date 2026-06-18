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

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$scheduleCsv = Join-Path $astro "ASTRODDS-source-mlb-schedule-latest.csv"
$outCsv = Join-Path $astro "ASTRODDS-ballpark-advanced-factors-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-304-ballpark-alias-repair-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-304-ballpark-alias-repair-latest.json"

Write-Host ""
Write-Host "ASTRODDS 304 BALLPARK ALIAS REPAIR" -ForegroundColor Cyan
Write-Host "Repairs renamed venue aliases like Daikin Park and UNIQLO Field at Dodger Stadium." -ForegroundColor Cyan
Write-Host ""

$schedule = Safe-Csv $scheduleCsv

# Static baseline factors. These are practical model priors, not official betting guarantees.
# ParkRunFactor is a conservative relative run environment proxy for ASTRODDS context.
$parks = @{
    "coors field" = @{Canonical="Coors Field"; ElevationFt=5200; ParkRunFactor=1.15; Roof="open"; Orientation="varies"}
    "chase field" = @{Canonical="Chase Field"; ElevationFt=1086; ParkRunFactor=1.02; Roof="retractable"; Orientation="varies"}
    "wrigley field" = @{Canonical="Wrigley Field"; ElevationFt=600; ParkRunFactor=1.08; Roof="open"; Orientation="varies"}
    "fenway park" = @{Canonical="Fenway Park"; ElevationFt=20; ParkRunFactor=1.05; Roof="open"; Orientation="varies"}
    "yankee stadium" = @{Canonical="Yankee Stadium"; ElevationFt=55; ParkRunFactor=1.03; Roof="open"; Orientation="varies"}
    "great american ball park" = @{Canonical="Great American Ball Park"; ElevationFt=489; ParkRunFactor=1.08; Roof="open"; Orientation="varies"}
    "citizens bank park" = @{Canonical="Citizens Bank Park"; ElevationFt=20; ParkRunFactor=1.04; Roof="open"; Orientation="varies"}
    "dodger stadium" = @{Canonical="Dodger Stadium"; ElevationFt=522; ParkRunFactor=0.98; Roof="open"; Orientation="varies"}
    "uniqlo field at dodger stadium" = @{Canonical="Dodger Stadium"; ElevationFt=522; ParkRunFactor=0.98; Roof="open"; Orientation="varies"; AliasOf="Dodger Stadium"}
    "t-mobile park" = @{Canonical="T-Mobile Park"; ElevationFt=10; ParkRunFactor=0.96; Roof="retractable"; Orientation="varies"}
    "busch stadium" = @{Canonical="Busch Stadium"; ElevationFt=466; ParkRunFactor=0.98; Roof="open"; Orientation="varies"}
    "minute maid park" = @{Canonical="Daikin Park"; ElevationFt=50; ParkRunFactor=1.01; Roof="retractable"; Orientation="varies"; AliasOf="Daikin Park"}
    "daikin park" = @{Canonical="Daikin Park"; ElevationFt=50; ParkRunFactor=1.01; Roof="retractable"; Orientation="varies"; AliasOf="Minute Maid Park"}
    "american family field" = @{Canonical="American Family Field"; ElevationFt=617; ParkRunFactor=1.00; Roof="retractable"; Orientation="varies"}
    "truist park" = @{Canonical="Truist Park"; ElevationFt=1000; ParkRunFactor=1.01; Roof="open"; Orientation="varies"}
    "nationals park" = @{Canonical="Nationals Park"; ElevationFt=25; ParkRunFactor=1.00; Roof="open"; Orientation="varies"}
    "sutter health park" = @{Canonical="Sutter Health Park"; ElevationFt=30; ParkRunFactor=1.00; Roof="open"; Orientation="varies"}
    "loanDepot park".ToLower() = @{Canonical="loanDepot park"; ElevationFt=10; ParkRunFactor=0.98; Roof="retractable"; Orientation="varies"}
    "rogers centre" = @{Canonical="Rogers Centre"; ElevationFt=250; ParkRunFactor=1.00; Roof="retractable"; Orientation="varies"}
    "comerica park" = @{Canonical="Comerica Park"; ElevationFt=600; ParkRunFactor=0.97; Roof="open"; Orientation="varies"}
    "progressive field" = @{Canonical="Progressive Field"; ElevationFt=653; ParkRunFactor=1.00; Roof="open"; Orientation="varies"}
    "petco park" = @{Canonical="Petco Park"; ElevationFt=62; ParkRunFactor=0.94; Roof="open"; Orientation="varies"}
    "angel stadium" = @{Canonical="Angel Stadium"; ElevationFt=160; ParkRunFactor=0.98; Roof="open"; Orientation="varies"}
    "guaranteed rate field" = @{Canonical="Guaranteed Rate Field"; ElevationFt=594; ParkRunFactor=1.02; Roof="open"; Orientation="varies"}
    "camden yards" = @{Canonical="Oriole Park at Camden Yards"; ElevationFt=33; ParkRunFactor=1.03; Roof="open"; Orientation="varies"}
    "oriole park at camden yards" = @{Canonical="Oriole Park at Camden Yards"; ElevationFt=33; ParkRunFactor=1.03; Roof="open"; Orientation="varies"}
}

function Norm-Venue($s) {
    $x = "$s".ToLower().Trim()
    $x = $x -replace "\s+", " "
    return $x
}

$out = @()
$missing = @()

foreach ($g in $schedule) {
    $venue = Get-Val $g @("Venue")
    $key = Norm-Venue $venue
    $p = $null

    if ($parks.ContainsKey($key)) {
        $p = $parks[$key]
    } else {
        foreach ($k in $parks.Keys) {
            if ($key -like "*$k*" -or $k -like "*$key*") {
                $p = $parks[$k]
                break
            }
        }
    }

    $status = "CONNECTED_STATIC_OR_ALIAS"
    if ($null -eq $p) {
        $p = @{Canonical=""; ElevationFt=""; ParkRunFactor=""; Roof="unknown"; Orientation="unknown"; AliasOf=""}
        $status = "MISSING_STATIC_PARK_ALIAS"
        $missing += $venue
    }

    $out += ,[pscustomobject]@{
        Source = "ASTRODDS_STATIC_BALLPARK_FACTORS_WITH_ALIASES"
        Game = Get-Val $g @("Game")
        GamePk = Get-Val $g @("GamePk")
        Venue = $venue
        CanonicalVenue = $p.Canonical
        AliasOf = $p.AliasOf
        ElevationFt = $p.ElevationFt
        ParkRunFactor = $p.ParkRunFactor
        RoofType = $p.Roof
        FieldOrientation = $p.Orientation
        BallparkFactorStatus = $status
        ImpactNote = "More important for totals; moderate for moneyline context."
    }
}

$out | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$connected = @($out | Where-Object { $_.BallparkFactorStatus -eq "CONNECTED_STATIC_OR_ALIAS" }).Count
$missingCount = @($out | Where-Object { $_.BallparkFactorStatus -ne "CONNECTED_STATIC_OR_ALIAS" }).Count

$lines = @()
$lines += "ASTRODDS 304 BALLPARK ALIAS REPAIR"
$lines += ""
$lines += "Rows: $($out.Count)"
$lines += "Connected rows: $connected"
$lines += "Missing rows: $missingCount"
$lines += ""
foreach ($r in $out) {
    $lines += "- $($r.Game) | venue=$($r.Venue) | canonical=$($r.CanonicalVenue) | elevation=$($r.ElevationFt) | park=$($r.ParkRunFactor) | roof=$($r.RoofType) | $($r.BallparkFactorStatus)"
}
if ($missing.Count -gt 0) {
    $lines += ""
    $lines += "MISSING VENUES"
    foreach ($v in ($missing | Select-Object -Unique)) { $lines += "- $v" }
}

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    rows=$out.Count
    connectedRows=$connected
    missingRows=$missingCount
    outputCsv=$outCsv
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
