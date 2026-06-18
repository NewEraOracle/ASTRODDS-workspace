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

function Invoke-Json($url, $timeout = 30) {
    try { return Invoke-RestMethod -Uri $url -Method Get -TimeoutSec $timeout }
    catch { return $null }
}

function Get-DateKey($d) {
    try { return ([datetime]$d).ToString("yyyy-MM-dd") } catch { return (Get-Date).ToString("yyyy-MM-dd") }
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

$datasetCsv = Join-Path $astro "ASTRODDS-model-training-dataset-latest.csv"
$ledgerCsv = Join-Path $astro "ASTRODDS-official-picks-ledger-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-356-performance-milestone-tracker-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-356-performance-milestone-tracker-latest.json"

Write-Host ""
Write-Host "ASTRODDS 356 PERFORMANCE MILESTONE TRACKER" -ForegroundColor Cyan
Write-Host "Real results only. No synthetic settled rows." -ForegroundColor Cyan
Write-Host ""

$dataset = Safe-Csv $datasetCsv
$ledger = Safe-Csv $ledgerCsv

$labeled = @($dataset | Where-Object { (Get-Val $_ @("Label")) -match "^[01]$" })
if ($labeled.Count -eq 0 -and $ledger.Count -gt 0) {
    $labeled = @($ledger | Where-Object { (Get-Val $_ @("Status")) -eq "SETTLED" -and (Get-Val $_ @("Result")) -match "WIN|LOSS" })
}

$settled = $labeled.Count
$wins = @($labeled | Where-Object { (Get-Val $_ @("Label","Result")) -match "^1$|WIN" }).Count
$losses = @($labeled | Where-Object { (Get-Val $_ @("Label","Result")) -match "^0$|LOSS" }).Count

$experimentalTarget = 75
$productionTarget = 150
$experimentalRemaining = [math]::Max(0, $experimentalTarget - $settled)
$productionRemaining = [math]::Max(0, $productionTarget - $settled)
$experimentalPct = [math]::Round(($settled / $experimentalTarget) * 100, 1)
$productionPct = [math]::Round(($settled / $productionTarget) * 100, 1)

$mode = "SOURCE_FIRST_ONLY"
if ($settled -ge $productionTarget) { $mode = "PRODUCTION_MODEL_ELIGIBLE" }
elseif ($settled -ge $experimentalTarget) { $mode = "EXPERIMENTAL_MODEL_ELIGIBLE" }

$lines = @()
$lines += "ASTRODDS 356 PERFORMANCE MILESTONE TRACKER"
$lines += ""
$lines += "Settled labeled rows: $settled"
$lines += "Wins: $wins"
$lines += "Losses: $losses"
$lines += "Experimental target: $settled / $experimentalTarget ($experimentalPct%)"
$lines += "Production target: $settled / $productionTarget ($productionPct%)"
$lines += "Remaining to experimental: $experimentalRemaining"
$lines += "Remaining to production: $productionRemaining"
$lines += "Model mode: $mode"
$lines += ""
$lines += "Rule:"
$lines += "- No synthetic results are created."
$lines += "- Model promotion only unlocks from real settled WIN/LOSS rows."

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    settledLabeledRows=$settled
    wins=$wins
    losses=$losses
    experimentalTarget=$experimentalTarget
    productionTarget=$productionTarget
    experimentalRemaining=$experimentalRemaining
    productionRemaining=$productionRemaining
    experimentalProgressPct=$experimentalPct
    productionProgressPct=$productionPct
    modelMode=$mode
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
