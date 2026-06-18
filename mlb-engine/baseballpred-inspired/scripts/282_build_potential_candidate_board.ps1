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
    foreach ($x in $arr) {
        $n = Num $x
        if ($null -ne $n) {
            if ($n -gt 1) { $n = $n / 100.0 }
            if ($n -gt 0 -and $n -lt 1) { $vals += $n }
        }
    }
    if ($vals.Count -eq 0) { return $null }
    return (($vals | Measure-Object -Average).Average)
}

function Fatigue-Penalty($v) {
    $x = "$v".ToLower()
    if ($x -match "high") { return 2.5 }
    if ($x -match "medium") { return 1.2 }
    return 0.0
}

function Injury-Penalty($v) {
    $x = "$v".ToLower()
    if ($x -match "high") { return 3.0 }
    if ($x -match "medium") { return 1.5 }
    if ($x -match "low") { return 0.5 }
    return 0.0
}


$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$outCsv = Join-Path $astro "ASTRODDS-potential-candidate-board-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-282-potential-candidate-board-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-282-potential-candidate-board-latest.json"

Write-Host ""
Write-Host "ASTRODDS 282G POTENTIAL CANDIDATE BOARD" -ForegroundColor Cyan
Write-Host "Uses varied 265G probabilities/edge. Does not call Odds API." -ForegroundColor Cyan
Write-Host ""

$sourceBoard = Safe-Csv (Join-Path $astro "ASTRODDS-source-first-context-board-latest.csv")
$baseline = Safe-Csv (Join-Path $astro "ASTRODDS-265-source-first-baseline-model-latest.csv")
$market = Safe-Csv (Join-Path $astro "ASTRODDS-market-moneyline-source-latest.csv")

$out = @()

foreach ($g in @($sourceBoard)) {
    $game = Get-Val $g @("Game")
    if ($game -eq "") { continue }

    $b = Find-By-Game $baseline $game
    $marketRows = @($market | Where-Object { (Game-Key (Get-Val $_ @("Game"))) -eq (Game-Key $game) })

    $status = Get-Val $g @("MlbStatus")
    $awayLineup = Get-Val $g @("AwayLineupStatus")
    $homeLineup = Get-Val $g @("HomeLineupStatus")
    $lineups = "$awayLineup/$homeLineup"
    $full = Get-Val $g @("FullContextConnected")
    $missing = Get-Val $g @("MissingContext")

    $candidateScore = 0
    $reasons = @()

    if ($status -match "Pre-Game|Warmup|Scheduled") { $candidateScore += 12; $reasons += "pregame_or_scheduled" }
    elseif ($status -match "In Progress|Final|Game Over") { $candidateScore -= 50; $reasons += "already_started_or_final" }

    if ($lineups -eq "confirmed/confirmed") { $candidateScore += 18; $reasons += "lineups_confirmed" }
    elseif ($lineups -match "confirmed") { $candidateScore += 6; $reasons += "partial_lineup" }

    if ($full -eq "YES") { $candidateScore += 15; $reasons += "full_context" }
    if ($marketRows.Count -gt 0) { $candidateScore += 12; $reasons += "cached_market_available" }

    $modelProb = ""
    $edge = ""
    $conf = ""
    $pick = ""
    $awayModel = ""
    $homeModel = ""

    if ($null -ne $b) {
        $pick = Get-Val $b @("Pick")
        $modelProb = Get-Val $b @("ModelProbability")
        $edge = Get-Val $b @("Edge")
        $conf = Get-Val $b @("SourceFirstConfidence")
        $awayModel = Get-Val $b @("AwayModelProbability")
        $homeModel = Get-Val $b @("HomeModelProbability")

        $m = Num $modelProb
        $e = Num $edge

        if ($null -ne $m -and $m -ge 60) { $candidateScore += 15; $reasons += "model_60_plus" }
        elseif ($null -ne $m -and $m -ge 57) { $candidateScore += 10; $reasons += "model_57_plus" }
        elseif ($null -ne $m -and $m -ge 55) { $candidateScore += 5; $reasons += "model_55_plus" }

        if ($null -ne $e -and $e -ge 7) { $candidateScore += 18; $reasons += "edge_7_plus" }
        elseif ($null -ne $e -and $e -ge 5) { $candidateScore += 12; $reasons += "edge_5_plus" }
        elseif ($null -ne $e -and $e -ge 3) { $candidateScore += 5; $reasons += "edge_3_plus" }
    }

    $level = "NO_SCAN"
    if ($candidateScore -ge 60) { $level = "ODDS_RESCAN_CANDIDATE" }
    elseif ($candidateScore -ge 38) { $level = "WATCHLIST_FREE_SOURCES_ONLY" }

    $out += ,[pscustomobject]@{
        CandidateLevel = $level
        CandidateScore = $candidateScore
        Pick = $pick
        Game = $game
        MlbStatus = $status
        ModelProbability = $modelProb
        Edge = $edge
        Confidence = $conf
        AwayModelProbability = $awayModel
        HomeModelProbability = $homeModel
        Lineups = $lineups
        FullContextConnected = $full
        MissingContext = $missing
        MarketRowsFound = $marketRows.Count
        Reasons = ($reasons -join "|")
    }
}

$out | Sort-Object CandidateScore -Descending | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$oddsCandidates = @($out | Where-Object { $_.CandidateLevel -eq "ODDS_RESCAN_CANDIDATE" }).Count
$watch = @($out | Where-Object { $_.CandidateLevel -eq "WATCHLIST_FREE_SOURCES_ONLY" }).Count

$lines = @()
$lines += "ASTRODDS 282G POTENTIAL CANDIDATE BOARD"
$lines += ""
$lines += "Rows: $($out.Count)"
$lines += "Odds rescan candidates: $oddsCandidates"
$lines += "Watchlist free-only: $watch"
$lines += ""
$lines += "BOARD"
foreach ($r in ($out | Sort-Object CandidateScore -Descending | Select-Object -First 15)) {
    $lines += "- $($r.CandidateLevel) | score=$($r.CandidateScore) | $($r.Pick) | $($r.Game) | status=$($r.MlbStatus) | model=$($r.ModelProbability) | edge=$($r.Edge) | lineups=$($r.Lineups)"
    $lines += "  Reasons=$($r.Reasons)"
}

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    rows = $out.Count
    oddsRescanCandidates = $oddsCandidates
    watchlist = $watch
    outputCsv = $outCsv
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
exit 0
