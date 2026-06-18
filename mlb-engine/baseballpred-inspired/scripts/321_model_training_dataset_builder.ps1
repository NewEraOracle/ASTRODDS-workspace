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

function Find-By-Team($rows, $team) {
    $k = Normalize-Team $team
    foreach ($r in @($rows)) {
        $t = Get-Val $r @("Team","team","Name","name")
        if ((Normalize-Team $t) -eq $k) { return $r }
    }
    return $null
}

function Clamp($x, $lo, $hi) {
    if ($x -lt $lo) { return $lo }
    if ($x -gt $hi) { return $hi }
    return $x
}

function Ip-To-Decimal($ipText) {
    $s = "$ipText".Trim()
    if ($s -eq "") { return $null }
    $parts = $s -split "\."
    $whole = 0
    $frac = 0
    try { $whole = [int]$parts[0] } catch { return $null }
    if ($parts.Count -gt 1) {
        try { $outs = [int]$parts[1]; $frac = $outs / 3.0 } catch { $frac = 0 }
    }
    return ($whole + $frac)
}

function Invoke-Json($url, $timeout = 25) {
    try { return Invoke-RestMethod -Uri $url -Method Get -TimeoutSec $timeout }
    catch { return $null }
}

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$ledgerCsv = Join-Path $astro "ASTRODDS-official-picks-ledger-latest.csv"
$eliteCsv = Join-Path $astro "ASTRODDS-elite-factor-context-latest.csv"
$outCsv = Join-Path $astro "ASTRODDS-model-training-dataset-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-321-model-training-dataset-builder-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-321-model-training-dataset-builder-latest.json"

Write-Host ""
Write-Host "ASTRODDS 321 MODEL TRAINING DATASET BUILDER" -ForegroundColor Cyan
Write-Host ""

$ledger = Safe-Csv $ledgerCsv
$elite = Safe-Csv $eliteCsv
$out = @()

foreach ($r in $ledger) {
    $status = Get-Val $r @("Status")
    $game = Get-Val $r @("Game")
    $pick = Get-Val $r @("Pick")
    $e = Find-By-Game $elite $game

    $label = ""
    if ((Get-Val $r @("Result")) -eq "WIN") { $label = 1 }
    elseif ((Get-Val $r @("Result")) -eq "LOSS") { $label = 0 }

    $out += ,[pscustomobject]@{
        Label = $label
        Status = $status
        Pick = $pick
        Game = $game
        EntryPrice = Get-Val $r @("EntryPrice","Entry")
        ModelProbability = Get-Val $r @("PublicModel","FullSlateModel","ModelProbability")
        Edge = Get-Val $r @("Edge")
        CLV = Get-Val $r @("CLV")
        ROI = Get-Val $r @("ROI")
        Brier = Get-Val $r @("BrierComponent")
        LogLoss = Get-Val $r @("LogLossComponent")
        AwayFIPProxy = Get-Val $e @("AwayFIPProxy")
        HomeFIPProxy = Get-Val $e @("HomeFIPProxy")
        AwayKMinusBBPctProxy = Get-Val $e @("AwayKMinusBBPctProxy")
        HomeKMinusBBPctProxy = Get-Val $e @("HomeKMinusBBPctProxy")
        AwayReliefStressLevel = Get-Val $e @("AwayReliefStressLevel")
        HomeReliefStressLevel = Get-Val $e @("HomeReliefStressLevel")
        EliteContextStatus = Get-Val $e @("EliteContextStatus")
    }
}

$out | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$settled = @($out | Where-Object { "$($_.Label)" -ne "" }).Count

$lines = @()
$lines += "ASTRODDS 321 MODEL TRAINING DATASET BUILDER"
$lines += ""
$lines += "Rows: $($out.Count)"
$lines += "Settled labeled rows: $settled"
$lines += "Output: $outCsv"
$lines += ""
$lines += "Training policy: do not train/promote model until enough settled labeled rows exist."

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    rows=$out.Count
    settledLabeledRows=$settled
    outputCsv=$outCsv
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
