$ErrorActionPreference = "Continue"

function Ensure-Dir($path) {
    if (!(Test-Path $path)) { New-Item -ItemType Directory -Force -Path $path | Out-Null }
}

function Read-JsonSafe($path) {
    if (!(Test-Path $path)) { return $null }
    try { return Get-Content $path -Raw | ConvertFrom-Json } catch { return $null }
}

function JVal($obj, $names, $default = "0") {
    if ($null -eq $obj) { return $default }
    foreach ($n in @($names)) {
        try {
            $p = $obj.PSObject.Properties[$n]
            if ($null -ne $p -and $null -ne $p.Value) {
                $v = "$($p.Value)".Trim()
                if ($v -ne "") { return $v }
            }
        } catch {}
    }
    return $default
}

function As-Int($v) {
    try { return [int]"$v" } catch { return 0 }
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

$outTxt = Join-Path $astro "ASTRODDS-362-premium-readiness-report-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-362-premium-readiness-report-latest.json"
$outChild = Join-Path $astro "ASTRODDS-362-child-log-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 362B PREMIUM READINESS REPORT - BULLPEN DISPLAY FIX" -ForegroundColor Cyan
Write-Host "Reads both old and new 360/360C bullpen JSON keys. No fake data." -ForegroundColor Cyan
Write-Host ""

$child = @()
$ref = [ref]$child

# Keep the bridge fresh, but don't fail the report if optional scripts are missing.
$steps = @()
foreach ($step in @(
    @("356 performance milestone tracker", "356_performance_milestone_tracker.ps1"),
    @("357 umpire real source bridge", "357_umpire_real_source_bridge.ps1"),
    @("358 platoon splits real source bridge", "358_platoon_splits_real_source_bridge.ps1"),
    @("359 starter xFIP real source bridge", "359_starter_xfip_real_source_bridge.ps1"),
    @("360 bullpen pitch availability", "360_bullpen_pitch_availability_upgrade.ps1"),
    @("366 bullpen stress calibration", "366_bullpen_stress_calibration.ps1"),
    @("361 premium real source merge", "361_premium_real_source_merge.ps1")
)) {
    $path = Join-Path $scripts $step[1]
    if (Test-Path $path) { $steps += ,(Run-Step $step[0] $path $ref) }
}

$child | Set-Content -Encoding UTF8 $outChild

function Json($file) {
    return Read-JsonSafe (Join-Path $astro $file)
}

$milestone = Json "ASTRODDS-356-performance-milestone-tracker-latest.json"
$ump = Json "ASTRODDS-357-umpire-real-source-bridge-latest.json"
$platoon = Json "ASTRODDS-358-platoon-splits-real-source-bridge-latest.json"
$xfip = Json "ASTRODDS-359-starter-xfip-real-source-bridge-latest.json"
$bp = Json "ASTRODDS-360-bullpen-pitch-availability-upgrade-latest.json"
$cal = Json "ASTRODDS-366-bullpen-stress-calibration-latest.json"
$merge = Json "ASTRODDS-361-premium-real-source-merge-latest.json"

$settledRows = JVal $milestone @("settledLabeledRows") "0"
$experimentalTarget = JVal $milestone @("experimentalTarget") "75"
$productionTarget = JVal $milestone @("productionTarget") "150"
$modelMode = JVal $milestone @("modelMode") "SOURCE_FIRST_ONLY"

$umpireConnected = JVal $ump @("homePlateConnected") "0"
$umpireRatingConnected = JVal $ump @("ratingConnected") "0"
$platoonFull = JVal $platoon @("rowsFullyConnected") "0"
$xfipFull = JVal $xfip @("rowsFullyConnected") "0"

# Compatibility fix: old 360 used realPitchUsageConnectedTeams, 360B/360C use realBullpenUsageConnectedTeams / realPitchCountsConnectedTeams.
$bullpenUsageTeams = JVal $bp @("realPitchUsageConnectedTeams","realBullpenUsageConnectedTeams","realPitchCountsConnectedTeams") "0"
$bullpenPitchCountTeams = JVal $bp @("realPitchCountsConnectedTeams","realPitchCountsConnectedTeams") "0"
$bullpenCalibratedTeams = JVal $cal @("calibratedConnectedTeams") "0"
$trueLeverageTeams = JVal $bp @("trueLeverageConnectedTeams") "0"

$premiumCore = JVal $merge @("premiumRealCoreConnected") "0"
$premiumPartial = JVal $merge @("premiumPartialRealConnected") "0"

$status = "PREMIUM_BRIDGE_READY_NO_FAKE_DATA"
$warnings = @()

if ((As-Int $platoonFull) -eq 0) { $warnings += "platoon CSV/source not connected yet" }
if ((As-Int $xfipFull) -eq 0) { $warnings += "true xFIP CSV/source not connected yet" }
if ((As-Int $trueLeverageTeams) -eq 0) { $warnings += "true leverage source not connected yet" }
if ((As-Int $bullpenUsageTeams) -eq 0) { $warnings += "bullpen pitch usage source not connected yet" }

$lines = @()
$lines += "ASTRODDS 362B PREMIUM READINESS REPORT - BULLPEN DISPLAY FIX"
$lines += ""
$lines += "Status: $status"
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$lines += ""
$lines += "PERFORMANCE"
$lines += "- Settled labeled rows: $settledRows"
$lines += "- Experimental: $settledRows / $experimentalTarget"
$lines += "- Production: $settledRows / $productionTarget"
$lines += "- Model mode: $modelMode"
$lines += ""
$lines += "REAL PREMIUM SOURCES"
$lines += "- Home plate umpire connected rows: $umpireConnected"
$lines += "- Umpire rating connected rows: $umpireRatingConnected"
$lines += "- Platoon fully connected rows: $platoonFull"
$lines += "- True xFIP fully connected rows: $xfipFull"
$lines += "- Real bullpen pitch usage teams: $bullpenUsageTeams"
$lines += "- Real bullpen pitch count teams: $bullpenPitchCountTeams"
$lines += "- Calibrated bullpen stress teams: $bullpenCalibratedTeams"
$lines += "- True leverage connected teams: $trueLeverageTeams"
$lines += "- Premium real core connected rows: $premiumCore"
$lines += "- Premium partial real connected rows: $premiumPartial"
$lines += ""
$lines += "WARNINGS / MISSING REAL SOURCES"
if ($warnings.Count -eq 0) { $lines += "- none" } else { foreach ($w in $warnings) { $lines += "- $w" } }
$lines += ""
$lines += "NO-FAKE RULE"
$lines += "- Umpire, platoon, xFIP and true leverage are only used when real source rows exist."
$lines += "- Missing source fields stay MISSING_SOURCE."
$lines += "- Premium bridge does not create client official picks by itself."
$lines += "- 2:30 AM remains report only; Moneyline send is pre-game gate only."
$lines += ""
$lines += "CSV TEMPLATES"
$lines += "- C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace\.astrodds\ASTRODDS-premium-input-umpire-ratings.csv"
$lines += "- C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace\.astrodds\ASTRODDS-premium-input-team-platoon-splits.csv"
$lines += "- C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace\.astrodds\ASTRODDS-premium-input-starter-xfip.csv"
$lines += "- C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace\.astrodds\ASTRODDS-premium-input-bullpen-leverage-availability.csv"

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    status=$status
    warnings=@($warnings)
    settledLabeledRows=$settledRows
    modelMode=$modelMode
    homePlateUmpireConnectedRows=$umpireConnected
    umpireRatingConnectedRows=$umpireRatingConnected
    platoonFullyConnectedRows=$platoonFull
    trueXfipFullyConnectedRows=$xfipFull
    realBullpenPitchUsageTeams=$bullpenUsageTeams
    realBullpenPitchCountTeams=$bullpenPitchCountTeams
    calibratedBullpenStressTeams=$bullpenCalibratedTeams
    trueLeverageConnectedTeams=$trueLeverageTeams
    premiumRealCoreConnectedRows=$premiumCore
    premiumPartialRealConnectedRows=$premiumPartial
    childLog=$outChild
} | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
