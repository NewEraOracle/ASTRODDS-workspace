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

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
$scripts = Join-Path $root "mlb-engine\baseballpred-inspired\scripts"
Ensure-Dir $astro

$outTxt = Join-Path $astro "ASTRODDS-348-SETTLEMENT-FIX-AND-REPORTS-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-348-SETTLEMENT-FIX-AND-REPORTS-latest.json"
$outChild = Join-Path $astro "ASTRODDS-348-child-log-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 348 SETTLEMENT FIX + REPORTS RUNNER" -ForegroundColor Cyan
Write-Host ""

$child = @()
$ref = [ref]$child

$steps = @()
$steps += ,(Run-Step "347 force settle pending officials" (Join-Path $scripts "347_force_settle_pending_officials.ps1") $ref)
$steps += ,(Run-Step "321 rebuild model training dataset" (Join-Path $scripts "321_model_training_dataset_builder.ps1") $ref)
$steps += ,(Run-Step "322 train model policy" (Join-Path $scripts "322_train_model_when_ready_policy.ps1") $ref)
$steps += ,(Run-Step "349 settlement integrity report" (Join-Path $scripts "349_settlement_integrity_report.ps1") $ref)
$steps += ,(Run-Step "309 rebuild client/admin report" (Join-Path $scripts "309_client_admin_report_builder.ps1") $ref)

$child | Set-Content -Encoding UTF8 $outChild

$settleReport = Join-Path $astro "ASTRODDS-347-force-settle-pending-officials-latest.txt"
$integrityReport = Join-Path $astro "ASTRODDS-349-settlement-integrity-report-latest.txt"
$admin = Join-Path $astro "ASTRODDS-FINAL-admin-report-latest.txt"

$settleText = ""
$integrityText = ""
if (Test-Path $settleReport) { $settleText = Get-Content $settleReport -Raw }
if (Test-Path $integrityReport) { $integrityText = Get-Content $integrityReport -Raw }

$lines = @()
$lines += "ASTRODDS 348 SETTLEMENT FIX + REPORTS RUNNER"
$lines += ""
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$lines += ""
$lines += "STEPS"
foreach ($s in $steps) {
    $lines += "- $($s.Name): $($s.Status) | Exit=$($s.ExitCode) | Duration=$($s.DurationSec)s"
}
$lines += ""
$lines += "SETTLEMENT"
$lines += $settleText
$lines += ""
$lines += "INTEGRITY"
$lines += $integrityText
$lines += ""
$lines += "Admin report: $admin"

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    steps=@($steps)
    settlementReport=$settleReport
    integrityReport=$integrityReport
    adminReport=$admin
    childLog=$outChild
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
