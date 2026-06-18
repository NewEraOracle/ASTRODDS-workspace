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

$outTxt = Join-Path $astro "ASTRODDS-363-bullpen-premium-refresh-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-363-bullpen-premium-refresh-latest.json"
$outChild = Join-Path $astro "ASTRODDS-363-child-log-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 363 BULLPEN + PREMIUM REFRESH" -ForegroundColor Cyan
Write-Host ""

$child = @()
$ref = [ref]$child

$steps = @()
$steps += ,(Run-Step "360B bullpen real usage hotfix" (Join-Path $scripts "360_bullpen_pitch_availability_upgrade.ps1") $ref)
$steps += ,(Run-Step "361 premium real source merge" (Join-Path $scripts "361_premium_real_source_merge.ps1") $ref)
$steps += ,(Run-Step "362 premium readiness report" (Join-Path $scripts "362_premium_readiness_report.ps1") $ref)

$child | Set-Content -Encoding UTF8 $outChild

$premiumTxt = Join-Path $astro "ASTRODDS-362-premium-readiness-report-latest.txt"
$bpTxt = Join-Path $astro "ASTRODDS-360-bullpen-pitch-availability-upgrade-latest.txt"
$premium = ""; $bp = ""
if (Test-Path $premiumTxt) { $premium = Get-Content $premiumTxt -Raw }
if (Test-Path $bpTxt) { $bp = Get-Content $bpTxt -Raw }

$lines = @()
$lines += "ASTRODDS 363 BULLPEN + PREMIUM REFRESH"
$lines += ""
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$lines += ""
$lines += "STEPS"
foreach ($s in $steps) { $lines += "- $($s.Name): $($s.Status) | Exit=$($s.ExitCode) | Duration=$($s.DurationSec)s" }
$lines += ""
$lines += "BULLPEN"
$lines += $bp
$lines += ""
$lines += "PREMIUM"
$lines += $premium

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    steps=@($steps)
    bullpenReport=$bpTxt
    premiumReport=$premiumTxt
    childLog=$outChild
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
