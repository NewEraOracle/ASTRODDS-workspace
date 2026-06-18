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
    if ($g -match "\s@\s") {
        $parts = $g -split "\s@\s", 2
        return (Normalize-Team $parts[0]) + " @ " + (Normalize-Team $parts[1])
    }
    return (Normalize-Team $g)
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

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$gateCsv = Join-Path $astro "ASTRODDS-323-elite-official-gate-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-326-elite-gate-classification-audit-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-326-elite-gate-classification-audit-latest.json"

Write-Host ""
Write-Host "ASTRODDS 326 ELITE GATE CLASSIFICATION AUDIT" -ForegroundColor Cyan
Write-Host ""

$rows = Safe-Csv $gateCsv

$send = @($rows | Where-Object { (Get-Val $_ @("FinalEliteDecision")) -eq "CLIENT_OFFICIAL_ELITE_SEND_OK" }).Count
$review = @($rows | Where-Object { (Get-Val $_ @("FinalEliteDecision")) -eq "REVIEW_ONLY_ELITE" }).Count
$noValue = @($rows | Where-Object { (Get-Val $_ @("FinalEliteDecision")) -eq "BLOCKED_NO_VALUE" }).Count
$notLive = @($rows | Where-Object { (Get-Val $_ @("FinalEliteDecision")) -eq "BLOCKED_NOT_LIVE_SAFE" }).Count
$other = @($rows | Where-Object { (Get-Val $_ @("FinalEliteDecision")) -like "BLOCKED*" -and (Get-Val $_ @("FinalEliteDecision")) -ne "BLOCKED_NO_VALUE" -and (Get-Val $_ @("FinalEliteDecision")) -ne "BLOCKED_NOT_LIVE_SAFE" }).Count

$lines = @()
$lines += "ASTRODDS 326 ELITE GATE CLASSIFICATION AUDIT"
$lines += ""
$lines += "CLIENT_OFFICIAL_ELITE_SEND_OK: $send"
$lines += "REVIEW_ONLY_ELITE: $review"
$lines += "BLOCKED_NO_VALUE: $noValue"
$lines += "BLOCKED_NOT_LIVE_SAFE: $notLive"
$lines += "BLOCKED_OTHER: $other"
$lines += ""
$lines += "INTERPRETATION"
if ($send -eq 0 -and $review -eq 0 -and ($noValue + $notLive + $other) -gt 0) {
    $lines += "- Clean: no fake review noise. Current slate has no clean value or is not live-safe."
} elseif ($review -gt 0) {
    $lines += "- Review rows exist because edge/context is close but not official."
} elseif ($send -gt 0) {
    $lines += "- SEND_OK rows exist. Verify client message before sending."
}
$lines += ""
$lines += "ROWS"
foreach ($r in $rows) {
    $lines += "- $((Get-Val $r @('FinalEliteDecision'))) | $((Get-Val $r @('Pick'))) | $((Get-Val $r @('Game'))) | edge=$((Get-Val $r @('EdgeVsBest'))) | status=$((Get-Val $r @('MlbStatus')))"
}

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    sendOk=$send
    review=$review
    blockedNoValue=$noValue
    blockedNotLiveSafe=$notLive
    blockedOther=$other
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
