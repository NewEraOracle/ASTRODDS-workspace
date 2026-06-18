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
$scheduleCsv = Join-Path $astro "ASTRODDS-source-mlb-schedule-latest.csv"
$clvCsv = Join-Path $astro "ASTRODDS-closing-line-snapshots-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-291-enhanced-settlement-roi-clv-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-291-enhanced-settlement-roi-clv-latest.json"

Write-Host ""
Write-Host "ASTRODDS 291 ENHANCED SETTLEMENT ROI / CLV / BRIER / LOGLOSS" -ForegroundColor Cyan
Write-Host ""

$ledger = Safe-Csv $ledgerCsv
$schedule = Safe-Csv $scheduleCsv
$clv = Safe-Csv $clvCsv

$out = @()
$settledNow = 0

foreach ($p in @($ledger)) {
    $row = $p.PSObject.Copy()
    $status = Get-Val $row @("Status")
    $game = Get-Val $row @("Game")
    $pick = Get-Val $row @("Pick")
    $sched = Find-By-Game $schedule $game

    $mlbStatus = ""
    if ($null -ne $sched) { $mlbStatus = Get-Val $sched @("MlbStatus") }

    if ($status -eq "PENDING_RESULT" -and $mlbStatus -match "Final|Game Over") {
        $awayTeamName = Get-Val $sched @("AwayTeam")
        $homeTeamName = Get-Val $sched @("HomeTeam")
        $awayScore = Num (Get-Val $sched @("AwayScore"))
        $homeScore = Num (Get-Val $sched @("HomeScore"))

        if ($null -ne $awayScore -and $null -ne $homeScore) {
            $winner = if ($awayScore -gt $homeScore) { $awayTeamName } else { $homeTeamName }
            $result = if ((Normalize-Team $winner) -eq (Normalize-Team $pick)) { "WIN" } else { "LOSS" }

            $entry = Num (Get-Val $row @("EntryPrice","Entry"))
            if ($null -ne $entry -and $entry -gt 1) { $entry = $entry / 100.0 }

            $roi = ""
            if ($null -ne $entry -and $entry -gt 0 -and $entry -lt 1) {
                if ($result -eq "WIN") { $roi = ([math]::Round(((1.0 / $entry) - 1.0) * 100.0, 1)).ToString() + "%" }
                else { $roi = "-100%" }
            }

            $model = Num (Get-Val $row @("PublicModel","FullSlateModel","ModelProbability","Model"))
            if ($null -ne $model -and $model -gt 1) { $model = $model / 100.0 }
            $outcome = if ($result -eq "WIN") { 1.0 } else { 0.0 }
            $brier = ""
            $logloss = ""

            if ($null -ne $model -and $model -gt 0 -and $model -lt 1) {
                $b = [math]::Pow(($model - $outcome), 2)
                $brier = [math]::Round($b, 6)
                $pSafe = Clamp $model 0.001 0.999
                if ($outcome -eq 1.0) { $ll = -[math]::Log($pSafe) }
                else { $ll = -[math]::Log(1.0 - $pSafe) }
                $logloss = [math]::Round($ll, 6)
            }

            $latestClv = @($clv | Where-Object { (Get-Val $_ @("LedgerKey")) -eq (Get-Val $row @("LedgerKey")) } | Sort-Object SnapshotAt -Descending | Select-Object -First 1)
            $closingPrice = ""
            $clvAvg = ""
            if ($latestClv.Count -gt 0) {
                $closingPrice = Get-Val $latestClv[0] @("CurrentAvgPrice")
                $clvAvg = Get-Val $latestClv[0] @("CLVAvg")
            }

            $row.Status = "SETTLED"
            $row.Result = $result
            $row.Winner = $winner
            $row.FinalScore = "$awayTeamName $awayScore - $homeTeamName $homeScore"
            $row.ClosingPrice = $closingPrice
            $row.CLV = $clvAvg
            $row.ROI = $roi
            $row.BrierComponent = "$brier"
            $row.LogLossComponent = "$logloss"
            $settledNow++
        }
    }

    $out += ,$row
}

$out | Export-Csv -NoTypeInformation -Encoding UTF8 $ledgerCsv

$lines = @()
$lines += "ASTRODDS 291 ENHANCED SETTLEMENT ROI / CLV / BRIER / LOGLOSS"
$lines += ""
$lines += "Settled now: $settledNow"
$lines += "Ledger rows: $($out.Count)"
$lines += ""
foreach ($r in ($out | Where-Object { (Get-Val $_ @("Status")) -eq "SETTLED" } | Select-Object -Last 10)) {
    $lines += "- $($r.Result) | $($r.Pick) | $($r.Game) | Winner=$($r.Winner) | ROI=$($r.ROI) | CLV=$($r.CLV) | Brier=$($r.BrierComponent) | LogLoss=$($r.LogLossComponent)"
}

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    settledNow = $settledNow
    ledgerRows = $out.Count
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
