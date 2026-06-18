$ErrorActionPreference = "Continue"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$outTxt = Join-Path $astro "ASTRODDS-264-source-health-check-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-264-source-health-check-latest.json"

Write-Host ""
Write-Host "ASTRODDS 264 SOURCE HEALTH CHECK" -ForegroundColor Cyan
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

$files = @(
    @{Name="MLB schedule"; Path=(Join-Path $astro "ASTRODDS-source-mlb-schedule-latest.csv")},
    @{Name="Live lineups"; Path=(Join-Path $astro "ASTRODDS-source-live-lineups-latest.csv")},
    @{Name="Pitchers"; Path=(Join-Path $astro "ASTRODDS-lineup-pitcher-live-context-latest.csv")},
    @{Name="Weather"; Path=(Join-Path $astro "ASTRODDS-weather-ballpark-context-latest.csv")},
    @{Name="Injury/transactions"; Path=(Join-Path $astro "ASTRODDS-free-injury-context-gate-latest.csv")},
    @{Name="Bullpen proxy"; Path=(Join-Path $astro "ASTRODDS-bpen-game-relief-stats-latest.csv")},
    @{Name="Source-first board"; Path=(Join-Path $astro "ASTRODDS-source-first-context-board-latest.csv")}
)

$checks = @()
foreach ($f in $files) {
    $exists = Test-Path $f.Path
    $rows = 0
    $last = ""
    if ($exists) {
        $rows = @(Safe-Csv $f.Path).Count
        $last = (Get-Item $f.Path).LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss")
    }

    $checks += ,[pscustomobject]@{
        Source = $f.Name
        Exists = $exists
        Rows = $rows
        LastWriteTime = $last
        Path = $f.Path
    }
}

$lines = @()
$lines += "ASTRODDS 264 SOURCE HEALTH CHECK"
$lines += ""
foreach ($c in $checks) {
    $lines += "- $($c.Source): exists=$($c.Exists) | rows=$($c.Rows) | last=$($c.LastWriteTime)"
}
$lines += ""
$bad = @($checks | Where-Object { $_.Exists -ne $true -or $_.Rows -eq 0 }).Count
if ($bad -gt 0) {
    $lines += "STATUS: SOURCE_HEALTH_PARTIAL"
    $lines += "Some source files are missing or empty."
} else {
    $lines += "STATUS: SOURCE_HEALTH_OK"
    $lines += "All primary source files exist and contain rows."
}

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    badSources = $bad
    checks = @($checks)
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
