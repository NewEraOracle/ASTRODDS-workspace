$ErrorActionPreference = "Continue"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$bridgeCsv = Join-Path $astro "ASTRODDS-266-source-model-market-bridge-latest.csv"
$outCsv = Join-Path $astro "ASTRODDS-267-source-first-official-gate-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-267-source-first-official-gate-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-267-source-first-official-gate-latest.json"

Write-Host ""
Write-Host "ASTRODDS 267 SOURCE-FIRST OFFICIAL GATE" -ForegroundColor Cyan
Write-Host "Final safe gate for source-first model rows." -ForegroundColor Cyan
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

function Find-By-Game($rows, $game) {
    $k = Game-Key $game
    foreach ($r in @($rows)) {
        $g = Get-Val $r @("Game","game")
        if ($g -eq "") { continue }
        if ((Game-Key $g) -eq $k) { return $r }
    }
    return $null
}

$rows = Safe-Csv $bridgeCsv
$out = @()

foreach ($r in @($rows)) {
    $hard = @()
    $warn = @()
    $decision = "BLOCKED_FOR_REVIEW"

    $status = (Get-Val $r @("MlbStatus")).ToLower()
    $edge = Num (Get-Val $r @("Edge"))
    $model = Num (Get-Val $r @("ModelProbability"))
    if ($null -ne $model -and $model -gt 1) { $model = $model / 100.0 }

    $lineupsOk = ((Get-Val $r @("AwayLineupStatus")) -eq "confirmed" -and (Get-Val $r @("HomeLineupStatus")) -eq "confirmed")
    $marketOk = ((Get-Val $r @("BridgeDecision")) -eq "MODEL_MARKET_CONNECTED")
    $contextOk = ((Get-Val $r @("FullContextConnected")) -eq "YES")
    $modelStatus = Get-Val $r @("ModelStatus")

    if (-not $marketOk) { $hard += "no safe market price connected" }
    if (-not $lineupsOk) { $hard += "lineups not fully confirmed" }
    if ($status -match "in progress|live|final|game over") { $hard += "game already started or final" }
    if ($null -eq $edge) { $hard += "missing edge" }
    elseif ($edge -lt 5) { $hard += "edge below 5% official threshold" }
    if ($null -eq $model) { $hard += "missing model probability" }
    elseif ($model -lt 0.55) { $hard += "model below 55% minimum" }
    if (-not $contextOk) { $warn += "partial context" }
    if ($modelStatus -ne "MODEL_READY_FULL_CONTEXT") { $warn += "baseline model review status" }

    if ($hard.Count -eq 0) {
        if ($edge -ge 10) { $decision = "CLIENT_OFFICIAL_STRONG_BUY" }
        else { $decision = "CLIENT_OFFICIAL_VALUE_BUY" }
    } elseif ($marketOk -and $null -ne $edge -and $edge -ge 3 -and $lineupsOk) {
        $decision = "REVIEW_ONLY"
    }

    $confidence = Num (Get-Val $r @("SourceFirstConfidence"))
    if ($null -eq $confidence) { $confidence = 60 }
    if ($edge -ge 10) { $confidence = [math]::Min(94, $confidence + 4) }
    elseif ($edge -ge 5) { $confidence = [math]::Min(88, $confidence + 2) }
    if (-not $contextOk) { $confidence -= 4 }
    if ($warn.Count -gt 0) { $confidence -= 2 }
    $confidence = Clamp $confidence 50 94

    $out += ,[pscustomobject]@{
        FinalDecision = $decision
        Pick = Get-Val $r @("Pick")
        Game = Get-Val $r @("Game")
        MlbStatus = Get-Val $r @("MlbStatus")
        Entry = Get-Val $r @("Entry")
        ModelProbability = Get-Val $r @("ModelProbability")
        MarketProbability = Get-Val $r @("MarketProbability")
        Edge = Get-Val $r @("Edge")
        Confidence = [int][math]::Round($confidence,0)
        AwayLineupStatus = Get-Val $r @("AwayLineupStatus")
        HomeLineupStatus = Get-Val $r @("HomeLineupStatus")
        FullContextConnected = Get-Val $r @("FullContextConnected")
        HardBlocks = ($hard -join " | ")
        Warnings = ($warn -join " | ")
        Reason = if ($hard.Count -eq 0) { "Passed source-first official gate." } else { "Blocked by source-first official gate." }
    }
}

$out | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$send = @($out | Where-Object { $_.FinalDecision -like "CLIENT_OFFICIAL*" }).Count
$review = @($out | Where-Object { $_.FinalDecision -eq "REVIEW_ONLY" }).Count
$blocked = @($out | Where-Object { $_.FinalDecision -eq "BLOCKED_FOR_REVIEW" }).Count

$lines = @()
$lines += "ASTRODDS 267 SOURCE-FIRST OFFICIAL GATE"
$lines += ""
$lines += "SEND_OK official rows: $send"
$lines += "Review rows: $review"
$lines += "Blocked rows: $blocked"
$lines += ""
$lines += "GATE BOARD"
foreach ($r in $out) {
    $lines += "- $($r.FinalDecision) | $($r.Pick) | $($r.Game) | Entry=$($r.Entry) | Confidence=$($r.Confidence)/100 | Edge=$($r.Edge) | Status=$($r.MlbStatus)"
    if ($r.HardBlocks -ne "") { $lines += "  Hard=$($r.HardBlocks)" }
    if ($r.Warnings -ne "") { $lines += "  Warn=$($r.Warnings)" }
}

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    officialRows = $send
    reviewRows = $review
    blockedRows = $blocked
    outputCsv = $outCsv
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
