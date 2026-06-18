$ErrorActionPreference = "Continue"

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
if (!(Test-Path $astro)) { New-Item -ItemType Directory -Force -Path $astro | Out-Null }

$outTxt = Join-Path $astro "ASTRODDS-365-bullpen-boxscore-parser-fix-run-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-365-bullpen-boxscore-parser-fix-run-latest.json"
$outChild = Join-Path $astro "ASTRODDS-365-child-log-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 365 BULLPEN BOXSCORE PARSER FIX RUNNER" -ForegroundColor Cyan
Write-Host ""

$child = @()
$ref = [ref]$child

$steps = @()
$steps += ,(Run-Step "364 MLB boxscore pitcher diagnostic" (Join-Path $scripts "364_mlb_boxscore_pitcher_diagnostic.ps1") $ref)
$steps += ,(Run-Step "360C bullpen boxscore parser fix" (Join-Path $scripts "360_bullpen_pitch_availability_upgrade.ps1") $ref)
$steps += ,(Run-Step "361 premium real source merge" (Join-Path $scripts "361_premium_real_source_merge.ps1") $ref)
$steps += ,(Run-Step "362 premium readiness report" (Join-Path $scripts "362_premium_readiness_report.ps1") $ref)

$child | Set-Content -Encoding UTF8 $outChild

$diag = Join-Path $astro "ASTRODDS-364-mlb-boxscore-pitcher-diagnostic-latest.txt"
$bp = Join-Path $astro "ASTRODDS-360-bullpen-pitch-availability-upgrade-latest.txt"
$premium = Join-Path $astro "ASTRODDS-362-premium-readiness-report-latest.txt"

$diagText = ""; $bpText = ""; $premiumText = ""
if (Test-Path $diag) { $diagText = Get-Content $diag -Raw }
if (Test-Path $bp) { $bpText = Get-Content $bp -Raw }
if (Test-Path $premium) { $premiumText = Get-Content $premium -Raw }

$lines = @()
$lines += "ASTRODDS 365 BULLPEN BOXSCORE PARSER FIX RUNNER"
$lines += ""
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$lines += ""
$lines += "STEPS"
foreach ($s in $steps) { $lines += "- $($s.Name): $($s.Status) | Exit=$($s.ExitCode) | Duration=$($s.DurationSec)s" }
$lines += ""
$lines += "DIAGNOSTIC"
$lines += $diagText
$lines += ""
$lines += "BULLPEN"
$lines += $bpText
$lines += ""
$lines += "PREMIUM"
$lines += $premiumText

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    steps=@($steps)
    diagnostic=$diag
    bullpenReport=$bp
    premiumReport=$premium
    childLog=$outChild
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
