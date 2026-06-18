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

$outTxt = Join-Path $astro "ASTRODDS-312-final-readiness-gate-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-312-final-readiness-gate-latest.json"

Write-Host ""
Write-Host "ASTRODDS 312 FINAL READINESS GATE" -ForegroundColor Cyan
Write-Host ""

$envDoc = $null
try { $envDoc = Get-Content (Join-Path $astro "ASTRODDS-307-final-env-config-doctor-latest.json") -Raw | ConvertFrom-Json } catch {}
$credit = $null
try { $credit = Get-Content (Join-Path $astro "ASTRODDS-310-credit-budget-dashboard-latest.json") -Raw | ConvertFrom-Json } catch {}
$elite = $null
try { $elite = Get-Content (Join-Path $astro "ASTRODDS-325-elite-factors-report-latest.json") -Raw | ConvertFrom-Json } catch {}
$train = $null
try { $train = Get-Content (Join-Path $astro "ASTRODDS-322-train-model-when-ready-policy-latest.json") -Raw | ConvertFrom-Json } catch {}

$blocks = @()
$warn = @()

if ($null -eq $envDoc -or -not $envDoc.ready) { $blocks += "environment/scripts not ready" }
if ($null -ne $credit -and $credit.status -eq "BLOCK_NEW_PAID_ODDS") { $blocks += "odds credit guard blocking paid odds" }
if ($null -eq $elite) { $warn += "elite report missing" }
else {
    if ($elite.pitcherConnectedRows -lt 1) { $blocks += "starter advanced metrics not connected" }
    if ($elite.bullpenRows -lt 1) { $blocks += "enhanced bullpen not connected" }
    if ($elite.umpireConnectedRows -eq 0) { $warn += "umpire source not connected; slot ready" }
    if ($elite.platoonConnectedRows -eq 0) { $warn += "platoon source not connected; slot ready" }
}
if ($null -ne $train -and $train.mode -eq "NO_TRAIN_NOT_ENOUGH_SETTLED_RESULTS") { $warn += "trained model not promoted yet; not enough settled picks" }

$status = "PRODUCTION_READY_SAFE_MODE"
if ($blocks.Count -gt 0) { $status = "NOT_READY_BLOCKED" }
elseif ($warn.Count -gt 0) { $status = "PRODUCTION_READY_WITH_WARNINGS" }

$lines = @()
$lines += "ASTRODDS 312 FINAL READINESS GATE"
$lines += ""
$lines += "Status: $status"
$lines += ""
$lines += "Hard blocks:"
if ($blocks.Count -eq 0) { $lines += "- none" } else { foreach ($b in $blocks) { $lines += "- $b" } }
$lines += ""
$lines += "Warnings:"
if ($warn.Count -eq 0) { $lines += "- none" } else { foreach ($w in $warn) { $lines += "- $w" } }
$lines += ""
$lines += "Decision:"
if ($status -eq "NOT_READY_BLOCKED") {
    $lines += "- Do not sell as automated production yet."
} else {
    $lines += "- Bot is safe to run/sell as MLB Moneyline value-alert system with clear disclaimers."
    $lines += "- Do not claim guaranteed wins."
    $lines += "- Keep Telegram auto-send dry-run until you trust the next live slate."
}

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    status=$status
    hardBlocks=@($blocks)
    warnings=@($warn)
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
