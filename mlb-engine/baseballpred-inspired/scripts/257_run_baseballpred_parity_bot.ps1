$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
$scripts = Join-Path $root "mlb-engine\baseballpred-inspired\scripts"

$script251 = Join-Path $scripts "251_run_finished_bot.ps1"
$script253 = Join-Path $scripts "253_baseballpred_parity_audit.ps1"
$script254 = Join-Path $scripts "254_missing_games_source_hunter_fast.ps1"
$script255 = Join-Path $scripts "255_schedule_first_full_slate_bridge.ps1"
$script256 = Join-Path $scripts "256_confidence_calibration_board.ps1"
$script258 = Join-Path $scripts "258_block_in_progress_new_drops.ps1"

$outTxt = Join-Path $astro "ASTRODDS-257-BASEBALLPRED-PARITY-BOT-RUN-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-257-BASEBALLPRED-PARITY-BOT-RUN-latest.json"
$outChildLog = Join-Path $astro "ASTRODDS-257-child-log-latest.txt"

$finalTelegram = Join-Path $astro "ASTRODDS-telegram-client-safe-new-drops-only-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 257 BASEBALLPRED PARITY BOT RUNNER" -ForegroundColor Cyan
Write-Host "ONE COMMAND - FINISHED BOT + PARITY AUDIT + NO_MODEL HUNTER + CALIBRATION" -ForegroundColor Cyan
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
$steps += ,(Run-Step "251 finished bot core" $script251)
$steps += ,(Run-Step "253 BaseballPred parity audit" $script253)
$steps += ,(Run-Step "254 missing games source hunter" $script254)
$steps += ,(Run-Step "255 schedule-first full slate bridge" $script255)
$steps += ,(Run-Step "256 confidence calibration board" $script256)
$steps += ,(Run-Step "258 block in-progress new drops" $script258)

$childLog | Set-Content -Encoding UTF8 $outChildLog

$telegramText = ""
if (Test-Path $finalTelegram) { $telegramText = Get-Content $finalTelegram -Raw }

$lines = @()
$lines += "ASTRODDS 257 BASEBALLPRED PARITY BOT RUNNER"
$lines += ""
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$lines += ""
$lines += "STEPS"
foreach ($s in $steps) {
    $lines += "- $($s.Name): $($s.Status) | Exit=$($s.ExitCode) | Duration=$($s.DurationSec)s"
}
$lines += ""
$lines += "FINAL NEW-DROP TELEGRAM FILE"
$lines += $finalTelegram
$lines += ""
$lines += "FINAL NEW-DROP MESSAGE"
$lines += $telegramText
$lines += ""
$lines += "IMPORTANT"
$lines += "- If final message is BLOCKED_ALREADY_STARTED, do not send as a new pick."
$lines += "- Ledger settlement still tracks picks already sent."

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
