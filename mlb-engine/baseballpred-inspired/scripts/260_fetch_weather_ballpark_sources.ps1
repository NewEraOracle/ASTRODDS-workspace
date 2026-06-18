$ErrorActionPreference = "Continue"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$scheduleCsv = Join-Path $astro "ASTRODDS-source-mlb-schedule-latest.csv"
$outCsv = Join-Path $astro "ASTRODDS-weather-ballpark-context-latest.csv"
$outJson = Join-Path $astro "ASTRODDS-weather-ballpark-context-latest.json"
$outTxt = Join-Path $astro "ASTRODDS-260-fetch-weather-ballpark-sources-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 260 FETCH WEATHER BALLPARK SOURCES" -ForegroundColor Cyan
Write-Host "Source: Open-Meteo forecast API" -ForegroundColor Cyan
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

# Ballpark coordinates: approximate center of venue.
$ballparks = @{
    "Nationals Park" = @{Lat=38.8730; Lon=-77.0074}
    "Citizens Bank Park" = @{Lat=39.9061; Lon=-75.1665}
    "American Family Field" = @{Lat=43.0280; Lon=-87.9712}
    "Great American Ball Park" = @{Lat=39.0974; Lon=-84.5066}
    "Truist Park" = @{Lat=33.8908; Lon=-84.4678}
    "Busch Stadium" = @{Lat=38.6226; Lon=-90.1928}
    "Dodger Stadium" = @{Lat=34.0739; Lon=-118.2400}
    "Yankee Stadium" = @{Lat=40.8296; Lon=-73.9262}
    "T-Mobile Park" = @{Lat=47.5914; Lon=-122.3325}
    "Chase Field" = @{Lat=33.4455; Lon=-112.0667}
    "Fenway Park" = @{Lat=42.3467; Lon=-71.0972}
    "Wrigley Field" = @{Lat=41.9484; Lon=-87.6553}
    "Sutter Health Park" = @{Lat=38.5804; Lon=-121.5133}
    "Minute Maid Park" = @{Lat=29.7573; Lon=-95.3555}
    "Rogers Centre" = @{Lat=43.6414; Lon=-79.3894}
}

$schedule = Safe-Csv $scheduleCsv
$date = Get-Date -Format "yyyy-MM-dd"

$rows = @()
$raw = @()

foreach ($g in $schedule) {
    $venue = Get-Val $g @("Venue")
    $coords = $null
    if ($ballparks.ContainsKey($venue)) { $coords = $ballparks[$venue] }

    if ($null -eq $coords) {
        $rows += ,[pscustomobject]@{
            Source = "OPEN_METEO"
            ScheduleDate = $date
            GamePk = Get-Val $g @("GamePk")
            Game = Get-Val $g @("Game")
            Venue = $venue
            WeatherStatus = "NO_COORDS_FOR_BALLPARK"
            TemperatureF = ""
            WindMph = ""
            PrecipitationMm = ""
            RainRisk = ""
            WeatherRisk = "unknown"
            SourceUrl = ""
            FetchedAt = (Get-Date).ToString("o")
        }
        continue
    }

    $lat = $coords.Lat
    $lon = $coords.Lon
    $url = "https://api.open-meteo.com/v1/forecast?latitude=$lat&longitude=$lon&hourly=temperature_2m,precipitation,wind_speed_10m,wind_gusts_10m&temperature_unit=fahrenheit&wind_speed_unit=mph&precipitation_unit=mm&forecast_days=1&timezone=auto"

    $w = Invoke-Json $url 20
    $raw += ,[pscustomobject]@{ Game=(Get-Val $g @("Game")); Venue=$venue; Url=$url; Response=$w }

    $temp = ""
    $wind = ""
    $gust = ""
    $precip = ""

    try {
        $temp = "$($w.hourly.temperature_2m[0])"
        $wind = "$($w.hourly.wind_speed_10m[0])"
        $gust = "$($w.hourly.wind_gusts_10m[0])"
        $precip = "$($w.hourly.precipitation[0])"
    } catch {}

    $risk = "low"
    $rainRisk = "low"
    $windN = 0.0
    $precipN = 0.0
    [void][double]::TryParse("$wind", [ref]$windN)
    [void][double]::TryParse("$precip", [ref]$precipN)

    if ($precipN -gt 0.5) { $rainRisk = "medium"; $risk = "medium" }
    if ($precipN -gt 2.0) { $rainRisk = "high"; $risk = "high" }
    if ($windN -ge 15) { if ($risk -eq "low") { $risk = "medium" } }
    if ($windN -ge 25) { $risk = "high" }

    $rows += ,[pscustomobject]@{
        Source = "OPEN_METEO_FORECAST"
        ScheduleDate = $date
        GamePk = Get-Val $g @("GamePk")
        Game = Get-Val $g @("Game")
        Venue = $venue
        WeatherStatus = "CONNECTED"
        TemperatureF = $temp
        WindMph = $wind
        WindGustMph = $gust
        PrecipitationMm = $precip
        RainRisk = $rainRisk
        WeatherRisk = $risk
        SourceUrl = $url
        FetchedAt = (Get-Date).ToString("o")
    }
}

$rows | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv
Write-Json $raw $outJson

$lines = @()
$lines += "ASTRODDS 260 FETCH WEATHER BALLPARK SOURCES"
$lines += ""
$lines += "Games checked: $($schedule.Count)"
$lines += "Weather rows written: $($rows.Count)"
$lines += "Connected rows: $(@($rows | Where-Object { $_.WeatherStatus -eq 'CONNECTED' }).Count)"
$lines += "No-coordinate rows: $(@($rows | Where-Object { $_.WeatherStatus -ne 'CONNECTED' }).Count)"
$lines += ""
$lines += "Output: $outCsv"

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
