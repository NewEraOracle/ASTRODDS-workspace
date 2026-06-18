$ErrorActionPreference = "Continue"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
$scripts = Join-Path $root "mlb-engine\baseballpred-inspired\scripts"

$outTxt = Join-Path $astro "ASTRODDS-279-MODEL-QUALITY-UPGRADE-BOT-RUN-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-279-MODEL-QUALITY-UPGRADE-BOT-RUN-latest.json"
$outChildLog = Join-Path $astro "ASTRODDS-279-child-log-latest.txt"
$productionTelegram = Join-Path $astro "ASTRODDS-telegram-PRODUCTION-final-latest.txt"

$stepsToRun = @(
    @{Name="259 refresh MLB live sources"; Path=(Join-Path $scripts "259_fetch_mlb_live_sources.ps1")},
    @{Name="273 fetch market moneyline sources"; Path=(Join-Path $scripts "273_fetch_market_moneyline_sources.ps1")},
    @{Name="274 build rolling bullpen 3d/7d"; Path=(Join-Path $scripts "274_build_rolling_bullpen_3d_7d.ps1")},
    @{Name="275 fetch full roster injury status"; Path=(Join-Path $scripts "275_fetch_full_roster_injury_status.ps1")},
    @{Name="260 refresh weather"; Path=(Join-Path $scripts "260_fetch_weather_ballpark_sources.ps1")},
    @{Name="278 rebuild source board with quality sources"; Path=(Join-Path $scripts "278_rebuild_source_board_with_quality_sources.ps1")},
    @{Name="276 calibrate confidence from ledger"; Path=(Join-Path $scripts "276_calibrate_confidence_from_ledger.ps1")},
    @{Name="277 train or refresh model policy"; Path=(Join-Path $scripts "277_train_or_refresh_model_policy.ps1")},
    @{Name="271 production final router"; Path=(Join-Path $scripts "271_production_final_router.ps1")},
    @{Name="280 model quality upgrade report"; Path=(Join-Path $scripts "280_model_quality_upgrade_report.ps1")}
)

Write-Host ""
Write-Host "ASTRODDS 279 MODEL QUALITY UPGRADE BOT RUNNER" -ForegroundColor Cyan
Write-Host "Market + rolling bullpen + stronger injury + calibration + production router" -ForegroundColor Cyan
Write-Host ""

$childLog = @()

function Run-Step($name, $path) {
    $start = Get-Date
    Write-Host "Running $name..." -ForegroundColor Cyan

    if (!(Test-Path $path)) {
        Write-Host "MISSING: $path" -ForegroundColor Yellow
        return [pscustomobject]@{ Name=$name; Status="MISSING"; ExitCode=""; DurationSec=0 }
    }

    try {
        $output = & powershell -ExecutionPolicy Bypass -File $path 2>&1
        $exitCode = $LASTEXITCODE
        $duration = [math]::Round(((Get-Date) - $start).TotalSeconds, 2)

        $script:childLog += ""
        $script:childLog += "============================================================"
        $script:childLog += "STEP: $name"
        $script:childLog += "PATH: $path"
        $script:childLog += "EXIT: $exitCode"
        $script:childLog += "DURATION: $duration sec"
        $script:childLog += "============================================================"
        $script:childLog += @($output | ForEach-Object { "$_" })

        if ($exitCode -eq 0 -or $null -eq $exitCode) {
            Write-Host "OK: $name ($duration sec)" -ForegroundColor Green
            return [pscustomobject]@{ Name=$name; Status="OK"; ExitCode="0"; DurationSec=$duration }
        } else {
            Write-Host "ERROR: $name exit $exitCode" -ForegroundColor Red
            return [pscustomobject]@{ Name=$name; Status="ERROR"; ExitCode="$exitCode"; DurationSec=$duration }
        }
    } catch {
        $duration = [math]::Round(((Get-Date) - $start).TotalSeconds, 2)
        $script:childLog += ""
        $script:childLog += "ERROR STEP: $name"
        $script:childLog += "$($_.Exception.Message)"
        return [pscustomobject]@{ Name=$name; Status="ERROR"; ExitCode="1"; DurationSec=$duration }
    }
}

$steps = @()
foreach ($s in $stepsToRun) {
    $steps += ,(Run-Step $s.Name $s.Path)
}

$childLog | Set-Content -Encoding UTF8 $outChildLog

$telegram = ""
if (Test-Path $productionTelegram) { $telegram = Get-Content $productionTelegram -Raw }

$lines = @()
$lines += "ASTRODDS 279 MODEL QUALITY UPGRADE BOT RUNNER"
$lines += ""
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$lines += ""
$lines += "STEPS"
foreach ($s in $steps) {
    $lines += "- $($s.Name): $($s.Status) | Exit=$($s.ExitCode) | Duration=$($s.DurationSec)s"
}
$lines += ""
$lines += "FINAL PRODUCTION TELEGRAM"
$lines += $productionTelegram
$lines += ""
$lines += "FINAL MESSAGE"
$lines += $telegram

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    steps = @($steps)
    productionTelegram = $productionTelegram
    childLog = $outChildLog
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output JSON: $outJson"
Write-Host "Child log: $outChildLog"
Write-Host "Production Telegram: $productionTelegram"
Write-Host ""
exit 0
