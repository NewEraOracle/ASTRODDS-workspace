$ErrorActionPreference = "Continue"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$ledgerCsv = Join-Path $astro "ASTRODDS-official-picks-ledger-latest.csv"
$contextCsv = Join-Path $astro "ASTRODDS-248-context-merged-confidence-latest.csv"
$outCsv = Join-Path $astro "ASTRODDS-confidence-calibration-policy-latest.csv"
$outJson = Join-Path $astro "ASTRODDS-confidence-calibration-policy-latest.json"
$outTxt = Join-Path $astro "ASTRODDS-276-confidence-calibration-policy-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 276 CALIBRATE CONFIDENCE FROM LEDGER" -ForegroundColor Cyan
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

$ledger = Safe-Csv $ledgerCsv
$context = Safe-Csv $contextCsv

function Find-Conf($game,$pick) {
    foreach ($r in $context) {
        if ((Get-Val $r @("Game")) -eq $game -and (Get-Val $r @("Pick")) -eq $pick) {
            return Get-Val $r @("Confidence")
        }
    }
    return ""
}

$bins = @(
    @{Name="90-100"; Min=90; Max=100; DefaultAdj=0},
    @{Name="80-89"; Min=80; Max=89.999; DefaultAdj=0},
    @{Name="70-79"; Min=70; Max=79.999; DefaultAdj=0},
    @{Name="60-69"; Min=60; Max=69.999; DefaultAdj=-2},
    @{Name="0-59"; Min=0; Max=59.999; DefaultAdj=-5}
)

$out = @()
foreach ($b in $bins) {
    $members = @()
    foreach ($r in $ledger) {
        $conf = Get-Val $r @("Confidence")
        if ($conf -eq "") { $conf = Find-Conf (Get-Val $r @("Game")) (Get-Val $r @("Pick")) }
        $c = Num $conf
        if ($null -eq $c) { continue }
        if ($c -ge $b.Min -and $c -le $b.Max) { $members += ,$r }
    }

    $settled = @($members | Where-Object { (Get-Val $_ @("Status")) -eq "SETTLED" })
    $wins = @($settled | Where-Object { (Get-Val $_ @("Result")) -eq "WIN" }).Count
    $losses = @($settled | Where-Object { (Get-Val $_ @("Result")) -eq "LOSS" }).Count
    $total = $settled.Count
    $wr = ""
    $adj = $b.DefaultAdj
    $status = "NOT_ENOUGH_SAMPLE"

    if ($total -ge 20) {
        $winRate = ($wins / [math]::Max(1,$total))
        $wr = ([math]::Round($winRate*100,1)).ToString() + "%"
        $status = "CALIBRATED"
        if ($winRate -lt 0.50) { $adj = -6 }
        elseif ($winRate -lt 0.54) { $adj = -3 }
        elseif ($winRate -gt 0.60) { $adj = 3 }
        elseif ($winRate -gt 0.56) { $adj = 1 }
    } elseif ($total -gt 0) {
        $wr = ([math]::Round(($wins/[math]::Max(1,$total))*100,1)).ToString() + "%"
    }

    $out += ,[pscustomobject]@{
        ConfidenceBin = $b.Name
        Picks = $members.Count
        Settled = $total
        Wins = $wins
        Losses = $losses
        WinRate = $wr
        ConfidenceAdjustment = $adj
        CalibrationStatus = $status
    }
}

$out | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    bins = @($out)
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

$lines = @()
$lines += "ASTRODDS 276 CALIBRATE CONFIDENCE FROM LEDGER"
$lines += ""
foreach ($r in $out) {
    $lines += "- $($r.ConfidenceBin) | settled=$($r.Settled) | W=$($r.Wins) L=$($r.Losses) | winRate=$($r.WinRate) | adj=$($r.ConfidenceAdjustment) | $($r.CalibrationStatus)"
}
$lines += ""
$lines += "Output: $outCsv"

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
exit 0
