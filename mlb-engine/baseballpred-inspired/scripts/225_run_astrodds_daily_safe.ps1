$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
$scripts = Join-Path $root "mlb-engine\baseballpred-inspired\scripts"

$outTxt  = Join-Path $astro "ASTRODDS-daily-safe-run-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-daily-safe-run-latest.json"
$outTelegram = Join-Path $astro "ASTRODDS-telegram-client-safe-final-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 225 DAILY SAFE RUNNER" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - CLIENT SAFE PIPELINE" -ForegroundColor Cyan
Write-Host ""

function Run-Step($name, $path) {
    Write-Host ""
    Write-Host "Running $name..." -ForegroundColor Cyan

    if (!(Test-Path $path)) {
        Write-Host "SKIP: Missing script $path" -ForegroundColor Yellow
        return [pscustomobject]@{
            Name = $name
            Path = $path
            Status = "MISSING"
            ExitCode = ""
        }
    }

    try {
        powershell -ExecutionPolicy Bypass -File $path
        return [pscustomobject]@{
            Name = $name
            Path = $path
            Status = "OK"
            ExitCode = "0"
        }
    } catch {
        Write-Host "ERROR in $name" -ForegroundColor Red
        Write-Host $_.Exception.Message
        return [pscustomobject]@{
            Name = $name
            Path = $path
            Status = "ERROR"
            ExitCode = "1"
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

$runSteps += Run-Step "217 client safe official gate" (Join-Path $scripts "217_client_safe_official_gate.ps1")
$runSteps += Run-Step "219 client safe public board" (Join-Path $scripts "219_build_client_safe_public_board.ps1")
$runSteps += Run-Step "220 client safe ranker repair" (Join-Path $scripts "220_repair_ranker_model_probability_client_safe.ps1")
$runSteps += Run-Step "224 lineup-aware client policy" (Join-Path $scripts "224_lineup_aware_client_policy.ps1")

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
    $telegramLines += "Action:"
    $telegramLines += "Wait for clean live lineups and clean calibrated model connection before official Telegram picks."
}

$telegramMessage = $telegramLines -join [Environment]::NewLine
$telegramMessage | Set-Content -Encoding UTF8 $outTelegram

$reportLines = @()
$reportLines += "ASTRODDS 225 DAILY SAFE RUNNER"
$reportLines += ""
$reportLines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$reportLines += "Client decision: $clientDecision"
$reportLines += "SEND_OK: $($sendOkRows.Count)"
$reportLines += "REVIEW_ONLY: $($reviewRows.Count)"
$reportLines += "BLOCKED: $($blockedRows.Count)"
$reportLines += ""
$reportLines += "STEPS"
foreach ($s in $runSteps) {
    $reportLines += "- $($s.Name): $($s.Status)"
}
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
    steps = $runSteps
    telegramOutput = $outTelegram
}

$report | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 $outJson
($reportLines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($reportLines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output JSON: $outJson"
Write-Host "Telegram/blocked message: $outTelegram"
Write-Host ""
