$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$outTxt = Join-Path $astro "ASTRODDS-255-schedule-first-full-slate-bridge-latest.txt"
$outCsv = Join-Path $astro "ASTRODDS-255-schedule-first-full-slate-bridge-latest.csv"
$outJson = Join-Path $astro "ASTRODDS-255-schedule-first-full-slate-bridge-latest.json"

Write-Host ""
Write-Host "ASTRODDS 255 SCHEDULE-FIRST FULL SLATE BRIDGE" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - EXPLICITLY SCORE OR BLOCK EVERY GAME" -ForegroundColor Cyan
Write-Host ""


function Safe-Csv($path) {
    if (!(Test-Path $path)) { return @() }
    try { return @(Import-Csv $path) }
    catch { return @() }
}

function Read-JsonSafe($path) {
    if (!(Test-Path $path)) { return $null }
    try { return Get-Content $path -Raw | ConvertFrom-Json }
    catch { return $null }
}

function Get-Val($row, $names) {
    if ($null -eq $row) { return "" }
    foreach ($n in @($names)) {
        $p = $row.PSObject.Properties[$n]
        if ($null -ne $p -and $null -ne $p.Value -and "$($p.Value)".Trim() -ne "") {
            return "$($p.Value)".Trim()
        }
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

function Split-Game($game) {
    $awayTeamName = ""
    $homeTeamName = ""
    if ($game -match "\s@\s") {
        $parts = $game -split "\s@\s", 2
        $awayTeamName = "$($parts[0])".Trim()
        $homeTeamName = "$($parts[1])".Trim()
    } elseif ($game -match "\svs\s") {
        $parts = $game -split "\svs\s", 2
        $awayTeamName = "$($parts[0])".Trim()
        $homeTeamName = "$($parts[1])".Trim()
    }
    return [pscustomobject]@{
        Away = $awayTeamName
        Home = $homeTeamName
        AwayNorm = Normalize-Team $awayTeamName
        HomeNorm = Normalize-Team $homeTeamName
        Key = (Normalize-Team $awayTeamName) + " @ " + (Normalize-Team $homeTeamName)
    }
}

function Get-MlbSchedule($date) {
    $url = "https://statsapi.mlb.com/api/v1/schedule?sportId=1&date=$date&hydrate=probablePitcher"
    try { return Invoke-RestMethod -Uri $url -Method Get -TimeoutSec 15 }
    catch { return $null }
}

function Get-Game-Key($game) {
    return (Split-Game $game).Key
}

function Clean-KeyPart($s) {
    $x = "$s".ToLower().Trim()
    $x = $x -replace "\s+", " "
    return $x
}

$parityCsv = Join-Path $astro "ASTRODDS-253-baseballpred-parity-audit-latest.csv"
$hitsCsv = Join-Path $astro "ASTRODDS-254-missing-games-source-hunter-latest.csv"
$controlCsv = Join-Path $astro "ASTRODDS-schedule-first-full-slate-control-board-latest.csv"

$parity = Safe-Csv $parityCsv
$hits = Safe-Csv $hitsCsv
$control = Safe-Csv $controlCsv

$bridged = @()

foreach ($r in $parity) {
    $game = Get-Val $r @("Game")
    $ready = (Get-Val $r @("ParityStatus")) -eq "BASEBALLPRED_READY_ROW"
    $issues = Get-Val $r @("Issues")

    $bridgeHits = @($hits | Where-Object {
        (Get-Val $_ @("Game")) -eq $game -and
        (Get-Val $_ @("BridgeCandidate")) -eq "YES"
    })

    $finalDecision = "NO_BET_BLOCKED"
    $reason = "No safe model/market bridge found."

    if ($ready) {
        $finalDecision = "EVALUATED_READY"
        $reason = "Already has model, market, edge and lineup context."
    } elseif ($bridgeHits.Count -gt 0) {
        # Conservative: do not invent row values. Mark as SOURCE_FOUND_REVIEW until upstream model is patched.
        $finalDecision = "SOURCE_FOUND_REVIEW"
        $reason = "Model/market terms found in source files, but no safe structured bridge was applied automatically."
    } elseif ($issues -like "*lineups_not_confirmed*" -and $issues -notlike "*missing_model*" -and $issues -notlike "*NO_MODEL_YET*") {
        $finalDecision = "WAIT_FOR_LINEUPS"
        $reason = "Game has model/market but lineups are not confirmed."
    } elseif ($issues -like "*missing_model*" -or $issues -like "*NO_MODEL_YET*") {
        $finalDecision = "NO_MODEL_YET"
        $reason = "Upstream model/market generator did not score this game."
    }

    $bridged += ,[pscustomobject]@{
        Game = $game
        GamePk = Get-Val $r @("GamePk")
        MlbStatus = Get-Val $r @("MlbStatus")
        Pick = Get-Val $r @("Pick")
        ModelProbability = Get-Val $r @("ModelProbability")
        MarketProbability = Get-Val $r @("MarketProbability")
        Edge = Get-Val $r @("Edge")
        Lineups = Get-Val $r @("Lineups")
        FinalBridgeDecision = $finalDecision
        Reason = $reason
        CandidateSources = (($bridgeHits | Select-Object -ExpandProperty SourceFile -Unique) -join " | ")
    }
}

$bridged | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$readyCount = @($bridged | Where-Object { $_.FinalBridgeDecision -eq "EVALUATED_READY" }).Count
$reviewCount = @($bridged | Where-Object { $_.FinalBridgeDecision -eq "SOURCE_FOUND_REVIEW" }).Count
$noModelCount = @($bridged | Where-Object { $_.FinalBridgeDecision -eq "NO_MODEL_YET" }).Count
$waitCount = @($bridged | Where-Object { $_.FinalBridgeDecision -eq "WAIT_FOR_LINEUPS" }).Count
$blockedCount = @($bridged | Where-Object { $_.FinalBridgeDecision -eq "NO_BET_BLOCKED" }).Count

$lines = @()
$lines += "ASTRODDS 255 SCHEDULE-FIRST FULL SLATE BRIDGE"
$lines += ""
$lines += "Rows: $($bridged.Count)"
$lines += "Evaluated ready: $readyCount"
$lines += "Source found review: $reviewCount"
$lines += "NO_MODEL_YET: $noModelCount"
$lines += "WAIT_FOR_LINEUPS: $waitCount"
$lines += "Other blocked: $blockedCount"
$lines += ""
$lines += "FULL SLATE DECISION BOARD"
foreach ($b in $bridged) {
    $lines += "- $($b.FinalBridgeDecision) | $($b.Game) | Pick=$($b.Pick) | Model=$($b.ModelProbability) | Market=$($b.MarketProbability) | Edge=$($b.Edge)"
    $lines += "  Reason=$($b.Reason)"
    if ($b.CandidateSources -ne "") { $lines += "  CandidateSources=$($b.CandidateSources)" }
}
$lines += ""
$lines += "IMPORTANT"
$lines += "- This script does not fake probabilities."
$lines += "- If NO_MODEL_YET remains, the true fix is upstream model/market coverage for those games."
$lines += "- SOURCE_FOUND_REVIEW means source terms exist but need structured extraction before official use."

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    rows = $bridged.Count
    evaluatedReady = $readyCount
    sourceFoundReview = $reviewCount
    noModelYet = $noModelCount
    waitForLineups = $waitCount
    otherBlocked = $blockedCount
    outputCsv = $outCsv
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output CSV: $outCsv"
Write-Host "Output JSON: $outJson"
Write-Host ""
