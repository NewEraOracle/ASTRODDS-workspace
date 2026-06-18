$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$guardCsv = Join-Path $astro "ASTRODDS-249-price-guard-latest.csv"
$ledgerCsv = Join-Path $astro "ASTRODDS-official-picks-ledger-latest.csv"
$contextCsv = Join-Path $astro "ASTRODDS-248-context-merged-confidence-latest.csv"

$outTxt = Join-Path $astro "ASTRODDS-252-final-status-board-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-252-final-status-board-latest.json"

Write-Host ""
Write-Host "ASTRODDS 252 FINAL STATUS BOARD" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - BOT HEALTH / PICKS / LEDGER" -ForegroundColor Cyan
Write-Host ""

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

$guardRows = Safe-Csv $guardCsv
$ledgerRows = Safe-Csv $ledgerCsv
$contextRows = Safe-Csv $contextCsv

$sendOk = @($guardRows | Where-Object { (Get-Val $_ @("Decision")) -eq "SEND_OK" }).Count
$blockedPrice = @($guardRows | Where-Object { (Get-Val $_ @("Decision")) -ne "SEND_OK" }).Count

$pending = @($ledgerRows | Where-Object { (Get-Val $_ @("Status")) -eq "PENDING_RESULT" }).Count
$settled = @($ledgerRows | Where-Object { (Get-Val $_ @("Status")) -eq "SETTLED" }).Count
$wins = @($ledgerRows | Where-Object { (Get-Val $_ @("Result")) -eq "WIN" }).Count
$losses = @($ledgerRows | Where-Object { (Get-Val $_ @("Result")) -eq "LOSS" }).Count

$fullContext = @($contextRows | Where-Object { (Get-Val $_ @("ContextStatus")) -eq "FULL_CONTEXT_CONNECTED" }).Count
$partialContext = @($contextRows | Where-Object { (Get-Val $_ @("ContextStatus")) -ne "FULL_CONTEXT_CONNECTED" }).Count

$lines = @()
$lines += "ASTRODDS 252 FINAL STATUS BOARD"
$lines += ""
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$lines += ""
$lines += "BOT STATUS"
$lines += "- Client-ready picks after price guard: $sendOk"
$lines += "- Price blocked/review picks: $blockedPrice"
$lines += "- Full-context official picks: $fullContext"
$lines += "- Partial-context official picks: $partialContext"
$lines += "- Ledger pending: $pending"
$lines += "- Ledger settled: $settled"
$lines += "- Wins: $wins"
$lines += "- Losses: $losses"
$lines += ""
$lines += "CURRENT CLIENT-READY PICKS"
if ($guardRows.Count -eq 0) {
    $lines += "- None"
} else {
    foreach ($r in $guardRows) {
        $lines += "- $(Get-Val $r @('Decision')) | $(Get-Val $r @('Grade')) | $(Get-Val $r @('Pick')) | $(Get-Val $r @('Game')) | Entry=$(Get-Val $r @('CurrentEntry')) | Confidence=$(Get-Val $r @('Confidence'))/100"
    }
}
$lines += ""
$lines += "LEDGER"
foreach ($r in $ledgerRows) {
    $lines += "- $(Get-Val $r @('Status')) | $(Get-Val $r @('Result')) | $(Get-Val $r @('Pick')) | $(Get-Val $r @('Game')) | ROI=$(Get-Val $r @('ROI'))"
}

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    clientReadyPicks = $sendOk
    priceBlockedOrReview = $blockedPrice
    fullContextPicks = $fullContext
    partialContextPicks = $partialContext
    ledgerPending = $pending
    ledgerSettled = $settled
    wins = $wins
    losses = $losses
} | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output JSON: $outJson"
Write-Host ""
