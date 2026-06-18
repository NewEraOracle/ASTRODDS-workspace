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

$outTxt = Join-Path $astro "ASTRODDS-377-premium-bullpen-display-fix-run-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-377-premium-bullpen-display-fix-run-latest.json"
$outChild = Join-Path $astro "ASTRODDS-377-child-log-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 377 PREMIUM BULLPEN DISPLAY FIX RUNNER" -ForegroundColor Cyan
Write-Host ""

$child = @()
$ref = [ref]$child

$steps = @()
$steps += ,(Run-Step "362B premium readiness display fix" (Join-Path $scripts "362_premium_readiness_report.ps1") $ref)
$steps += ,(Run-Step "375 moneyline send guard audit" (Join-Path $scripts "375_moneyline_send_guard_and_daily_report_audit.ps1") $ref)

$child | Set-Content -Encoding UTF8 $outChild

$premiumPath = Join-Path $astro "ASTRODDS-362-premium-readiness-report-latest.txt"
$guardPath = Join-Path $astro "ASTRODDS-375-moneyline-send-guard-and-daily-report-audit-latest.txt"
$premium = ""; $guard = ""
if (Test-Path $premiumPath) { $premium = Get-Content $premiumPath -Raw }
if (Test-Path $guardPath) { $guard = Get-Content $guardPath -Raw }

$lines = @()
$lines += "ASTRODDS 377 PREMIUM BULLPEN DISPLAY FIX RUNNER"
$lines += ""
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$lines += ""
$lines += "STEPS"
foreach ($s in $steps) { $lines += "- $($s.Name): $($s.Status) | Exit=$($s.ExitCode) | Duration=$($s.DurationSec)s" }
$lines += ""
$lines += "PREMIUM READINESS"
$lines += $premium
$lines += ""
$lines += "MONEYLINE / 2:30AM GUARD"
$lines += $guard

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    steps=@($steps)
    premiumReport=$premiumPath
    guardReport=$guardPath
    childLog=$outChild
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
