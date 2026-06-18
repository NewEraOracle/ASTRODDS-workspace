param(
    [int]$PlatoonDaysBack = 14
)

$ErrorActionPreference = "Continue"


function Ensure-Dir($path) {
    if (!(Test-Path $path)) { New-Item -ItemType Directory -Force -Path $path | Out-Null }
}

function Run-Step($name, $path, [ref]$childLog) {
    $start = Get-Date
    Write-Host "Running $name..." -ForegroundColor Cyan

    if (!(Test-Path $path)) {
        Write-Host "MISSING: $path" -ForegroundColor Yellow
        return [pscustomobject]@{Name=$name;Status="MISSING";ExitCode="";DurationSec=0}
    }

    $output = & powershell -ExecutionPolicy Bypass -File $path 2>&1
    $exit = $LASTEXITCODE
    $dur = [math]::Round(((Get-Date)-$start).TotalSeconds,2)

    $childLog.Value += ""
    $childLog.Value += "==== $name | Exit=$exit | Duration=$dur ===="
    $childLog.Value += @($output | ForEach-Object { "$_" })

    if ($exit -eq 0 -or $null -eq $exit) {
        Write-Host "OK: $name ($dur sec)" -ForegroundColor Green
        return [pscustomobject]@{Name=$name;Status="OK";ExitCode="0";DurationSec=$dur}
    } else {
        Write-Host "ERROR: $name ($exit)" -ForegroundColor Red
        return [pscustomobject]@{Name=$name;Status="ERROR";ExitCode="$exit";DurationSec=$dur}
    }
}

function Status-FromExit($exitCode) {
    if ($exitCode -eq 0 -or $null -eq $exitCode) { return "OK" }
    return "ERROR"
}

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
$scripts = Join-Path $root "mlb-engine\baseballpred-inspired\scripts"
Ensure-Dir $astro

$outTxt = Join-Path $astro "ASTRODDS-384-force-real-data-acquisition-no-empty-skip-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-384-force-real-data-acquisition-no-empty-skip-latest.json"
$outChild = Join-Path $astro "ASTRODDS-384-child-log-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 384F FORCE REAL DATA ACQUISITION - POWERSHELL IF FIX" -ForegroundColor Cyan
Write-Host "No inline if expressions. Windows PowerShell 5.1 safe." -ForegroundColor Cyan
Write-Host ""

$child = @()
$ref = [ref]$child
$steps = @()

$steps += ,(Run-Step "378 Python pybaseball tools" (Join-Path $scripts "378_check_python_pybaseball_tools.ps1") $ref)

$start = Get-Date
Write-Host "Running 379F true xFIP fetch -Force..." -ForegroundColor Cyan
$out379 = & powershell -ExecutionPolicy Bypass -File (Join-Path $scripts "379_fetch_true_xfip_fangraphs_pybaseball.ps1") -Force 2>&1
$exit379 = $LASTEXITCODE
$status379 = Status-FromExit $exit379
$dur379 = [math]::Round(((Get-Date)-$start).TotalSeconds,2)
$steps += ,[pscustomobject]@{Name="379F true xFIP fetch -Force";Status=$status379;ExitCode="$exit379";DurationSec=$dur379}
$child += ""
$child += "==== 379F true xFIP fetch -Force | Exit=$exit379 | Duration=$dur379 ===="
$child += @($out379 | ForEach-Object { "$_" })

$start = Get-Date
Write-Host "Running 380F platoon fetch -Force..." -ForegroundColor Cyan
$out380 = & powershell -ExecutionPolicy Bypass -File (Join-Path $scripts "380_fetch_team_platoon_statcast_pybaseball.ps1") -Force -DaysBack $PlatoonDaysBack 2>&1
$exit380 = $LASTEXITCODE
$status380 = Status-FromExit $exit380
$dur380 = [math]::Round(((Get-Date)-$start).TotalSeconds,2)
$steps += ,[pscustomobject]@{Name="380F platoon fetch -Force";Status=$status380;ExitCode="$exit380";DurationSec=$dur380}
$child += ""
$child += "==== 380F platoon fetch -Force | Exit=$exit380 | Duration=$dur380 ===="
$child += @($out380 | ForEach-Object { "$_" })

$start = Get-Date
Write-Host "Running 381F true leverage fetch -Force..." -ForegroundColor Cyan
$out381 = & powershell -ExecutionPolicy Bypass -File (Join-Path $scripts "381_fetch_true_leverage_fangraphs_pybaseball.ps1") -Force 2>&1
$exit381 = $LASTEXITCODE
$status381 = Status-FromExit $exit381
$dur381 = [math]::Round(((Get-Date)-$start).TotalSeconds,2)
$steps += ,[pscustomobject]@{Name="381F true leverage fetch -Force";Status=$status381;ExitCode="$exit381";DurationSec=$dur381}
$child += ""
$child += "==== 381F true leverage fetch -Force | Exit=$exit381 | Duration=$dur381 ===="
$child += @($out381 | ForEach-Object { "$_" })

foreach ($pair in @(
    @("370 CSV schema validator","370_real_premium_csv_schema_validator.ps1"),
    @("358 platoon bridge","358_platoon_splits_real_source_bridge.ps1"),
    @("371 platoon finalizer","371_platoon_real_csv_finalizer.ps1"),
    @("359 xFIP bridge","359_starter_xfip_real_source_bridge.ps1"),
    @("372 xFIP finalizer","372_fangraphs_xfip_real_csv_finalizer.ps1"),
    @("373 true leverage finalizer","373_true_leverage_real_csv_finalizer.ps1"),
    @("361 premium merge","361_premium_real_source_merge.ps1"),
    @("362 premium readiness","362_premium_readiness_report.ps1"),
    @("383 acquisition report","383_real_premium_source_acquisition_report.ps1"),
    @("385 error diagnostic","385_real_data_fetch_error_diagnostic.ps1")
)) {
    $steps += ,(Run-Step $pair[0] (Join-Path $scripts $pair[1]) $ref)
}

$child | Set-Content -Encoding UTF8 $outChild

$report = Join-Path $astro "ASTRODDS-383-real-premium-source-acquisition-report-latest.txt"
$premium = Join-Path $astro "ASTRODDS-362-premium-readiness-report-latest.txt"
$diag = Join-Path $astro "ASTRODDS-385-real-data-fetch-error-diagnostic-latest.txt"

$reportText = ""
$premiumText = ""
$diagText = ""

if (Test-Path $report) { $reportText = Get-Content $report -Raw }
if (Test-Path $premium) { $premiumText = Get-Content $premium -Raw }
if (Test-Path $diag) { $diagText = Get-Content $diag -Raw }

$lines = @()
$lines += "ASTRODDS 384F FORCE REAL DATA ACQUISITION - POWERSHELL IF FIX"
$lines += ""
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$lines += "PlatoonDaysBack: $PlatoonDaysBack"
$lines += ""
$lines += "STEPS"
foreach ($s in $steps) {
    $lines += "- $($s.Name): $($s.Status) | Exit=$($s.ExitCode) | Duration=$($s.DurationSec)s"
}
$lines += ""
$lines += "ACQUISITION REPORT"
$lines += $reportText
$lines += ""
$lines += "DIAGNOSTIC"
$lines += $diagText
$lines += ""
$lines += "PREMIUM"
$lines += $premiumText

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    platoonDaysBack=$PlatoonDaysBack
    steps=@($steps)
    acquisitionReport=$report
    diagnosticReport=$diag
    premiumReport=$premium
    childLog=$outChild
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
