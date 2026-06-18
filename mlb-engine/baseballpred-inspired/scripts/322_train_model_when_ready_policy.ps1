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

$dataCsv = Join-Path $astro "ASTRODDS-model-training-dataset-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-322-train-model-when-ready-policy-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-322-train-model-when-ready-policy-latest.json"

Write-Host ""
Write-Host "ASTRODDS 322 TRAIN MODEL WHEN READY POLICY" -ForegroundColor Cyan
Write-Host "No fake trained model. Promotes only after settled sample is large enough." -ForegroundColor Cyan
Write-Host ""

$data = Safe-Csv $dataCsv
$labeled = @($data | Where-Object { (Get-Val $_ @("Label")) -ne "" })

$minTrain = 75
$minPromote = 150
$mode = "NO_TRAIN_NOT_ENOUGH_SETTLED_RESULTS"
$action = "Keep source-first + line-shopping production gate."

if ($labeled.Count -ge $minPromote) {
    $mode = "READY_FOR_TRAIN_AND_PROMOTION_BACKTEST_REQUIRED"
    $action = "Train model, backtest, compare Brier/logloss/ROI/CLV before production promotion."
} elseif ($labeled.Count -ge $minTrain) {
    $mode = "READY_FOR_EXPERIMENTAL_TRAINING_NOT_PRODUCTION"
    $action = "Train experimental model only; do not use for client official until promotion threshold."
}

$lines = @()
$lines += "ASTRODDS 322 TRAIN MODEL WHEN READY POLICY"
$lines += ""
$lines += "Labeled settled rows: $($labeled.Count)"
$lines += "Minimum for experimental training: $minTrain"
$lines += "Minimum for production promotion: $minPromote"
$lines += "Mode: $mode"
$lines += "Action: $action"
$lines += ""
$lines += "Why:"
$lines += "- A model trained on too few results will overfit."
$lines += "- ASTRODDS keeps production safe until enough real outcomes are logged."
$lines += "- BaseballPred++ features are now stored so future training has the right columns."

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    labeledSettledRows=$labeled.Count
    minTrain=$minTrain
    minPromote=$minPromote
    mode=$mode
    action=$action
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
