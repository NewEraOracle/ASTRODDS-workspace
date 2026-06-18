$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
$scripts = Join-Path $root "mlb-engine\baseballpred-inspired\scripts"

$outTxt  = Join-Path $astro "ASTRODDS-daily-safe-run-CLEAN-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-daily-safe-run-CLEAN-latest.json"
$outTelegram = Join-Path $astro "ASTRODDS-telegram-client-safe-final-CLEAN-latest.txt"
$outChildLog = Join-Path $astro "ASTRODDS-daily-safe-run-child-output-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 225B DAILY SAFE RUNNER CLEAN" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - CLEAN STEP REPORT" -ForegroundColor Cyan
Write-Host ""

$childLogLines = @()

function Run-StepClean($name, $path) {
    $started = Get-Date

    Write-Host "Running $name..." -ForegroundColor Cyan

    if (!(Test-Path $path)) {
        Write-Host "MISSING: $path" -ForegroundColor Yellow

        return [pscustomobject]@{
            Name = $name
            Path = $path
            Status = "MISSING"
            ExitCode = ""
            DurationSec = 0
        }
    }

    try {
        $output = & powershell -ExecutionPolicy Bypass -File $path 2>&1
        $exitCode = $LASTEXITCODE

        $script:childLogLines += ""
        $script:childLogLines += "============================================================"
        $script:childLogLines += "STEP: $name"
        $script:childLogLines += "PATH: $path"
        $script:childLogLines += "EXIT: $exitCode"
        $script:childLogLines += "============================================================"
        $script:childLogLines += @($output | ForEach-Object { "$_" })

        $ended = Get-Date
        $duration = [math]::Round(($ended - $started).TotalSeconds, 2)

        if ($exitCode -eq 0 -or $null -eq $exitCode) {
            Write-Host "OK: $name ($duration sec)" -ForegroundColor Green

            return [pscustomobject]@{
                Name = $name
                Path = $path
                Status = "OK"
                ExitCode = "0"
                DurationSec = $duration
            }
        } else {
            Write-Host "ERROR: $name exit $exitCode" -ForegroundColor Red

            return [pscustomobject]@{
                Name = $name
                Path = $path
                Status = "ERROR"
                ExitCode = "$exitCode"
                DurationSec = $duration
            }
        }
    } catch {
        $ended = Get-Date
        $duration = [math]::Round(($ended - $started).TotalSeconds, 2)

        $script:childLogLines += ""
        $script:childLogLines += "ERROR STEP: $name"
        $script:childLogLines += "$($_.Exception.Message)"

        Write-Host "ERROR: $name" -ForegroundColor Red
        Write-Host $_.Exception.Message

        return [pscustomobject]@{
            Name = $name
            Path = $path
            Status = "ERROR"
            ExitCode = "1"
            DurationSec = $duration
        }
    }
}

function Read-JsonSafe($path) {
    if (!(Test-Path $path)) { return $null }
    try { return Get-Content $path -Raw | ConvertFrom-Json }
    catch { return $null }
}

function Safe-Csv($path) {
    if (!(Test-Path $path)) { return @() }
    try { return @(Import-Csv $path) }
    catch { return @() }
}

function Get-Val($row, $names) {
    if ($null -eq $row) { return "" }

    foreach ($n in @($names)) {
        $p = $row.PSObject.Properties[$n]
        if ($null -ne $p -and $null -ne $p.Value -and "$($p.Value)".Trim() -ne "") {
            return "$($p.Value)".Trim()
        }
    }

    return ""
}

$runSteps = @()

$runSteps += ,(Run-StepClean "217 client safe official gate" (Join-Path $scripts "217_client_safe_official_gate.ps1"))
$runSteps += ,(Run-StepClean "219 client safe public board" (Join-Path $scripts "219_build_client_safe_public_board.ps1"))
$runSteps += ,(Run-StepClean "220 client safe ranker repair" (Join-Path $scripts "220_repair_ranker_model_probability_client_safe.ps1"))
$runSteps += ,(Run-StepClean "224 lineup-aware client policy" (Join-Path $scripts "224_lineup_aware_client_policy.ps1"))

$childLogLines | Set-Content -Encoding UTF8 $outChildLog

$policyJsonPath = Join-Path $astro "ASTRODDS-lineup-aware-client-policy-latest.json"
$policyCsvPath  = Join-Path $astro "ASTRODDS-lineup-aware-client-policy-latest.csv"

$policy = Read-JsonSafe $policyJsonPath
$policyRows = Safe-Csv $policyCsvPath

$clientDecision = ""
if ($null -ne $policy -and $policy.clientDecision) {
    $clientDecision = "$($policy.clientDecision)"
}

if ($clientDecision -eq "") {
    $clientDecision = "CLIENT_DROP_BLOCKED"
}

$sendOkRows = @($policyRows | Where-Object {
    (Get-Val $_ @("FinalDecision")) -eq "CLIENT_OFFICIAL_SEND_OK"
})

$reviewRows = @($policyRows | Where-Object {
    (Get-Val $_ @("FinalDecision")) -eq "REVIEW_ONLY"
})

$blockedRows = @($policyRows | Where-Object {
    (Get-Val $_ @("FinalDecision")) -eq "BLOCKED_FOR_REVIEW"
})

$telegramLines = @()

if ($clientDecision -eq "CLIENT_DROP_ALLOWED" -and $sendOkRows.Count -gt 0) {
    $telegramLines += "🚀 ASTRODDS OFFICIAL PICKS"
    $telegramLines += "MLB MONEYLINE ONLY"
    $telegramLines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
    $telegramLines += ""
    $telegramLines += "Rules:"
    $telegramLines += "• No parlays"
    $telegramLines += "• 5% bankroll max"
    $telegramLines += "• Only client-safe confirmed picks"
    $telegramLines += ""

    $i = 1
    foreach ($r in $sendOkRows) {
        $telegramLines += "✅ OFFICIAL BUY #$i"
        $telegramLines += "$(Get-Val $r @('Pick')) ML"
        $telegramLines += "Game: $(Get-Val $r @('Game'))"
        $telegramLines += "Entry: $(Get-Val $r @('Price'))"
        $telegramLines += "Model: $(Get-Val $r @('ModelProbability'))"
        $telegramLines += "Edge: $(Get-Val $r @('Edge'))"
        $telegramLines += "Why: passed model, market, full slate, and live lineup gates."
        $telegramLines += ""
        $i++
    }

    $telegramLines += "⚠️ Risk note:"
    $telegramLines += "These are data-driven value spots, not guaranteed wins."
    $telegramLines += ""
    $telegramLines += "ASTRODDS"
} else {
    $telegramLines += "🚫 ASTRODDS CLIENT DROP BLOCKED"
    $telegramLines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
    $telegramLines += ""
    $telegramLines += "No official client picks will be sent."
    $telegramLines += ""
    $telegramLines += "Reason:"
    $telegramLines += "• Client decision: $clientDecision"
    $telegramLines += "• SEND_OK picks: $($sendOkRows.Count)"
    $telegramLines += "• REVIEW_ONLY picks: $($reviewRows.Count)"
    $telegramLines += "• BLOCKED picks: $($blockedRows.Count)"
    $telegramLines += ""

    if ($blockedRows.Count -gt 0) {
        $telegramLines += "Blocked details:"
        foreach ($r in $blockedRows) {
            $telegramLines += "- $(Get-Val $r @('Pick')) | $(Get-Val $r @('Game'))"
            $telegramLines += "  Lineups: away=$(Get-Val $r @('AwayLineupStatus')) home=$(Get-Val $r @('HomeLineupStatus'))"

            $hb = Get-Val $r @("HardBlocks")
            $wr = Get-Val $r @("Warnings")

            if ($hb -ne "") { $telegramLines += "  Hard blocks: $hb" }
            if ($wr -ne "") { $telegramLines += "  Warnings: $wr" }
        }
        $telegramLines += ""
    }

    $telegramLines += "Action:"
    $telegramLines += "Wait for clean live lineups and clean calibrated model connection before official Telegram picks."
}

$telegramMessage = $telegramLines -join [Environment]::NewLine
$telegramMessage | Set-Content -Encoding UTF8 $outTelegram

$reportLines = @()
$reportLines += "ASTRODDS 225B DAILY SAFE RUNNER CLEAN"
$reportLines += ""
$reportLines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$reportLines += "Client decision: $clientDecision"
$reportLines += "SEND_OK: $($sendOkRows.Count)"
$reportLines += "REVIEW_ONLY: $($reviewRows.Count)"
$reportLines += "BLOCKED: $($blockedRows.Count)"
$reportLines += ""
$reportLines += "STEPS"

foreach ($s in $runSteps) {
    $reportLines += "- $($s.Name): $($s.Status) | Exit=$($s.ExitCode) | Duration=$($s.DurationSec)s"
}

$reportLines += ""
$reportLines += "CHILD LOG"
$reportLines += $outChildLog
$reportLines += ""
$reportLines += "TELEGRAM OUTPUT"
$reportLines += $outTelegram
$reportLines += ""
$reportLines += "FINAL MESSAGE"
$reportLines += $telegramMessage

$report = [pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    clientDecision = $clientDecision
    sendOk = $sendOkRows.Count
    reviewOnly = $reviewRows.Count
    blocked = $blockedRows.Count
    steps = @($runSteps)
    childLog = $outChildLog
    telegramOutput = $outTelegram
}

$report | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 $outJson
($reportLines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($reportLines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output JSON: $outJson"
Write-Host "Child log: $outChildLog"
Write-Host "Telegram/blocked message: $outTelegram"
Write-Host ""
