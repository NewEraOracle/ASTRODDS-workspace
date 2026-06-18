$ErrorActionPreference = "Continue"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$outTxt = Join-Path $astro "ASTRODDS-280-model-quality-upgrade-report-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-280-model-quality-upgrade-report-latest.json"

Write-Host ""
Write-Host "ASTRODDS 280 MODEL QUALITY UPGRADE REPORT" -ForegroundColor Cyan
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

$market = Safe-Csv (Join-Path $astro "ASTRODDS-market-moneyline-source-latest.csv")
$bullpen = Safe-Csv (Join-Path $astro "ASTRODDS-bullpen-fatigue-context-latest.csv")
$injury = Safe-Csv (Join-Path $astro "ASTRODDS-full-roster-injury-status-latest.csv")
$board = Safe-Csv (Join-Path $astro "ASTRODDS-source-first-context-board-latest.csv")
$cal = Safe-Csv (Join-Path $astro "ASTRODDS-confidence-calibration-policy-latest.csv")

$marketRows = $market.Count
$externalMarketRows = @($market | Where-Object { (Get-Val $_ @("Source")) -like "THE_ODDS_API*" }).Count
$bullpenRows = $bullpen.Count
$injuryRows = $injury.Count
$boardRows = $board.Count
$fullRows = @($board | Where-Object { (Get-Val $_ @("FullContextConnected")) -eq "YES" }).Count
$rowsWithMarket = @($board | Where-Object { (Num (Get-Val $_ @("MarketRowsFound"))) -gt 0 }).Count
$calibratedBins = @($cal | Where-Object { (Get-Val $_ @("CalibrationStatus")) -eq "CALIBRATED" }).Count

$status = "MODEL_QUALITY_UPGRADE_INSTALLED"
if ($marketRows -eq 0) { $status = "NEEDS_MARKET_SOURCE" }
elseif ($externalMarketRows -eq 0) { $status = "USING_INTERNAL_MARKET_ONLY" }

$lines = @()
$lines += "ASTRODDS 280 MODEL QUALITY UPGRADE REPORT"
$lines += ""
$lines += "Status: $status"
$lines += ""
$lines += "COUNTS"
$lines += "- Market rows: $marketRows"
$lines += "- External market rows: $externalMarketRows"
$lines += "- Rolling bullpen rows: $bullpenRows"
$lines += "- Full roster injury rows: $injuryRows"
$lines += "- Source board rows: $boardRows"
$lines += "- Full context rows: $fullRows"
$lines += "- Rows with market: $rowsWithMarket"
$lines += "- Calibrated confidence bins: $calibratedBins"
$lines += ""
$lines += "WHAT IS NOW CONNECTED"
$lines += "- Optional real market connector via ODDS_API_KEY"
$lines += "- Internal market fallback"
$lines += "- Rolling bullpen fatigue 3d/7d"
$lines += "- Full roster injury/IL proxy"
$lines += "- Confidence calibration policy from ledger"
$lines += "- Model policy artifact check"
$lines += "- Quality source board rebuild"
$lines += ""
$lines += "NEXT IF YOU WANT EVEN STRONGER"
$lines += "- Add ODDS_API_KEY for sportsbook moneyline coverage on all games"
$lines += "- Accumulate settled picks to calibrate confidence bins"
$lines += "- Integrate a trained model artifact only after backtest gate passes"

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    status = $status
    marketRows = $marketRows
    externalMarketRows = $externalMarketRows
    bullpenRows = $bullpenRows
    injuryRosterRows = $injuryRows
    sourceBoardRows = $boardRows
    fullContextRows = $fullRows
    rowsWithMarket = $rowsWithMarket
    calibratedBins = $calibratedBins
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
