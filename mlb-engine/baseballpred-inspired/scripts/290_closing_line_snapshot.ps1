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

$ledgerCsv = Join-Path $astro "ASTRODDS-official-picks-ledger-latest.csv"
$marketCsv = Join-Path $astro "ASTRODDS-market-moneyline-source-latest.csv"
$outCsv = Join-Path $astro "ASTRODDS-closing-line-snapshots-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-290-closing-line-snapshot-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-290-closing-line-snapshot-latest.json"

Write-Host ""
Write-Host "ASTRODDS 290 CLOSING LINE SNAPSHOT / CLV TRACKER" -ForegroundColor Cyan
Write-Host "Snapshots current best/avg market for pending official picks." -ForegroundColor Cyan
Write-Host ""

$ledger = Safe-Csv $ledgerCsv
$market = Safe-Csv $marketCsv
$old = Safe-Csv $outCsv
$newRows = @()

foreach ($p in @($ledger | Where-Object { (Get-Val $_ @("Status")) -eq "PENDING_RESULT" })) {
    $game = Get-Val $p @("Game")
    $pick = Get-Val $p @("Pick")
    $entry = Num (Get-Val $p @("EntryPrice","Entry"))
    if ($null -ne $entry -and $entry -gt 1) { $entry = $entry / 100.0 }

    $rows = @($market | Where-Object {
        (Game-Key (Get-Val $_ @("Game"))) -eq (Game-Key $game) -and
        (Normalize-Team (Get-Val $_ @("Pick"))) -eq (Normalize-Team $pick)
    })

    $prices = @()
    foreach ($r in $rows) {
        $v = Num (Get-Val $r @("MarketProbability","Entry"))
        if ($null -ne $v) {
            if ($v -gt 1) { $v = $v / 100.0 }
            if ($v -gt 0 -and $v -lt 1) { $prices += $v }
        }
    }

    $best = ""
    $avg = ""
    $clvBest = ""
    $clvAvg = ""

    if ($prices.Count -gt 0) {
        $bestN = ($prices | Measure-Object -Minimum).Minimum
        $avgN = ($prices | Measure-Object -Average).Average
        $best = ([math]::Round($bestN*100,1)).ToString() + "¢"
        $avg = ([math]::Round($avgN*100,1)).ToString() + "¢"
        if ($null -ne $entry) {
            $clvBest = ([math]::Round(($bestN - $entry)*100,1)).ToString() + "¢"
            $clvAvg = ([math]::Round(($avgN - $entry)*100,1)).ToString() + "¢"
        }
    }

    $newRows += ,[pscustomobject]@{
        SnapshotAt = (Get-Date).ToString("o")
        LedgerKey = Get-Val $p @("LedgerKey")
        Pick = $pick
        Game = $game
        EntryPrice = Get-Val $p @("EntryPrice","Entry")
        CurrentBestPrice = $best
        CurrentAvgPrice = $avg
        CLVBest = $clvBest
        CLVAvg = $clvAvg
        MarketRows = $prices.Count
        Status = Get-Val $p @("Status")
    }
}

$all = @($old) + @($newRows)
$all | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$lines = @()
$lines += "ASTRODDS 290 CLOSING LINE SNAPSHOT / CLV TRACKER"
$lines += ""
$lines += "New snapshots: $($newRows.Count)"
$lines += "Total snapshots: $($all.Count)"
$lines += ""
foreach ($r in $newRows) {
    $lines += "- $($r.Pick) | $($r.Game) | Entry=$($r.EntryPrice) | Best=$($r.CurrentBestPrice) | Avg=$($r.CurrentAvgPrice) | CLVBest=$($r.CLVBest) | CLVAvg=$($r.CLVAvg)"
}

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    newSnapshots = $newRows.Count
    totalSnapshots = $all.Count
    outputCsv = $outCsv
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
