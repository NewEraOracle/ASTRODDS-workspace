$ErrorActionPreference = "Continue"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
$engine = Join-Path $root "mlb-engine"
Ensure-Dir $astro

$outTxt = Join-Path $astro "ASTRODDS-277-train-or-refresh-model-policy-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-277-train-or-refresh-model-policy-latest.json"
$outPolicy = Join-Path $astro "ASTRODDS-model-quality-policy-latest.json"

Write-Host ""
Write-Host "ASTRODDS 277 TRAIN OR REFRESH MODEL POLICY" -ForegroundColor Cyan
Write-Host "Does not fake training. Uses trained artifacts if they exist, otherwise keeps baseline policy." -ForegroundColor Cyan
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

$trainingFiles = @()
try {
    $trainingFiles = Get-ChildItem -Path $engine -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -match "training_report|calibration|backtest|model\.pkl|feature_columns|moneyline" -and
            $_.Length -lt 10000000
        } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 40
} catch {}

$hasModel = @($trainingFiles | Where-Object { $_.Name -match "model\.pkl|moneyline.*\.pkl" }).Count -gt 0
$hasBacktest = @($trainingFiles | Where-Object { $_.Name -match "backtest|training_report|calibration" }).Count -gt 0

$modelMode = "SOURCE_FIRST_BASELINE"
if ($hasModel -and $hasBacktest) { $modelMode = "TRAINED_ARTIFACTS_AVAILABLE_REVIEW" }

$policy = [pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    modelMode = $modelMode
    hasModelArtifact = $hasModel
    hasBacktestOrCalibration = $hasBacktest
    productionUse = if ($modelMode -eq "TRAINED_ARTIFACTS_AVAILABLE_REVIEW") { "Use trained model only after integration test and calibration gate." } else { "Use conservative source-first baseline until enough settled results/training data exist." }
    minSettledPicksBeforeCalibration = 50
    minSettledPicksBeforeTrustingConfidenceBins = 20
    rules = @(
        "No trained model promotion without backtest file",
        "No official pick without market price",
        "No official pick after game start",
        "No fake probability or fake market",
        "Baseline model is review/coverage unless market gate passes"
    )
    artifactCandidates = @($trainingFiles | ForEach-Object { $_.FullName })
}

Write-Json $policy $outPolicy
Write-Json $policy $outJson

$lines = @()
$lines += "ASTRODDS 277 TRAIN OR REFRESH MODEL POLICY"
$lines += ""
$lines += "Model artifacts found: $hasModel"
$lines += "Backtest/calibration files found: $hasBacktest"
$lines += "Model mode: $modelMode"
$lines += ""
$lines += "ARTIFACT CANDIDATES"
foreach ($f in $trainingFiles) {
    $lines += "- $($f.FullName)"
}
$lines += ""
$lines += "POLICY"
$lines += "- No trained model promotion without integration/backtest gate."
$lines += "- Baseline source-first model remains conservative."
$lines += "- Official picks still require market, lineups, edge, pregame status and price guard."
$lines += ""
$lines += "Output policy: $outPolicy"

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
exit 0
