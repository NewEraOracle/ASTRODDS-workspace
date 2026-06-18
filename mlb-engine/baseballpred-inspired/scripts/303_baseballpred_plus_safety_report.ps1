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

$outTxt = Join-Path $astro "ASTRODDS-303-baseballpred-plus-safety-report-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-303-baseballpred-plus-safety-report-latest.json"

Write-Host ""
Write-Host "ASTRODDS 303 BASEBALLPRED++ SAFETY REPORT" -ForegroundColor Cyan
Write-Host ""

$line = Safe-Csv (Join-Path $astro "ASTRODDS-289-best-price-line-shopping-latest.csv")
$gate = Safe-Csv (Join-Path $astro "ASTRODDS-301-line-shopping-official-gate-latest.csv")
$plus = Safe-Csv (Join-Path $astro "ASTRODDS-baseballpred-plus-context-latest.csv")

$officialLine = @($line | Where-Object { (Get-Val $_ @("LineShopDecision")) -eq "BEST_PRICE_OFFICIAL_CANDIDATE" }).Count
$internalReview = @($line | Where-Object { (Get-Val $_ @("LineShopDecision")) -eq "INTERNAL_PRICE_REVIEW_ONLY" }).Count
$send = @($gate | Where-Object { (Get-Val $_ @("FinalDecision")) -eq "CLIENT_OFFICIAL_LINE_SHOP_SEND_OK" }).Count
$partialPlus = @($plus | Where-Object { (Get-Val $_ @("PlusStatus")) -ne "BASEBALLPRED_PLUS_CONNECTED" }).Count

$lines = @()
$lines += "ASTRODDS 303 BASEBALLPRED++ SAFETY REPORT"
$lines += ""
$lines += "Line shopping official candidates after safe external-only rule: $officialLine"
$lines += "Internal price review-only rows: $internalReview"
$lines += "Final line-shopping SEND_OK: $send"
$lines += "Partial plus-context rows: $partialPlus"
$lines += ""
$lines += "SAFETY FIXES APPLIED"
$lines += "- External book prices preferred over internal fallback."
$lines += "- Internal fallback cannot create client official line-shopping pick."
$lines += "- In Progress / Delayed / Suspended / Final cannot become new drops."
$lines += "- Empty park/elevation/roof/calibration fields now count as missing."
$lines += "- Line shopping official gate added."
$lines += ""
$lines += "NEXT"
$lines += "- If SEND_OK remains 0, that is not a bug; market has no clean value right now."
$lines += "- Wait for pregame windows and confirmed lineups."
$lines += "- Add umpire, pitcher advanced metrics, platoon splits for premium next level."

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    safeLineShoppingOfficialCandidates=$officialLine
    internalReviewOnlyRows=$internalReview
    lineShoppingSendOk=$send
    partialPlusRows=$partialPlus
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
