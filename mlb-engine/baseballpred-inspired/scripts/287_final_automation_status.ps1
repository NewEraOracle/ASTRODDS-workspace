$ErrorActionPreference = "Continue"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$outTxt = Join-Path $astro "ASTRODDS-287-final-automation-status-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-287-final-automation-status-latest.json"

Write-Host ""
Write-Host "ASTRODDS 287 FINAL AUTOMATION STATUS" -ForegroundColor Cyan
Write-Host ""


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

$credit = Safe-Csv (Join-Path $astro "ASTRODDS-odds-api-credit-ledger-latest.csv")
$candidates = Safe-Csv (Join-Path $astro "ASTRODDS-potential-candidate-board-latest.csv")
$market = Safe-Csv (Join-Path $astro "ASTRODDS-market-moneyline-source-latest.csv")

$monthKey = (Get-Date).ToString("yyyy-MM")
$monthRows = @($credit | Where-Object { (Get-Val $_ @("MonthKey")) -eq $monthKey })
$apiCalls = @($monthRows | Where-Object { (Get-Val $_ @("ApiCalled")) -eq "YES" }).Count
$estimatedCost = 0
foreach ($r in $monthRows) {
    $c = Num (Get-Val $r @("RequestsLast","EstimatedCost"))
    if ($null -ne $c) { $estimatedCost += [int][math]::Round($c,0) }
}

$externalRows = @($market | Where-Object { (Get-Val $_ @("Source")) -like "THE_ODDS_API*" }).Count
$candidateCount = @($candidates | Where-Object { (Get-Val $_ @("CandidateLevel")) -eq "ODDS_RESCAN_CANDIDATE" }).Count

$lines = @()
$lines += "ASTRODDS 287 FINAL AUTOMATION STATUS"
$lines += ""
$lines += "Automation status: INSTALLED"
$lines += "Month: $monthKey"
$lines += "Local Odds API calls logged this month: $apiCalls"
$lines += "Estimated credits used by automation ledger: $estimatedCost"
$lines += "External odds rows latest: $externalRows"
$lines += "Current odds-rescan candidates: $candidateCount"
$lines += ""
$lines += "COMMANDS"
$lines += "One safe scan:"
$lines += 'powershell -ExecutionPolicy Bypass -File ".\mlb-engine\baseballpred-inspired\scripts\283_credit_safe_pregame_rescan.ps1"'
$lines += ""
$lines += "Start server + loop:"
$lines += 'powershell -ExecutionPolicy Bypass -File ".\mlb-engine\baseballpred-inspired\scripts\285_start_server_and_autoscan.ps1"'
$lines += ""
$lines += "Credit ledger:"
$lines += (Join-Path $astro "ASTRODDS-odds-api-credit-ledger-latest.csv")

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    monthKey = $monthKey
    apiCallsThisMonth = $apiCalls
    estimatedCredits = $estimatedCost
    externalOddsRowsLatest = $externalRows
    oddsRescanCandidates = $candidateCount
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
