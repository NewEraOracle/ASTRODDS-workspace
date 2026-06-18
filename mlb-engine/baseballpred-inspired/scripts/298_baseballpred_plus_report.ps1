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

$outTxt = Join-Path $astro "ASTRODDS-298-baseballpred-plus-report-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-298-baseballpred-plus-report-latest.json"

Write-Host ""
Write-Host "ASTRODDS 298 BASEBALLPRED++ REPORT" -ForegroundColor Cyan
Write-Host ""

$plus = Safe-Csv (Join-Path $astro "ASTRODDS-baseballpred-plus-context-latest.csv")
$ls = Safe-Csv (Join-Path $astro "ASTRODDS-289-best-price-line-shopping-latest.csv")
$clv = Safe-Csv (Join-Path $astro "ASTRODDS-closing-line-snapshots-latest.csv")
$ledger = Safe-Csv (Join-Path $astro "ASTRODDS-official-picks-ledger-latest.csv")
$park = Safe-Csv (Join-Path $astro "ASTRODDS-ballpark-advanced-factors-latest.csv")
$travel = Safe-Csv (Join-Path $astro "ASTRODDS-travel-rest-timezone-context-latest.csv")

$officialLineShop = @($ls | Where-Object { (Get-Val $_ @("LineShopDecision")) -eq "BEST_PRICE_OFFICIAL_CANDIDATE" }).Count
$reviewLineShop = @($ls | Where-Object { (Get-Val $_ @("LineShopDecision")) -eq "BEST_PRICE_REVIEW_CANDIDATE" }).Count
$settled = @($ledger | Where-Object { (Get-Val $_ @("Status")) -eq "SETTLED" }).Count
$pending = @($ledger | Where-Object { (Get-Val $_ @("Status")) -eq "PENDING_RESULT" }).Count
$plusConnected = @($plus | Where-Object { (Get-Val $_ @("PlusStatus")) -eq "BASEBALLPRED_PLUS_CONNECTED" }).Count

$lines = @()
$lines += "ASTRODDS 298 BASEBALLPRED++ REPORT"
$lines += ""
$lines += "SUMMARY"
$lines += "- BaseballPred++ context rows: $($plus.Count)"
$lines += "- Fully connected plus rows: $plusConnected"
$lines += "- Line shopping official candidates: $officialLineShop"
$lines += "- Line shopping review candidates: $reviewLineShop"
$lines += "- CLV snapshots: $($clv.Count)"
$lines += "- Ledger pending: $pending"
$lines += "- Ledger settled: $settled"
$lines += "- Ballpark factor rows: $($park.Count)"
$lines += "- Travel/rest rows: $($travel.Count)"
$lines += ""
$lines += "CONNECTED NOW"
$lines += "- Best price / line shopping"
$lines += "- CLV snapshots"
$lines += "- Enhanced settlement metrics"
$lines += "- Confidence calibration application"
$lines += "- Ballpark elevation / park factor baseline"
$lines += "- Travel/rest schedule density proxy"
$lines += "- Telegram auto-send safe dry-run/send gate"
$lines += ""
$lines += "STILL NOT PERFECT / PREMIUM LEVEL"
$lines += "- Umpire strike-zone source"
$lines += "- True roof open/closed live source"
$lines += "- Starter advanced metrics FIP/xFIP/K-BB/handedness"
$lines += "- Platoon splits L/R"
$lines += "- Bullpen leverage by inning/pitches, not just usage proxy"
$lines += "- Trained model promoted only after backtest and calibration sample"

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    plusRows=$plus.Count
    plusConnected=$plusConnected
    lineShoppingOfficialCandidates=$officialLineShop
    lineShoppingReviewCandidates=$reviewLineShop
    clvSnapshots=$clv.Count
    ledgerPending=$pending
    ledgerSettled=$settled
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
