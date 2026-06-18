$ErrorActionPreference = "Continue"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
$scripts = Join-Path $root "mlb-engine\baseballpred-inspired\scripts"

$outTxt = Join-Path $astro "ASTRODDS-271-PRODUCTION-FINAL-ROUTER-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-271-PRODUCTION-FINAL-ROUTER-latest.json"
$outChildLog = Join-Path $astro "ASTRODDS-271-child-log-latest.txt"

$productionTelegram = Join-Path $astro "ASTRODDS-telegram-PRODUCTION-final-latest.txt"
$trustedTelegram = Join-Path $astro "ASTRODDS-telegram-client-safe-new-drops-only-latest.txt"
$sourceFirstTelegram = Join-Path $astro "ASTRODDS-telegram-FINAL-source-first-client-latest.txt"

$script263 = Join-Path $scripts "263_run_source_connectors_then_bot.ps1"
$script265 = Join-Path $scripts "265_build_source_first_baseline_model.ps1"
$script266 = Join-Path $scripts "266_source_model_market_bridge.ps1"
$script267 = Join-Path $scripts "267_source_first_official_gate.ps1"
$script270 = Join-Path $scripts "270_final_bot_readiness_report.ps1"
$script272 = Join-Path $scripts "272_final_production_status.ps1"

Write-Host ""
Write-Host "ASTRODDS 271 PRODUCTION FINAL ROUTER" -ForegroundColor Cyan
Write-Host "Production rule: trusted market-connected Telegram wins; source-first baseline is review coverage only." -ForegroundColor Cyan
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
$steps += ,(Run-Step "263 source connectors + trusted parity bot" $script263)
$steps += ,(Run-Step "265 source-first baseline model coverage" $script265)
$steps += ,(Run-Step "266 source model market bridge audit" $script266)
$steps += ,(Run-Step "267 source-first official gate audit" $script267)
$steps += ,(Run-Step "270 final bot readiness report" $script270)
$steps += ,(Run-Step "272 final production status" $script272)

$childLog | Set-Content -Encoding UTF8 $outChildLog

# Use trusted final message for production because source-first baseline can create review-only picks
# without real market price. Source-first telegram is audit only.
$finalMessage = ""
$sourceUsed = ""

if (Test-Path $trustedTelegram) {
    $finalMessage = Get-Content $trustedTelegram -Raw
    $sourceUsed = $trustedTelegram
} elseif (Test-Path $sourceFirstTelegram) {
    $finalMessage = Get-Content $sourceFirstTelegram -Raw
    $sourceUsed = $sourceFirstTelegram
} else {
    $finalMessage = "🚫 ASTRODDS CLIENT DROP BLOCKED`nNo final Telegram message file was found."
    $sourceUsed = "NONE"
}

$header = @()
$header += "ASTRODDS PRODUCTION FINAL MESSAGE"
$header += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$header += ""
$header += "Production mode:"
$header += "• Uses trusted market-connected client-safe pipeline"
$header += "• Source-first baseline model is coverage/review only"
$header += "• No fake market prices"
$header += ""

($header + $finalMessage) -join [Environment]::NewLine | Set-Content -Encoding UTF8 $productionTelegram

$lines = @()
$lines += "ASTRODDS 271 PRODUCTION FINAL ROUTER"
$lines += ""
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$lines += ""
$lines += "STEPS"
foreach ($s in $steps) {
    $lines += "- $($s.Name): $($s.Status) | Exit=$($s.ExitCode) | Duration=$($s.DurationSec)s"
}
$lines += ""
$lines += "PRODUCTION TELEGRAM FILE"
$lines += $productionTelegram
$lines += ""
$lines += "Production message source:"
$lines += $sourceUsed
$lines += ""
$lines += "FINAL MESSAGE"
$lines += Get-Content $productionTelegram -Raw

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    steps = @($steps)
    productionTelegram = $productionTelegram
    messageSource = $sourceUsed
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
