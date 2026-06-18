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

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$lineCsv = Join-Path $astro "ASTRODDS-289-best-price-line-shopping-latest.csv"
$outCsv = Join-Path $astro "ASTRODDS-301-line-shopping-official-gate-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-301-line-shopping-official-gate-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-301-line-shopping-official-gate-latest.json"

Write-Host ""
Write-Host "ASTRODDS 301 LINE SHOPPING OFFICIAL GATE" -ForegroundColor Cyan
Write-Host ""

$rows = Safe-Csv $lineCsv
$out = @()

foreach ($r in $rows) {
    $hard = @()
    $warn = @()
    $decision = "BLOCKED_FOR_REVIEW"

    $status = Get-Val $r @("MlbStatus")
    $edge = Num (Get-Val $r @("EdgeVsBest"))
    $mode = Get-Val $r @("MarketSourceMode")
    $lineups = Get-Val $r @("Lineups")

    if ($status -match "In Progress|Final|Game Over|Delayed|Suspended") { $hard += "game not eligible: $status" }
    if ($mode -ne "EXTERNAL_BOOKS") { $hard += "no external live book price" }
    if ($lineups -ne "confirmed/confirmed") { $hard += "lineups not fully confirmed" }
    if ($null -eq $edge) { $hard += "missing edge vs best" }
    elseif ($edge -lt 5) { $hard += "edge vs best below 5%" }

    if ($hard.Count -eq 0) { $decision = "CLIENT_OFFICIAL_LINE_SHOP_SEND_OK" }
    elseif ($null -ne $edge -and $edge -ge 3 -and $mode -eq "EXTERNAL_BOOKS") { $decision = "REVIEW_ONLY_LINE_SHOP" }

    $out += ,[pscustomobject]@{
        FinalDecision = $decision
        Pick = Get-Val $r @("Pick")
        Game = Get-Val $r @("Game")
        MlbStatus = $status
        ModelProbability = Get-Val $r @("ModelProbability")
        BestEntry = Get-Val $r @("BestEntry")
        BestBook = Get-Val $r @("BestBook")
        EdgeVsBest = Get-Val $r @("EdgeVsBest")
        EdgeVsAverage = Get-Val $r @("EdgeVsAverage")
        MarketSourceMode = $mode
        Lineups = $lineups
        HardBlocks = ($hard -join " | ")
        Warnings = ($warn -join " | ")
    }
}

$out | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$send = @($out | Where-Object { $_.FinalDecision -eq "CLIENT_OFFICIAL_LINE_SHOP_SEND_OK" }).Count
$review = @($out | Where-Object { $_.FinalDecision -eq "REVIEW_ONLY_LINE_SHOP" }).Count

$lines = @()
$lines += "ASTRODDS 301 LINE SHOPPING OFFICIAL GATE"
$lines += ""
$lines += "SEND_OK: $send"
$lines += "REVIEW: $review"
$lines += "Rows: $($out.Count)"
foreach ($r in $out) {
    $lines += "- $($r.FinalDecision) | $($r.Pick) | $($r.Game) | status=$($r.MlbStatus) | best=$($r.BestEntry) $($r.BestBook) | edge=$($r.EdgeVsBest)"
    if ($r.HardBlocks -ne "") { $lines += "  Hard=$($r.HardBlocks)" }
}

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    sendOk=$send
    review=$review
    rows=$out.Count
    outputCsv=$outCsv
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
