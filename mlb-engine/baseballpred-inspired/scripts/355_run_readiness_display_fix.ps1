$ErrorActionPreference = "Continue"

function Run-Step($name, $path) {
    $start = Get-Date
    Write-Host "Running $name..." -ForegroundColor Cyan

    if (!(Test-Path $path)) {
        Write-Host "MISSING: $path" -ForegroundColor Yellow
        return [pscustomobject]@{Name=$name;Status="MISSING";ExitCode="";DurationSec=0}
    }

    $output = & powershell -ExecutionPolicy Bypass -File $path 2>&1
    $exit = $LASTEXITCODE
    $dur = [math]::Round(((Get-Date)-$start).TotalSeconds,2)

    if ($exit -eq 0 -or $null -eq $exit) {
        Write-Host "OK: $name ($dur sec)" -ForegroundColor Green
        return [pscustomobject]@{Name=$name;Status="OK";ExitCode="0";DurationSec=$dur;Output=($output -join "`n")}
    } else {
        Write-Host "ERROR: $name ($exit)" -ForegroundColor Red
        return [pscustomobject]@{Name=$name;Status="ERROR";ExitCode="$exit";DurationSec=$dur;Output=($output -join "`n")}
    }
}

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
$scripts = Join-Path $root "mlb-engine\baseballpred-inspired\scripts"
if (!(Test-Path $astro)) { New-Item -ItemType Directory -Force -Path $astro | Out-Null }

$outTxt = Join-Path $astro "ASTRODDS-355-readiness-display-fix-run-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-355-readiness-display-fix-run-latest.json"

Write-Host ""
Write-Host "ASTRODDS 355 READINESS DISPLAY FIX RUNNER" -ForegroundColor Cyan
Write-Host ""

$steps = @()
$steps += ,(Run-Step "350 training dataset from settled ledger" (Join-Path $scripts "350_training_dataset_from_settled_ledger.ps1"))
$steps += ,(Run-Step "349 settlement integrity report" (Join-Path $scripts "349_settlement_integrity_report.ps1"))
$steps += ,(Run-Step "310 credit budget dashboard" (Join-Path $scripts "310_credit_budget_dashboard.ps1"))
$steps += ,(Run-Step "352B final 100 readiness display fix" (Join-Path $scripts "352_final_100_readiness_report.ps1"))

$readyPath = Join-Path $astro "ASTRODDS-352-final-100-readiness-report-latest.txt"
$ready = ""
if (Test-Path $readyPath) { $ready = Get-Content $readyPath -Raw }

$lines = @()
$lines += "ASTRODDS 355 READINESS DISPLAY FIX RUNNER"
$lines += ""
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$lines += ""
$lines += "STEPS"
foreach ($s in $steps) { $lines += "- $($s.Name): $($s.Status) | Exit=$($s.ExitCode) | Duration=$($s.DurationSec)s" }
$lines += ""
$lines += "READINESS"
$lines += $ready

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    steps=@($steps | Select-Object Name,Status,ExitCode,DurationSec)
    readinessReport=$readyPath
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
