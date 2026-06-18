$ErrorActionPreference = "Continue"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$scheduleCsv = Join-Path $astro "ASTRODDS-source-mlb-schedule-latest.csv"
$outCsv = Join-Path $astro "ASTRODDS-free-injury-context-gate-latest.csv"
$outJson = Join-Path $astro "ASTRODDS-source-mlb-transactions-latest.json"
$outTxt = Join-Path $astro "ASTRODDS-261-fetch-injury-transaction-sources-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 261 FETCH INJURY / TRANSACTION SOURCES FIXED" -ForegroundColor Cyan
Write-Host "Fixed reserved `$HOME bug." -ForegroundColor Cyan
Write-Host ""


function Ensure-Dir($path) {
    if (!(Test-Path $path)) { New-Item -ItemType Directory -Force -Path $path | Out-Null }
}

function Invoke-Json($url, $timeout = 20) {
    try { return Invoke-RestMethod -Uri $url -Method Get -TimeoutSec $timeout }
    catch { return $null }
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

$schedule = Safe-Csv $scheduleCsv
$end = Get-Date
$start = $end.AddDays(-7)

$startDate = $start.ToString("yyyy-MM-dd")
$endDate = $end.ToString("yyyy-MM-dd")

$url = "https://statsapi.mlb.com/api/v1/transactions?sportId=1&startDate=$startDate&endDate=$endDate"
$tx = Invoke-Json $url 25
Write-Json $tx $outJson

$rows = @()

foreach ($g in $schedule) {
    $game = Get-Val $g @("Game")
    $awayTeamName = Get-Val $g @("AwayTeam")
    $homeTeamName = Get-Val $g @("HomeTeam")

    $awayHits = @()
    $homeHits = @()

    if ($null -ne $tx -and $tx.transactions) {
        foreach ($t in @($tx.transactions)) {
            $team = ""
            $desc = ""
            $date = ""
            try { $team = "$($t.toTeam.name)" } catch {}
            if ($team -eq "") { try { $team = "$($t.fromTeam.name)" } catch {} }
            try { $desc = "$($t.description)" } catch {}
            try { $date = "$($t.date)" } catch {}

            if ($team -eq $awayTeamName -or $desc -like "*$awayTeamName*") { $awayHits += "$date $desc" }
            if ($team -eq $homeTeamName -or $desc -like "*$homeTeamName*") { $homeHits += "$date $desc" }
        }
    }

    $awayRisk = "none"
    $homeRisk = "none"
    if ($awayHits.Count -gt 0) { $awayRisk = "medium" }
    if ($homeHits.Count -gt 0) { $homeRisk = "medium" }

    $rows += ,[pscustomobject]@{
        Source = "MLB_STATSAPI_TRANSACTIONS"
        ScheduleDate = Get-Date -Format "yyyy-MM-dd"
        GamePk = Get-Val $g @("GamePk")
        Game = $game
        AwayTeam = $awayTeamName
        HomeTeam = $homeTeamName
        AwayInjuryRisk = $awayRisk
        HomeInjuryRisk = $homeRisk
        AwayInjuryDetail = (($awayHits | Select-Object -First 5) -join " || ")
        HomeInjuryDetail = (($homeHits | Select-Object -First 5) -join " || ")
        TransactionWindow = "$startDate to $endDate"
        SourceUrl = $url
        FetchedAt = (Get-Date).ToString("o")
    }
}

$rows | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$lines = @()
$lines += "ASTRODDS 261 FETCH INJURY / TRANSACTION SOURCES FIXED"
$lines += ""
$lines += "Schedule games checked: $($schedule.Count)"
$lines += "Rows written: $($rows.Count)"
$lines += "Output: $outCsv"

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
