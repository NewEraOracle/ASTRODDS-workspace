$ErrorActionPreference = "Continue"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
$scripts = Join-Path $root "mlb-engine\baseballpred-inspired\scripts"

$outTxt = Join-Path $astro "ASTRODDS-269-FINAL-SOURCE-FIRST-BOT-RUN-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-269-FINAL-SOURCE-FIRST-BOT-RUN-latest.json"
$outChildLog = Join-Path $astro "ASTRODDS-269-child-log-latest.txt"
$finalTelegram = Join-Path $astro "ASTRODDS-telegram-FINAL-source-first-client-latest.txt"

$script263 = Join-Path $scripts "263_run_source_connectors_then_bot.ps1"
$script265 = Join-Path $scripts "265_build_source_first_baseline_model.ps1"
$script266 = Join-Path $scripts "266_source_model_market_bridge.ps1"
$script267 = Join-Path $scripts "267_source_first_official_gate.ps1"
$script268 = Join-Path $scripts "268_build_final_source_first_telegram.ps1"
$script270 = Join-Path $scripts "270_final_bot_readiness_report.ps1"

Write-Host ""
Write-Host "ASTRODDS 269 FINAL SOURCE-FIRST BOT RUNNER" -ForegroundColor Cyan
Write-Host "Final flow: sources -> baseline model -> market bridge -> official gate -> telegram" -ForegroundColor Cyan
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
$steps += ,(Run-Step "263 source connectors + parity bot" $script263)
$steps += ,(Run-Step "265 source-first baseline model" $script265)
$steps += ,(Run-Step "266 source model market bridge" $script266)
$steps += ,(Run-Step "267 source-first official gate" $script267)
$steps += ,(Run-Step "268 final source-first telegram" $script268)
$steps += ,(Run-Step "270 final bot readiness report" $script270)

$childLog | Set-Content -Encoding UTF8 $outChildLog

$telegramText = ""
if (Test-Path $finalTelegram) { $telegramText = Get-Content $finalTelegram -Raw }

$lines = @()
$lines += "ASTRODDS 269 FINAL SOURCE-FIRST BOT RUNNER"
$lines += ""
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$lines += ""
$lines += "STEPS"
foreach ($s in $steps) {
    $lines += "- $($s.Name): $($s.Status) | Exit=$($s.ExitCode) | Duration=$($s.DurationSec)s"
}
$lines += ""
$lines += "FINAL CLIENT TELEGRAM FILE"
$lines += $finalTelegram
$lines += ""
$lines += "FINAL CLIENT MESSAGE"
$lines += $telegramText

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    steps = @($steps)
    finalTelegram = $finalTelegram
    childLog = $outChildLog
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output JSON: $outJson"
Write-Host "Child log: $outChildLog"
Write-Host "Telegram: $finalTelegram"
Write-Host ""
