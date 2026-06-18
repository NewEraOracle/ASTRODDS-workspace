$ErrorActionPreference = "Continue"

function Ensure-Dir($path) {
    if (!(Test-Path $path)) { New-Item -ItemType Directory -Force -Path $path | Out-Null }
}

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

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$ledgerCsv = Join-Path $astro "ASTRODDS-official-picks-ledger-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-349-settlement-integrity-report-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-349-settlement-integrity-report-latest.json"

Write-Host ""
Write-Host "ASTRODDS 349 SETTLEMENT INTEGRITY REPORT" -ForegroundColor Cyan
Write-Host ""

$ledger = Safe-Csv $ledgerCsv
$pending = @($ledger | Where-Object { (Get-Val $_ @("Status")) -eq "PENDING_RESULT" })
$settled = @($ledger | Where-Object { (Get-Val $_ @("Status")) -eq "SETTLED" })
$wins = @($settled | Where-Object { (Get-Val $_ @("Result")) -eq "WIN" })
$losses = @($settled | Where-Object { (Get-Val $_ @("Result")) -eq "LOSS" })

$winRate = "N/A"
if ($settled.Count -gt 0) {
    $winRate = ([math]::Round(($wins.Count / $settled.Count) * 100.0, 1)).ToString() + "%"
}

$lines = @()
$lines += "ASTRODDS 349 SETTLEMENT INTEGRITY REPORT"
$lines += ""
$lines += "Ledger rows: $($ledger.Count)"
$lines += "Pending: $($pending.Count)"
$lines += "Settled: $($settled.Count)"
$lines += "Wins: $($wins.Count)"
$lines += "Losses: $($losses.Count)"
$lines += "Win rate settled: $winRate"
$lines += ""
$lines += "SETTLED PICKS"
foreach ($r in $settled) {
    $lines += "- $((Get-Val $r @('Result'))) | $((Get-Val $r @('Pick'))) | $((Get-Val $r @('Game'))) | Winner=$((Get-Val $r @('Winner'))) | Final=$((Get-Val $r @('FinalScore'))) | ROI=$((Get-Val $r @('ROI')))"
}
$lines += ""
$lines += "PENDING PICKS"
foreach ($r in $pending) {
    $lines += "- $((Get-Val $r @('Pick'))) | $((Get-Val $r @('Game'))) | MlbStatus=$((Get-Val $r @('MlbStatusAtSettleCheck','MlbStatusAtLog')))"
}

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    ledgerRows=$ledger.Count
    pending=$pending.Count
    settled=$settled.Count
    wins=$wins.Count
    losses=$losses.Count
    winRateSettled=$winRate
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
