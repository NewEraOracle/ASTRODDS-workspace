$ErrorActionPreference = "Continue"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
$scripts = Join-Path $root "mlb-engine\baseballpred-inspired\scripts"

$outTxt = Join-Path $astro "ASTRODDS-263-SOURCE-CONNECTED-BOT-RUN-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-263-SOURCE-CONNECTED-BOT-RUN-latest.json"
$outChildLog = Join-Path $astro "ASTRODDS-263-child-log-latest.txt"

$script259 = Join-Path $scripts "259_fetch_mlb_live_sources.ps1"
$script260 = Join-Path $scripts "260_fetch_weather_ballpark_sources.ps1"
$script261 = Join-Path $scripts "261_fetch_injury_transaction_sources.ps1"
$script262 = Join-Path $scripts "262_build_source_first_context_board.ps1"
$script264 = Join-Path $scripts "264_source_health_check.ps1"
$script257 = Join-Path $scripts "257_run_baseballpred_parity_bot.ps1"

$finalTelegram = Join-Path $astro "ASTRODDS-telegram-client-safe-new-drops-only-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 263 SOURCE-CONNECTED BOT RUNNER" -ForegroundColor Cyan
Write-Host "CONNECT SOURCES THEN RUN BASEBALLPRED PARITY BOT" -ForegroundColor Cyan
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
$steps += ,(Run-Step "259 fetch MLB schedule/lineups/pitchers/bullpen" $script259)
$steps += ,(Run-Step "260 fetch weather ballpark sources" $script260)
$steps += ,(Run-Step "261 fetch injury/transaction sources" $script261)
$steps += ,(Run-Step "262 build source-first context board" $script262)
$steps += ,(Run-Step "264 source health check" $script264)
$steps += ,(Run-Step "257 BaseballPred parity bot" $script257)

$childLog | Set-Content -Encoding UTF8 $outChildLog

$telegramText = ""
if (Test-Path $finalTelegram) { $telegramText = Get-Content $finalTelegram -Raw }

$lines = @()
$lines += "ASTRODDS 263 SOURCE-CONNECTED BOT RUNNER"
$lines += ""
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$lines += ""
$lines += "STEPS"
foreach ($s in $steps) {
    $lines += "- $($s.Name): $($s.Status) | Exit=$($s.ExitCode) | Duration=$($s.DurationSec)s"
}
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
