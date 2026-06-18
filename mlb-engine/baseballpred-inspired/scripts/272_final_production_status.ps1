$ErrorActionPreference = "Continue"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$outTxt = Join-Path $astro "ASTRODDS-272-final-production-status-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-272-final-production-status-latest.json"

Write-Host ""
Write-Host "ASTRODDS 272 FINAL PRODUCTION STATUS" -ForegroundColor Cyan
Write-Host ""


function Safe-Csv($path) {
    if (!(Test-Path $path)) { return @() }
    try { return @(Import-Csv $path) } catch { return @() }
}

function Get-Val($row, $names) {
    if ($null -eq $row) { return "" }
    foreach ($n in @($names)) {
        try {
            $p = $row.PSObject.Properties[$n]
            if ($null -ne $p -and $null -ne $p.Value) {
                $v = "$($p.Value)".Trim()
                if ($v -ne "") { return $v }
            }
        } catch {}
    }
    return ""
}

$sourceBoard = Safe-Csv (Join-Path $astro "ASTRODDS-source-first-context-board-latest.csv")
$baseline = Safe-Csv (Join-Path $astro "ASTRODDS-265-source-first-baseline-model-latest.csv")
$trustedGate = Safe-Csv (Join-Path $astro "ASTRODDS-249-price-guard-latest.csv")
$newDropGate = Safe-Csv (Join-Path $astro "ASTRODDS-258-block-in-progress-new-drops-latest.csv")
$ledger = Safe-Csv (Join-Path $astro "ASTRODDS-official-picks-ledger-latest.csv")

$sourceRows = $sourceBoard.Count
$baselineRows = $baseline.Count
$trustedSend = @($trustedGate | Where-Object { (Get-Val $_ @("Decision")) -eq "SEND_OK" }).Count
$newDropSend = @($newDropGate | Where-Object { (Get-Val $_ @("FinalDropDecision")) -eq "SEND_OK" }).Count
$newDropBlocked = @($newDropGate | Where-Object { (Get-Val $_ @("FinalDropDecision")) -ne "SEND_OK" }).Count
$pending = @($ledger | Where-Object { (Get-Val $_ @("Status")) -eq "PENDING_RESULT" }).Count
$settled = @($ledger | Where-Object { (Get-Val $_ @("Status")) -eq "SETTLED" }).Count
$wins = @($ledger | Where-Object { (Get-Val $_ @("Result")) -eq "WIN" }).Count
$losses = @($ledger | Where-Object { (Get-Val $_ @("Result")) -eq "LOSS" }).Count

$status = "PRODUCTION_READY"
if ($sourceRows -eq 0) { $status = "SOURCE_FILES_MISSING" }
elseif ($newDropSend -eq 0) { $status = "PRODUCTION_READY_NO_NEW_DROP_NOW" }

$lines = @()
$lines += "ASTRODDS 272 FINAL PRODUCTION STATUS"
$lines += ""
$lines += "Status: $status"
$lines += ""
$lines += "COUNTS"
$lines += "- Source-first board rows: $sourceRows"
$lines += "- Baseline model rows: $baselineRows"
$lines += "- Trusted price-guard SEND_OK rows: $trustedSend"
$lines += "- New-drop SEND_OK rows: $newDropSend"
$lines += "- New-drop blocked rows: $newDropBlocked"
$lines += "- Ledger pending: $pending"
$lines += "- Ledger settled: $settled"
$lines += "- Wins: $wins"
$lines += "- Losses: $losses"
$lines += ""
$lines += "PRODUCTION RULE"
$lines += "- Client Telegram must use the trusted market-connected pipeline."
$lines += "- Source-first baseline model is used for coverage/review, not automatic client official picks."
$lines += "- If games are In Progress, new drops are blocked and ledger only tracks already-sent picks."
$lines += ""
$lines += "FINAL COMMAND"
$lines += 'powershell -ExecutionPolicy Bypass -File ".\mlb-engine\baseballpred-inspired\scripts\271_production_final_router.ps1"'

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    status = $status
    sourceRows = $sourceRows
    baselineRows = $baselineRows
    trustedSendOkRows = $trustedSend
    newDropSendOkRows = $newDropSend
    newDropBlockedRows = $newDropBlocked
    ledgerPending = $pending
    ledgerSettled = $settled
    wins = $wins
    losses = $losses
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
