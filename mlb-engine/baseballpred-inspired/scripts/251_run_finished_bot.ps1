$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
$scripts = Join-Path $root "mlb-engine\baseballpred-inspired\scripts"

$script248 = Join-Path $scripts "248_context_merged_confidence_score.ps1"
$script249 = Join-Path $scripts "249_price_movement_guard.ps1"
$script250 = Join-Path $scripts "250_settle_official_picks.ps1"
$script252 = Join-Path $scripts "252_final_status_board.ps1"

$outTxt = Join-Path $astro "ASTRODDS-FINISHED-BOT-RUN-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-FINISHED-BOT-RUN-latest.json"
$outChildLog = Join-Path $astro "ASTRODDS-FINISHED-BOT-child-log-latest.txt"

$finalTelegram = Join-Path $astro "ASTRODDS-telegram-price-guarded-final-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 251 FINISHED BOT RUNNER" -ForegroundColor Cyan
Write-Host "ONE COMMAND - FULL CONTEXT + PRICE GUARD + SETTLEMENT + STATUS" -ForegroundColor Cyan
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
$steps += ,(Run-Step "248 context-merged confidence" $script248)
$steps += ,(Run-Step "249 price movement guard" $script249)
$steps += ,(Run-Step "250 settle official picks" $script250)
$steps += ,(Run-Step "252 final status board" $script252)

$childLog | Set-Content -Encoding UTF8 $outChildLog

$telegramText = ""
if (Test-Path $finalTelegram) { $telegramText = Get-Content $finalTelegram -Raw }

$lines = @()
$lines += "ASTRODDS 251 FINISHED BOT RUNNER"
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
