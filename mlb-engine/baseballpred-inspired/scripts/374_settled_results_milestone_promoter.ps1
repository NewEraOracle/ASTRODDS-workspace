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

function Normalize-Name($s) {
    $x = "$s".ToLower().Trim()
    $x = $x -replace "[^a-z0-9 ]", ""
    $x = $x -replace "\s+", " "
    return $x
}

function Read-JsonSafe($path) {
    if (!(Test-Path $path)) { return $null }
    try { return Get-Content $path -Raw | ConvertFrom-Json } catch { return $null }
}

function Run-Step($name, $path, [ref]$childLog) {
    $start = Get-Date
    Write-Host "Running $name..." -ForegroundColor Cyan

    if (!(Test-Path $path)) {
        Write-Host "MISSING: $path" -ForegroundColor Yellow
        return [pscustomobject]@{Name=$name;Status="MISSING";ExitCode="";DurationSec=0}
    }

    try {
        $output = & powershell -ExecutionPolicy Bypass -File $path 2>&1
        $exit = $LASTEXITCODE
        $dur = [math]::Round(((Get-Date)-$start).TotalSeconds,2)

        $childLog.Value += ""
        $childLog.Value += "============================================================"
        $childLog.Value += "STEP: $name"
        $childLog.Value += "PATH: $path"
        $childLog.Value += "EXIT: $exit"
        $childLog.Value += "DURATION: $dur sec"
        $childLog.Value += "============================================================"
        $childLog.Value += @($output | ForEach-Object { "$_" })

        if ($exit -eq 0 -or $null -eq $exit) {
            Write-Host "OK: $name ($dur sec)" -ForegroundColor Green
            return [pscustomobject]@{Name=$name;Status="OK";ExitCode="0";DurationSec=$dur}
        } else {
            Write-Host "ERROR: $name ($exit)" -ForegroundColor Red
            return [pscustomobject]@{Name=$name;Status="ERROR";ExitCode="$exit";DurationSec=$dur}
        }
    } catch {
        $dur = [math]::Round(((Get-Date)-$start).TotalSeconds,2)
        $childLog.Value += ""
        $childLog.Value += "ERROR STEP: $name"
        $childLog.Value += "$($_.Exception.Message)"
        return [pscustomobject]@{Name=$name;Status="ERROR";ExitCode="1";DurationSec=$dur}
    }
}

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$datasetJson = Join-Path $astro "ASTRODDS-350-training-dataset-from-settled-ledger-latest.json"
$milestoneJson = Join-Path $astro "ASTRODDS-356-performance-milestone-tracker-latest.json"
$outTxt = Join-Path $astro "ASTRODDS-374-settled-results-milestone-promoter-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-374-settled-results-milestone-promoter-latest.json"

Write-Host ""
Write-Host "ASTRODDS 374 SETTLED RESULTS MILESTONE PROMOTER" -ForegroundColor Cyan
Write-Host "Tracks 75/150 real settled rows. No synthetic results." -ForegroundColor Cyan
Write-Host ""

$d = Read-JsonSafe $datasetJson
$m = Read-JsonSafe $milestoneJson

$settled = 0
try { $settled = [int]$d.labeledSettledRows } catch {
    try { $settled = [int]$m.settledLabeledRows } catch {}
}

$mode = "SOURCE_FIRST_ONLY"
$action = "Keep source-first + line-shopping production gate."
if ($settled -ge 150) {
    $mode = "PRODUCTION_MODEL_PROMOTION_ELIGIBLE"
    $action = "Run production model backtest + calibration before promotion."
} elseif ($settled -ge 75) {
    $mode = "EXPERIMENTAL_MODEL_ELIGIBLE"
    $action = "Allow experimental model board, not auto-send production."
}

$lines = @()
$lines += "ASTRODDS 374 SETTLED RESULTS MILESTONE PROMOTER"
$lines += ""
$lines += "Settled labeled rows: $settled"
$lines += "Experimental threshold: 75"
$lines += "Production threshold: 150"
$lines += "Mode: $mode"
$lines += "Action: $action"
$lines += ""
$lines += "RULE"
$lines += "- Only real settled WIN/LOSS rows count."
$lines += "- No model is promoted just because features exist."

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    settledLabeledRows=$settled
    experimentalThreshold=75
    productionThreshold=150
    mode=$mode
    action=$action
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
