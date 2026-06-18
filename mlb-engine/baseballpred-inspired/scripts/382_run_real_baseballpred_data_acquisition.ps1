param([switch]$Force,[int]$PlatoonDaysBack = 60)
$ErrorActionPreference = "Continue"

function Ensure-Dir($path) {
    if (!(Test-Path $path)) { New-Item -ItemType Directory -Force -Path $path | Out-Null }
}
function Is-FreshToday($path) {
    if (!(Test-Path $path)) { return $false }
    try { return ((Get-Item $path).LastWriteTime.Date -eq (Get-Date).Date) } catch { return $false }
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

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
$scripts = Join-Path $root "mlb-engine\baseballpred-inspired\scripts"
Ensure-Dir $astro
$outTxt = Join-Path $astro "ASTRODDS-382-real-baseballpred-data-acquisition-run-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-382-real-baseballpred-data-acquisition-run-latest.json"
$outChild = Join-Path $astro "ASTRODDS-382-child-log-latest.txt"
Write-Host ""
Write-Host "ASTRODDS 382 REAL BASEBALLPRED DATA ACQUISITION RUNNER" -ForegroundColor Cyan
Write-Host ""
$child = @()
$ref = [ref]$child
$steps = @()
$steps += ,(Run-Step "378 Python pybaseball tools" (Join-Path $scripts "378_check_python_pybaseball_tools.ps1") $ref)
$forceArgs = @()
if ($Force) { $forceArgs += "-Force" }

$start = Get-Date
Write-Host "Running 379 true xFIP fetch..." -ForegroundColor Cyan
$out379 = & powershell -ExecutionPolicy Bypass -File (Join-Path $scripts "379_fetch_true_xfip_fangraphs_pybaseball.ps1") @forceArgs 2>&1
$steps += ,[pscustomobject]@{Name="379 true xFIP fetch";Status=(if($LASTEXITCODE -eq 0){"OK"}else{"ERROR"});ExitCode="$LASTEXITCODE";DurationSec=[math]::Round(((Get-Date)-$start).TotalSeconds,2)}
$child += @($out379 | ForEach-Object { "$_" })

$start = Get-Date
Write-Host "Running 380 real platoon fetch..." -ForegroundColor Cyan
if ($Force) {
    $out380 = & powershell -ExecutionPolicy Bypass -File (Join-Path $scripts "380_fetch_team_platoon_statcast_pybaseball.ps1") -Force -DaysBack $PlatoonDaysBack 2>&1
} else {
    $out380 = & powershell -ExecutionPolicy Bypass -File (Join-Path $scripts "380_fetch_team_platoon_statcast_pybaseball.ps1") -DaysBack $PlatoonDaysBack 2>&1
}
$steps += ,[pscustomobject]@{Name="380 real platoon fetch";Status=(if($LASTEXITCODE -eq 0){"OK"}else{"ERROR"});ExitCode="$LASTEXITCODE";DurationSec=[math]::Round(((Get-Date)-$start).TotalSeconds,2)}
$child += @($out380 | ForEach-Object { "$_" })

$start = Get-Date
Write-Host "Running 381 true leverage fetch..." -ForegroundColor Cyan
$out381 = & powershell -ExecutionPolicy Bypass -File (Join-Path $scripts "381_fetch_true_leverage_fangraphs_pybaseball.ps1") @forceArgs 2>&1
$steps += ,[pscustomobject]@{Name="381 true leverage fetch";Status=(if($LASTEXITCODE -eq 0){"OK"}else{"ERROR"});ExitCode="$LASTEXITCODE";DurationSec=[math]::Round(((Get-Date)-$start).TotalSeconds,2)}
$child += @($out381 | ForEach-Object { "$_" })

foreach ($pair in @(
    @("370 real premium CSV schema validator","370_real_premium_csv_schema_validator.ps1"),
    @("358 platoon bridge","358_platoon_splits_real_source_bridge.ps1"),
    @("371 platoon finalizer","371_platoon_real_csv_finalizer.ps1"),
    @("359 xFIP bridge","359_starter_xfip_real_source_bridge.ps1"),
    @("372 xFIP finalizer","372_fangraphs_xfip_real_csv_finalizer.ps1"),
    @("373 true leverage finalizer","373_true_leverage_real_csv_finalizer.ps1"),
    @("361 premium merge","361_premium_real_source_merge.ps1"),
    @("362 premium readiness","362_premium_readiness_report.ps1"),
    @("367 11/11 scorecard","367_final_11_of_11_scorecard.ps1"),
    @("383 acquisition report","383_real_premium_source_acquisition_report.ps1")
)) {
    $steps += ,(Run-Step $pair[0] (Join-Path $scripts $pair[1]) $ref)
}
$child | Set-Content -Encoding UTF8 $outChild
$report = Join-Path $astro "ASTRODDS-383-real-premium-source-acquisition-report-latest.txt"
$reportText = ""
if (Test-Path $report) { $reportText = Get-Content $report -Raw }
$lines = @("ASTRODDS 382 REAL BASEBALLPRED DATA ACQUISITION RUNNER","","Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')","Force: $Force","PlatoonDaysBack: $PlatoonDaysBack","","STEPS")
foreach ($s in $steps) { $lines += "- $($s.Name): $($s.Status) | Exit=$($s.ExitCode) | Duration=$($s.DurationSec)s" }
$lines += ""; $lines += "ACQUISITION REPORT"; $lines += $reportText
[pscustomobject]@{generatedAt=(Get-Date).ToString("o");force=[bool]$Force;platoonDaysBack=$PlatoonDaysBack;steps=@($steps);acquisitionReport=$report;childLog=$outChild} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson
($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
