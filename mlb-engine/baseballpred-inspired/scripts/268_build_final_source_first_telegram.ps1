$ErrorActionPreference = "Continue"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$gateCsv = Join-Path $astro "ASTRODDS-267-source-first-official-gate-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-telegram-FINAL-source-first-client-latest.txt"
$outRunTxt = Join-Path $astro "ASTRODDS-268-build-final-source-first-telegram-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-268-build-final-source-first-telegram-latest.json"

Write-Host ""
Write-Host "ASTRODDS 268 BUILD FINAL SOURCE-FIRST TELEGRAM" -ForegroundColor Cyan
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

$rows = Safe-Csv $gateCsv
$official = @($rows | Where-Object { (Get-Val $_ @("FinalDecision")) -like "CLIENT_OFFICIAL*" } | Sort-Object Confidence -Descending)
$review = @($rows | Where-Object { (Get-Val $_ @("FinalDecision")) -eq "REVIEW_ONLY" })
$blocked = @($rows | Where-Object { (Get-Val $_ @("FinalDecision")) -eq "BLOCKED_FOR_REVIEW" })

$telegram = @()

if ($official.Count -gt 0) {
    $telegram += "🚀 ASTRODDS OFFICIAL PICKS"
    $telegram += "MLB MONEYLINE ONLY"
    $telegram += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
    $telegram += ""
    $telegram += "Rules:"
    $telegram += "• No parlays"
    $telegram += "• Source-connected model"
    $telegram += "• Lineups, model, market, weather, injuries, pitcher, bullpen checked"
    $telegram += "• New drops only before first pitch"
    $telegram += "• 5% bankroll max per pick"
    $telegram += ""

    $i = 1
    foreach ($r in $official) {
        $label = "VALUE BUY"
        if ((Get-Val $r @("FinalDecision")) -eq "CLIENT_OFFICIAL_STRONG_BUY") { $label = "STRONG BUY" }

        $stake = "2–3% bankroll recommended / 5% max"
        if ($label -eq "STRONG BUY") { $stake = "5% bankroll max" }

        $telegram += "✅ $label #$i"
        $telegram += "$(Get-Val $r @('Pick')) ML"
        $telegram += "Game: $(Get-Val $r @('Game'))"
        $telegram += "Entry: $(Get-Val $r @('Entry'))"
        $telegram += "Confidence: $(Get-Val $r @('Confidence'))/100"
        $telegram += "Stake: $stake"
        $telegram += "Status: $(Get-Val $r @('MlbStatus'))"
        $telegram += ""
        $i++
    }

    $telegram += "⚠️ Risk note:"
    $telegram += "Confidence is not a guaranteed win rate. It is ASTRODDS internal score based on model, market value, live lineups, source context and safety gates."
    $telegram += ""
    $telegram += "ASTRODDS"
} else {
    $telegram += "🚫 ASTRODDS NEW CLIENT DROP BLOCKED"
    $telegram += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
    $telegram += ""
    $telegram += "No new official picks passed the final source-first gate."
    $telegram += ""
    $sample = @($blocked | Select-Object -First 8)
    foreach ($r in $sample) {
        $telegram += "- $(Get-Val $r @('Pick')) | $(Get-Val $r @('Game')) | $(Get-Val $r @('MlbStatus'))"
        $hb = Get-Val $r @("HardBlocks")
        if ($hb -ne "") { $telegram += "  Reason: $hb" }
    }
}

($telegram -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

$lines = @()
$lines += "ASTRODDS 268 BUILD FINAL SOURCE-FIRST TELEGRAM"
$lines += ""
$lines += "Official client picks: $($official.Count)"
$lines += "Review rows: $($review.Count)"
$lines += "Blocked rows: $($blocked.Count)"
$lines += ""
$lines += "Telegram: $outTxt"
$lines += ""
$lines += "FINAL MESSAGE"
$lines += ($telegram -join [Environment]::NewLine)

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    officialClientPicks = $official.Count
    reviewRows = $review.Count
    blockedRows = $blocked.Count
    telegram = $outTxt
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outRunTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
