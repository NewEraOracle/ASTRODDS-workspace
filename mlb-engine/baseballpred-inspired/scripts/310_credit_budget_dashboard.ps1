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

$creditCsv = Join-Path $astro "ASTRODDS-odds-api-credit-ledger-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-310-credit-budget-dashboard-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-310-credit-budget-dashboard-latest.json"

Write-Host ""
Write-Host "ASTRODDS 310 ODDS CREDIT BUDGET DASHBOARD" -ForegroundColor Cyan
Write-Host ""

$ledger = Safe-Csv $creditCsv
$monthKey = (Get-Date).ToString("yyyy-MM")
$dayKey = (Get-Date).ToString("yyyy-MM-dd")
$monthRows = @($ledger | Where-Object { (Get-Val $_ @("MonthKey")) -eq $monthKey })
$dayRows = @($ledger | Where-Object { (Get-Val $_ @("DayKey")) -eq $dayKey })

$apiCallsMonth = @($monthRows | Where-Object { (Get-Val $_ @("ApiCalled")) -eq "YES" }).Count
$apiCallsDay = @($dayRows | Where-Object { (Get-Val $_ @("ApiCalled")) -eq "YES" }).Count

$estimatedCost = 0
foreach ($r in $monthRows) {
    $c = Num (Get-Val $r @("RequestsLast","EstimatedCost"))
    if ($null -ne $c) { $estimatedCost += [int][math]::Round($c,0) }
}

$monthlyLimit = 500
$reserve = 60
try { if ($env:ASTRODDS_ODDS_MONTHLY_LIMIT) { $monthlyLimit = [int]$env:ASTRODDS_ODDS_MONTHLY_LIMIT } } catch {}
try { if ($env:ASTRODDS_ODDS_RESERVE) { $reserve = [int]$env:ASTRODDS_ODDS_RESERVE } } catch {}

$usable = [math]::Max(0, $monthlyLimit - $reserve)
$remainingLocal = [math]::Max(0, $usable - $estimatedCost)
$status = "OK"
if ($estimatedCost -ge $usable) { $status = "BLOCK_NEW_PAID_ODDS" }
elseif ($remainingLocal -lt 25) { $status = "LOW_CREDIT_RESERVE" }

$last = @($ledger | Sort-Object FetchedAt -Descending | Select-Object -First 1)

$lines = @()
$lines += "ASTRODDS 310 ODDS CREDIT BUDGET DASHBOARD"
$lines += ""
$lines += "Status: $status"
$lines += "Month: $monthKey"
$lines += "Monthly limit: $monthlyLimit"
$lines += "Reserve: $reserve"
$lines += "Usable budget: $usable"
$lines += "Estimated local credits used: $estimatedCost"
$lines += "Estimated usable remaining: $remainingLocal"
$lines += "API calls this month: $apiCallsMonth"
$lines += "API calls today: $apiCallsDay"
if ($last.Count -gt 0) {
    $lines += ""
    $lines += "Last ledger row:"
    $lines += "- FetchedAt=$((Get-Val $last[0] @('FetchedAt')))"
    $lines += "- ApiCalled=$((Get-Val $last[0] @('ApiCalled')))"
    $lines += "- Status=$((Get-Val $last[0] @('Status')))"
    $lines += "- RequestsRemainingHeader=$((Get-Val $last[0] @('RequestsRemainingHeader')))"
    $lines += "- GuardReasons=$((Get-Val $last[0] @('GuardReasons')))"
}

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    status=$status
    monthKey=$monthKey
    monthlyLimit=$monthlyLimit
    reserve=$reserve
    usableBudget=$usable
    estimatedCreditsUsed=$estimatedCost
    estimatedUsableRemaining=$remainingLocal
    apiCallsThisMonth=$apiCallsMonth
    apiCallsToday=$apiCallsDay
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
