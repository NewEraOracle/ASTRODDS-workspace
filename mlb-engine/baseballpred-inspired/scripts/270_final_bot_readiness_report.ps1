$ErrorActionPreference = "Continue"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$outTxt = Join-Path $astro "ASTRODDS-270-final-bot-readiness-report-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-270-final-bot-readiness-report-latest.json"

Write-Host ""
Write-Host "ASTRODDS 270 FINAL BOT READINESS REPORT" -ForegroundColor Cyan
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

$sourceBoard = Safe-Csv (Join-Path $astro "ASTRODDS-source-first-context-board-latest.csv")
$model = Safe-Csv (Join-Path $astro "ASTRODDS-265-source-first-baseline-model-latest.csv")
$bridge = Safe-Csv (Join-Path $astro "ASTRODDS-266-source-model-market-bridge-latest.csv")
$gate = Safe-Csv (Join-Path $astro "ASTRODDS-267-source-first-official-gate-latest.csv")
$healthTxt = Join-Path $astro "ASTRODDS-264-source-health-check-latest.txt"

$sourceRows = $sourceBoard.Count
$modelRows = $model.Count
$marketConnected = @($bridge | Where-Object { (Get-Val $_ @("BridgeDecision")) -eq "MODEL_MARKET_CONNECTED" }).Count
$noMarket = @($bridge | Where-Object { (Get-Val $_ @("BridgeDecision")) -ne "MODEL_MARKET_CONNECTED" }).Count
$official = @($gate | Where-Object { (Get-Val $_ @("FinalDecision")) -like "CLIENT_OFFICIAL*" }).Count
$review = @($gate | Where-Object { (Get-Val $_ @("FinalDecision")) -eq "REVIEW_ONLY" }).Count
$blocked = @($gate | Where-Object { (Get-Val $_ @("FinalDecision")) -eq "BLOCKED_FOR_REVIEW" }).Count
$fullContext = @($sourceBoard | Where-Object { (Get-Val $_ @("FullContextConnected")) -eq "YES" }).Count

$ready = "BOT_OPERATIONAL_SOURCE_CONNECTED"
if ($sourceRows -eq 0 -or $modelRows -eq 0) { $ready = "BOT_NOT_READY_SOURCES_EMPTY" }
elseif ($official -eq 0) { $ready = "BOT_READY_NO_CLIENT_DROP_NOW" }

$lines = @()
$lines += "ASTRODDS 270 FINAL BOT READINESS REPORT"
$lines += ""
$lines += "Readiness: $ready"
$lines += ""
$lines += "COUNTS"
$lines += "- Source-first board rows: $sourceRows"
$lines += "- Source-first model rows: $modelRows"
$lines += "- Full-context rows: $fullContext"
$lines += "- Model+market connected rows: $marketConnected"
$lines += "- No-market rows: $noMarket"
$lines += "- Official client rows: $official"
$lines += "- Review rows: $review"
$lines += "- Blocked rows: $blocked"
$lines += ""
$lines += "WHAT IS FINISHED"
$lines += "- Live source connectors"
$lines += "- Full context board"
$lines += "- Baseline source-first model for every source-board game"
$lines += "- Market bridge without fake prices"
$lines += "- Official gate"
$lines += "- Client Telegram output"
$lines += "- Late drop blocker"
$lines += "- Ledger/settlement from previous patch"
$lines += ""
$lines += "WHAT REMAINS FOR MODEL QUALITY"
$lines += "- Replace baseline model with trained calibrated model once enough result data exists"
$lines += "- Add true market source for every MLB game to reduce NO_MARKET rows"
$lines += "- Add rolling bullpen 3d/7d fatigue instead of pitchers-used proxy"
$lines += "- Add premium or stronger injury source if available"
$lines += "- Calibrate confidence bins with settled results"
$lines += ""
$lines += "FINAL COMMAND"
$lines += 'powershell -ExecutionPolicy Bypass -File ".\mlb-engine\baseballpred-inspired\scripts\269_run_final_source_first_bot.ps1"'

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    readiness = $ready
    sourceRows = $sourceRows
    modelRows = $modelRows
    fullContextRows = $fullContext
    modelMarketConnectedRows = $marketConnected
    noMarketRows = $noMarket
    officialClientRows = $official
    reviewRows = $review
    blockedRows = $blocked
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
