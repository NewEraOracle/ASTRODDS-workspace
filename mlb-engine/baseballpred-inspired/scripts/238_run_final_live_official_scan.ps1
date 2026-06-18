$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
$scripts = Join-Path $root "mlb-engine\baseballpred-inspired\scripts"

$script228 = Join-Path $scripts "228_smart_live_lineup_gate_active_date.ps1"
$script235 = Join-Path $scripts "235_schedule_first_full_slate_control_board.ps1"
$script236 = Join-Path $scripts "236_evaluate_all_context_rows_smart_gate.ps1"
$script237 = Join-Path $scripts "237_final_reconciled_official_gate.ps1"

$finalGateCsv = Join-Path $astro "ASTRODDS-final-reconciled-official-gate-latest.csv"
$finalTelegram = Join-Path $astro "ASTRODDS-telegram-final-reconciled-official-latest.txt"

$ledgerCsv = Join-Path $astro "ASTRODDS-official-picks-ledger-latest.csv"
$ledgerJson = Join-Path $astro "ASTRODDS-official-picks-ledger-latest.json"

$outTxt = Join-Path $astro "ASTRODDS-final-live-official-scan-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-final-live-official-scan-latest.json"
$outChildLog = Join-Path $astro "ASTRODDS-final-live-official-scan-child-log-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 238 FINAL LIVE OFFICIAL SCAN" -ForegroundColor Cyan
Write-Host "LIVE LINEUPS + FULL SLATE + FINAL RECONCILED GATE + LEDGER" -ForegroundColor Cyan
Write-Host ""

$childLog = @()

function Run-Step($name, $path) {
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

        $script:childLog += ""
        $script:childLog += "ERROR STEP: $name"
        $script:childLog += "$($_.Exception.Message)"

        Write-Host "ERROR: $name" -ForegroundColor Red
        Write-Host $_.Exception.Message

        return [pscustomobject]@{
            Name = $name
            Status = "ERROR"
            ExitCode = "1"
            DurationSec = $duration
        }
    }
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

function Make-LedgerKey($r) {
    $game = Get-Val $r @("Game")
    $pick = Get-Val $r @("Pick")
    $entry = Get-Val $r @("Price")
    $date = Get-Date -Format "yyyy-MM-dd"
    return "$date|$game|$pick|$entry".ToLower()
}

$steps = @()
$steps += ,(Run-Step "228 smart live lineup gate" $script228)
$steps += ,(Run-Step "235 schedule-first full slate board" $script235)
$steps += ,(Run-Step "236 all-context smart gate" $script236)
$steps += ,(Run-Step "237 final reconciled official gate" $script237)

$childLog | Set-Content -Encoding UTF8 $outChildLog

$finalRows = Safe-Csv $finalGateCsv

$officialRows = @($finalRows | Where-Object {
    (Get-Val $_ @("FinalDecision")) -eq "CLIENT_OFFICIAL_SEND_OK"
})

$reviewContextRows = @($finalRows | Where-Object {
    (Get-Val $_ @("FinalDecision")) -eq "REVIEW_ONLY_CONTEXT"
})

$reviewRows = @($finalRows | Where-Object {
    (Get-Val $_ @("FinalDecision")) -eq "REVIEW_ONLY"
})

$blockedRows = @($finalRows | Where-Object {
    (Get-Val $_ @("FinalDecision")) -eq "BLOCKED_FOR_REVIEW"
})

$clientDecision = "CLIENT_DROP_BLOCKED"
if ($officialRows.Count -gt 0) {
    if ($blockedRows.Count -gt 0 -or $reviewRows.Count -gt 0 -or $reviewContextRows.Count -gt 0) {
        $clientDecision = "CLIENT_DROP_PARTIAL_ALLOWED"
    } else {
        $clientDecision = "CLIENT_DROP_ALLOWED"
    }
}

$existingLedger = Safe-Csv $ledgerCsv
$seen = @{}

foreach ($old in $existingLedger) {
    $key = Get-Val $old @("LedgerKey")
    if ($key -ne "") {
        $seen[$key] = $true
    }
}

$newLedgerRows = @()

foreach ($r in $officialRows) {
    $key = Make-LedgerKey $r

    if ($seen.ContainsKey($key)) {
        continue
    }

    $newLedgerRows += ,[pscustomobject]@{
        LedgerKey = $key
        LoggedAt = (Get-Date).ToString("o")
        Status = "PENDING_RESULT"
        Sport = "MLB"
        MarketType = "MONEYLINE"
        Pick = Get-Val $r @("Pick")
        Game = Get-Val $r @("Game")
        MlbStatusAtLog = Get-Val $r @("MlbStatus")
        EntryPrice = Get-Val $r @("Price")
        ModelProbability = Get-Val $r @("ModelProbability")
        MarketProbability = Get-Val $r @("MarketProbability")
        Edge = Get-Val $r @("Edge")
        Stake = "5% bankroll max"
        AwayLineupStatus = Get-Val $r @("AwayLineupStatus")
        HomeLineupStatus = Get-Val $r @("HomeLineupStatus")
        Result = ""
        Winner = ""
        FinalScore = ""
        ClosingPrice = ""
        CLV = ""
        ROI = ""
        BrierComponent = ""
        LogLossComponent = ""
        SourceGate = "ASTRODDS-final-reconciled-official-gate-latest.csv"
        TelegramFile = $finalTelegram
    }

    $seen[$key] = $true
}

$combinedLedger = @()
$combinedLedger += @($existingLedger)
$combinedLedger += @($newLedgerRows)

$combinedLedger | Export-Csv -NoTypeInformation -Encoding UTF8 $ledgerCsv
$combinedLedger | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 $ledgerJson

$telegramText = ""
if (Test-Path $finalTelegram) {
    $telegramText = Get-Content $finalTelegram -Raw
}

$lines = @()
$lines += "ASTRODDS 238 FINAL LIVE OFFICIAL SCAN"
$lines += ""
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$lines += "Client decision: $clientDecision"
$lines += "OFFICIAL SEND_OK: $($officialRows.Count)"
$lines += "REVIEW_CONTEXT: $($reviewContextRows.Count)"
$lines += "REVIEW_ONLY: $($reviewRows.Count)"
$lines += "BLOCKED: $($blockedRows.Count)"
$lines += "New ledger rows logged: $($newLedgerRows.Count)"
$lines += ""

$lines += "STEPS"
foreach ($s in $steps) {
    $lines += "- $($s.Name): $($s.Status) | Exit=$($s.ExitCode) | Duration=$($s.DurationSec)s"
}
$lines += ""

$lines += "OFFICIAL PICKS"
if ($officialRows.Count -eq 0) {
    $lines += "- None"
} else {
    foreach ($r in $officialRows) {
        $lines += "- $(Get-Val $r @('Pick')) | $(Get-Val $r @('Game')) | Entry=$(Get-Val $r @('Price')) | Model=$(Get-Val $r @('ModelProbability')) | Edge=$(Get-Val $r @('Edge'))"
    }
}
$lines += ""

$lines += "REVIEW CONTEXT"
if ($reviewContextRows.Count -eq 0) {
    $lines += "- None"
} else {
    foreach ($r in $reviewContextRows) {
        $lines += "- $(Get-Val $r @('Pick')) | $(Get-Val $r @('Game')) | Model=$(Get-Val $r @('ModelProbability')) | Edge=$(Get-Val $r @('Edge'))"
        $wr = Get-Val $r @("Warnings")
        if ($wr -ne "") { $lines += "  Warn: $wr" }
    }
}
$lines += ""

$lines += "BLOCKED SAMPLE"
foreach ($r in ($blockedRows | Select-Object -First 12)) {
    $lines += "- $(Get-Val $r @('Pick')) | $(Get-Val $r @('Game'))"
    $hb = Get-Val $r @("HardBlocks")
    $reason = Get-Val $r @("FinalReason")
    if ($hb -ne "") { $lines += "  Hard: $hb" }
    if ($reason -ne "") { $lines += "  Reason: $reason" }
}
if ($blockedRows.Count -gt 12) {
    $lines += "- ... plus $($blockedRows.Count - 12) blocked rows"
}
$lines += ""

$lines += "TELEGRAM FILE"
$lines += $finalTelegram
$lines += ""

$lines += "LEDGER"
$lines += "CSV: $ledgerCsv"
$lines += "JSON: $ledgerJson"
$lines += ""

$lines += "FINAL TELEGRAM MESSAGE"
$lines += $telegramText

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    clientDecision = $clientDecision
    officialSendOk = $officialRows.Count
    reviewContext = $reviewContextRows.Count
    reviewOnly = $reviewRows.Count
    blocked = $blockedRows.Count
    newLedgerRowsLogged = $newLedgerRows.Count
    steps = @($steps)
    finalTelegram = $finalTelegram
    ledgerCsv = $ledgerCsv
    childLog = $outChildLog
} | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output JSON: $outJson"
Write-Host "Child log: $outChildLog"
Write-Host "Telegram: $finalTelegram"
Write-Host "Ledger CSV: $ledgerCsv"
Write-Host ""
