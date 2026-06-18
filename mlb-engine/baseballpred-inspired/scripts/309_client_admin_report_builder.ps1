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

function Num($v) {
    if ($null -eq $v) { return $null }
    $s = "$v".Trim()
    if ($s -eq "") { return $null }
    $s = $s.Replace("%","").Replace("¢","").Replace(",", ".")
    $n = 0.0
    $culture = [System.Globalization.CultureInfo]::InvariantCulture
    if ([double]::TryParse($s, [System.Globalization.NumberStyles]::Any, $culture, [ref]$n)) { return $n }
    return $null
}

function Load-EnvLocal($root) {
    $envFile = Join-Path $root ".env.local"
    if (Test-Path $envFile) {
        Get-Content $envFile | ForEach-Object {
            if ($_ -match "^\s*([^#][A-Za-z0-9_]+)\s*=\s*(.+)\s*$") {
                $name = $matches[1].Trim()
                $value = $matches[2].Trim().Trim('"').Trim("'")
                [Environment]::SetEnvironmentVariable($name, $value, "Process")
            }
        }
    }

    if ($env:THE_ODDS_API_KEY -and -not $env:ODDS_API_KEY) { $env:ODDS_API_KEY = $env:THE_ODDS_API_KEY }
    if ($env:ASTRODDS_ODDS_API_KEY -and -not $env:ODDS_API_KEY) { $env:ODDS_API_KEY = $env:ASTRODDS_ODDS_API_KEY }
    if ($env:ASTRODDS_TELEGRAM_BOT_TOKEN -and -not $env:TELEGRAM_BOT_TOKEN) { $env:TELEGRAM_BOT_TOKEN = $env:ASTRODDS_TELEGRAM_BOT_TOKEN }
    if ($env:ASTRODDS_TELEGRAM_CHAT_ID -and -not $env:TELEGRAM_CHAT_ID) { $env:TELEGRAM_CHAT_ID = $env:ASTRODDS_TELEGRAM_CHAT_ID }
}

function Run-Step($name, $path, [ref]$childLog) {
    $start = Get-Date
    Write-Host "Running $name..." -ForegroundColor Cyan

    if (!(Test-Path $path)) {
        Write-Host "MISSING: $path" -ForegroundColor Yellow
        return [pscustomobject]@{Name=$name;Status="MISSING";ExitCode="";DurationSec=0}
    }

    try {
        $output = & powershell -ExecutionPolicy Bypass -File $path 2>&1
        $exitCode = $LASTEXITCODE
        $duration = [math]::Round(((Get-Date)-$start).TotalSeconds,2)

        $childLog.Value += ""
        $childLog.Value += "============================================================"
        $childLog.Value += "STEP: $name"
        $childLog.Value += "PATH: $path"
        $childLog.Value += "EXIT: $exitCode"
        $childLog.Value += "DURATION: $duration sec"
        $childLog.Value += "============================================================"
        $childLog.Value += @($output | ForEach-Object { "$_" })

        if ($exitCode -eq 0 -or $null -eq $exitCode) {
            Write-Host "OK: $name ($duration sec)" -ForegroundColor Green
            return [pscustomobject]@{Name=$name;Status="OK";ExitCode="0";DurationSec=$duration}
        } else {
            Write-Host "ERROR: $name exit $exitCode" -ForegroundColor Red
            return [pscustomobject]@{Name=$name;Status="ERROR";ExitCode="$exitCode";DurationSec=$duration}
        }
    } catch {
        $duration = [math]::Round(((Get-Date)-$start).TotalSeconds,2)
        $childLog.Value += ""
        $childLog.Value += "ERROR STEP: $name"
        $childLog.Value += "$($_.Exception.Message)"
        Write-Host "ERROR: $name $($_.Exception.Message)" -ForegroundColor Red
        return [pscustomobject]@{Name=$name;Status="ERROR";ExitCode="1";DurationSec=$duration}
    }
}

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$outClient = Join-Path $astro "ASTRODDS-FINAL-client-summary-latest.txt"
$outAdmin = Join-Path $astro "ASTRODDS-FINAL-admin-report-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-309-client-admin-report-builder-latest.json"

Write-Host ""
Write-Host "ASTRODDS 309 CLIENT + ADMIN REPORT BUILDER" -ForegroundColor Cyan
Write-Host ""

$eliteGate = Safe-Csv (Join-Path $astro "ASTRODDS-323-elite-official-gate-latest.csv")
$lineGate = Safe-Csv (Join-Path $astro "ASTRODDS-301-line-shopping-official-gate-latest.csv")
$ledger = Safe-Csv (Join-Path $astro "ASTRODDS-official-picks-ledger-latest.csv")
$eliteReport = Join-Path $astro "ASTRODDS-325-elite-factors-report-latest.txt"
$creditTxt = Join-Path $astro "ASTRODDS-310-credit-budget-dashboard-latest.txt"
$prodMsgFile = Join-Path $astro "ASTRODDS-telegram-PRODUCTION-final-latest.txt"

$send = @($eliteGate | Where-Object { (Get-Val $_ @("FinalEliteDecision")) -eq "CLIENT_OFFICIAL_ELITE_SEND_OK" })
$review = @($eliteGate | Where-Object { (Get-Val $_ @("FinalEliteDecision")) -match "REVIEW" })
$pending = @($ledger | Where-Object { (Get-Val $_ @("Status")) -eq "PENDING_RESULT" })
$settled = @($ledger | Where-Object { (Get-Val $_ @("Status")) -eq "SETTLED" })

$clientLines = @()
$clientLines += "ASTRODDS CLIENT STATUS"
$clientLines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$clientLines += ""
if ($send.Count -gt 0) {
    $clientLines += "🚀 OFFICIAL PICKS READY"
    foreach ($r in $send) {
        $clientLines += "- $((Get-Val $r @('Pick'))) ML | $((Get-Val $r @('Game'))) | Best=$((Get-Val $r @('BestEntry'))) $((Get-Val $r @('BestBook'))) | Model=$((Get-Val $r @('ModelProbability'))) | Edge=$((Get-Val $r @('EdgeVsBest')))"
    }
} else {
    $clientLines += "🚫 No new official picks right now."
    $clientLines += "Reason: no clean value passed all safety gates."
}
$clientLines += ""
$clientLines += "Rules:"
$clientLines += "• MLB moneyline only"
$clientLines += "• No parlays"
$clientLines += "• 5% bankroll max"
$clientLines += "• No picks after game start"
$clientLines += "• External market + line shopping + elite gate required"
$clientLines += ""
$clientLines += "ASTRODDS"
($clientLines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outClient

$adminLines = @()
$adminLines += "ASTRODDS FINAL ADMIN REPORT"
$adminLines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$adminLines += ""
$adminLines += "COUNTS"
$adminLines += "- Elite SEND_OK: $($send.Count)"
$adminLines += "- Elite REVIEW: $($review.Count)"
$adminLines += "- Ledger pending: $($pending.Count)"
$adminLines += "- Ledger settled: $($settled.Count)"
$adminLines += ""
$adminLines += "ELITE GATE"
foreach ($r in ($eliteGate | Select-Object -First 25)) {
    $adminLines += "- $((Get-Val $r @('FinalEliteDecision'))) | $((Get-Val $r @('Pick'))) | $((Get-Val $r @('Game'))) | edge=$((Get-Val $r @('EdgeVsBest'))) | elite=$((Get-Val $r @('EliteContextStatus')))"
    $hb = Get-Val $r @("HardBlocks")
    if ($hb -ne "") { $adminLines += "  Hard=$hb" }
}
$adminLines += ""
if (Test-Path $creditTxt) {
    $adminLines += "CREDIT DASHBOARD"
    $adminLines += (Get-Content $creditTxt -Raw)
}
$adminLines += ""
if (Test-Path $eliteReport) {
    $adminLines += "ELITE REPORT"
    $adminLines += (Get-Content $eliteReport -Raw)
}
$adminLines += ""
$adminLines += "FILES"
$adminLines += "- Client summary: $outClient"
$adminLines += "- Production Telegram: $prodMsgFile"
($adminLines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outAdmin

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    clientReport=$outClient
    adminReport=$outAdmin
    eliteSendOk=$send.Count
    eliteReview=$review.Count
    ledgerPending=$pending.Count
    ledgerSettled=$settled.Count
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

Write-Host "Client report: $outClient"
Write-Host "Admin report: $outAdmin"
exit 0
