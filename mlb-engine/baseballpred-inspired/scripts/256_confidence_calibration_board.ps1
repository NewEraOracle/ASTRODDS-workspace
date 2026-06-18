$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$ledgerCsv = Join-Path $astro "ASTRODDS-official-picks-ledger-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-256-confidence-calibration-board-latest.txt"
$outCsv = Join-Path $astro "ASTRODDS-256-confidence-calibration-board-latest.csv"
$outJson = Join-Path $astro "ASTRODDS-256-confidence-calibration-board-latest.json"

Write-Host ""
Write-Host "ASTRODDS 256 CONFIDENCE CALIBRATION BOARD" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - BIN CONFIDENCE VS RESULTS" -ForegroundColor Cyan
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

$rows = Safe-Csv $ledgerCsv

$bins = @(
    @{Name="90-100"; Min=90; Max=100},
    @{Name="80-89"; Min=80; Max=89.999},
    @{Name="70-79"; Min=70; Max=79.999},
    @{Name="60-69"; Min=60; Max=69.999},
    @{Name="0-59"; Min=0; Max=59.999}
)

# Try to infer confidence from source CSV if not on ledger
$contextCsv = Join-Path $astro "ASTRODDS-248-context-merged-confidence-latest.csv"
$contextRows = Safe-Csv $contextCsv

function Find-Confidence($game,$pick) {
    foreach ($r in $contextRows) {
        if ((Get-Val $r @("Game")) -eq $game -and (Get-Val $r @("Pick")) -eq $pick) {
            return Get-Val $r @("Confidence")
        }
    }
    return ""
}

$out = @()
foreach ($b in $bins) {
    $members = @()
    foreach ($r in $rows) {
        $confText = Get-Val $r @("Confidence")
        if ($confText -eq "") { $confText = Find-Confidence (Get-Val $r @("Game")) (Get-Val $r @("Pick")) }
        $conf = Num $confText
        if ($null -eq $conf) { continue }

        if ($conf -ge $b.Min -and $conf -le $b.Max) { $members += ,$r }
    }

    $settled = @($members | Where-Object { (Get-Val $_ @("Status")) -eq "SETTLED" })
    $wins = @($settled | Where-Object { (Get-Val $_ @("Result")) -eq "WIN" }).Count
    $losses = @($settled | Where-Object { (Get-Val $_ @("Result")) -eq "LOSS" }).Count
    $total = $settled.Count
    $winRate = ""
    if ($total -gt 0) { $winRate = ([math]::Round(($wins / $total) * 100.0, 1)).ToString() + "%" }

    $out += ,[pscustomobject]@{
        ConfidenceBin = $b.Name
        PicksInBin = $members.Count
        Settled = $total
        Wins = $wins
        Losses = $losses
        WinRate = $winRate
        CalibrationStatus = if ($total -lt 20) { "NOT_ENOUGH_SAMPLE" } else { "SAMPLE_OK" }
    }
}

$out | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$lines = @()
$lines += "ASTRODDS 256 CONFIDENCE CALIBRATION BOARD"
$lines += ""
$lines += "Ledger rows: $($rows.Count)"
$lines += ""
foreach ($r in $out) {
    $lines += "- $($r.ConfidenceBin) | picks=$($r.PicksInBin) | settled=$($r.Settled) | W=$($r.Wins) L=$($r.Losses) | winRate=$($r.WinRate) | $($r.CalibrationStatus)"
}
$lines += ""
$lines += "INTERPRETATION"
$lines += "- Confidence /100 is still an internal score until each bin has enough settled sample."
$lines += "- Use this board to calibrate confidence over time."

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    ledgerRows = $rows.Count
    bins = @($out)
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output CSV: $outCsv"
Write-Host "Output JSON: $outJson"
Write-Host ""
