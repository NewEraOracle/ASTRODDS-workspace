$ErrorActionPreference = "Continue"

function Ensure-Dir($path) {
    if (!(Test-Path $path)) { New-Item -ItemType Directory -Force -Path $path | Out-Null }
}

function Run-Step($name, $path, [ref]$childLog) {
    $start = Get-Date
    Write-Host "Running $name..." -ForegroundColor Cyan

    if (!(Test-Path $path)) {
        Write-Host "MISSING: $path" -ForegroundColor Yellow
        return [pscustomobject]@{
            Name = $name
            Status = "MISSING"
            ExitCode = ""
            DurationSec = 0
        }
    }

    try {
        $output = & powershell -ExecutionPolicy Bypass -File $path 2>&1
        $exitCode = $LASTEXITCODE
        $duration = [math]::Round(((Get-Date) - $start).TotalSeconds, 2)

        $childLog.Value += ""
        $childLog.Value += "============================================================"
        $childLog.Value += "STEP: $name"
        $childLog.Value += "PATH: $path"
        $childLog.Value += "EXIT: $exitCode"
        $childLog.Value += "DURATION: $duration sec"
        $childLog.Value += "============================================================"
        $childLog.Value += @($output | ForEach-Object { "$_" })

        if ($exitCode -eq 0 -or $null -eq $exitCode) {
            Write-Host "OK: $name ($duration sec)" -ForegroundColor Green
            return [pscustomobject]@{
                Name = $name
                Status = "OK"
                ExitCode = "0"
                DurationSec = $duration
            }
        } else {
            Write-Host "ERROR: $name exit $exitCode" -ForegroundColor Red
            return [pscustomobject]@{
                Name = $name
                Status = "ERROR"
                ExitCode = "$exitCode"
                DurationSec = $duration
            }
        }
    } catch {
        $duration = [math]::Round(((Get-Date) - $start).TotalSeconds, 2)
        $childLog.Value += ""
        $childLog.Value += "ERROR STEP: $name"
        $childLog.Value += "$($_.Exception.Message)"

        Write-Host "ERROR: $name $($_.Exception.Message)" -ForegroundColor Red
        return [pscustomobject]@{
            Name = $name
            Status = "ERROR"
            ExitCode = "1"
            DurationSec = $duration
        }
    }
}

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
$scripts = Join-Path $root "mlb-engine\baseballpred-inspired\scripts"

Ensure-Dir $astro

$outTxt = Join-Path $astro "ASTRODDS-324-ELITE-FACTORS-RUN-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-324-ELITE-FACTORS-RUN-latest.json"
$outChildLog = Join-Path $astro "ASTRODDS-324-child-log-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 324F ELITE FACTORS RUNNER FIXED" -ForegroundColor Cyan
Write-Host "Runs BaseballPred++ aliases + umpire slot + starter metrics + platoon slot + enhanced bullpen + training policy." -ForegroundColor Cyan
Write-Host ""

$childLog = @()
$ref = [ref]$childLog

$run = @(
    @{Name="306 BaseballPred++ with aliases"; Path=Join-Path $scripts "306_baseballpred_plus_runner_with_aliases.ps1"},
    @{Name="316 umpire strike-zone context"; Path=Join-Path $scripts "316_umpire_strike_zone_context.ps1"},
    @{Name="317 starter advanced pitcher metrics"; Path=Join-Path $scripts "317_starter_advanced_pitcher_metrics.ps1"},
    @{Name="318 platoon splits left/right context"; Path=Join-Path $scripts "318_platoon_splits_lr_context.ps1"},
    @{Name="319 enhanced bullpen leverage"; Path=Join-Path $scripts "319_bullpen_leverage_enhanced.ps1"},
    @{Name="320 elite factor context merge"; Path=Join-Path $scripts "320_elite_factor_context_merge.ps1"},
    @{Name="321 model training dataset builder"; Path=Join-Path $scripts "321_model_training_dataset_builder.ps1"},
    @{Name="322 train model policy"; Path=Join-Path $scripts "322_train_model_when_ready_policy.ps1"},
    @{Name="323 elite official gate"; Path=Join-Path $scripts "323_elite_official_gate.ps1"},
    @{Name="325 elite factors report"; Path=Join-Path $scripts "325_elite_factors_report.ps1"}
)

$steps = @()

foreach ($s in $run) {
    $steps += ,(Run-Step $s.Name $s.Path $ref)
}

$childLog | Set-Content -Encoding UTF8 $outChildLog

$reportPath = Join-Path $astro "ASTRODDS-325-elite-factors-report-latest.txt"
$report = ""
if (Test-Path $reportPath) { $report = Get-Content $reportPath -Raw }

$lines = @()
$lines += "ASTRODDS 324F ELITE FACTORS RUNNER FIXED"
$lines += ""
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$lines += ""
$lines += "STEPS"
foreach ($s in $steps) {
    $lines += "- $($s.Name): $($s.Status) | Exit=$($s.ExitCode) | Duration=$($s.DurationSec)s"
}
$lines += ""
$lines += "ELITE REPORT"
$lines += $report

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    steps = @($steps)
    report = $reportPath
    childLog = $outChildLog
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
exit 0
