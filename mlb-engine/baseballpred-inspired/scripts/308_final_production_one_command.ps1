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
$scripts = Join-Path $root "mlb-engine\baseballpred-inspired\scripts"
Ensure-Dir $astro
Load-EnvLocal $root

$outTxt = Join-Path $astro "ASTRODDS-308-FINAL-PRODUCTION-ONE-COMMAND-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-308-FINAL-PRODUCTION-ONE-COMMAND-latest.json"
$outChildLog = Join-Path $astro "ASTRODDS-308-child-log-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 308 FINAL PRODUCTION ONE COMMAND" -ForegroundColor Cyan
Write-Host "Final flow: env doctor -> elite runner -> credit dashboard -> reports -> readiness." -ForegroundColor Cyan
Write-Host ""

$childLog = @()
$ref = [ref]$childLog

$run = @(
    @{Name="307 env config doctor"; Path=Join-Path $scripts "307_final_env_config_doctor.ps1"},
    @{Name="324 elite factors runner"; Path=Join-Path $scripts "324_run_elite_factors_runner.ps1"},
    @{Name="310 credit budget dashboard"; Path=Join-Path $scripts "310_credit_budget_dashboard.ps1"},
    @{Name="309 client/admin report builder"; Path=Join-Path $scripts "309_client_admin_report_builder.ps1"},
    @{Name="312 final readiness gate"; Path=Join-Path $scripts "312_final_readiness_gate.ps1"}
)

$steps = @()
foreach ($s in $run) { $steps += ,(Run-Step $s.Name $s.Path $ref) }

$childLog | Set-Content -Encoding UTF8 $outChildLog

$readinessPath = Join-Path $astro "ASTRODDS-312-final-readiness-gate-latest.txt"
$clientPath = Join-Path $astro "ASTRODDS-FINAL-client-summary-latest.txt"
$adminPath = Join-Path $astro "ASTRODDS-FINAL-admin-report-latest.txt"
$readiness = ""
$client = ""
if (Test-Path $readinessPath) { $readiness = Get-Content $readinessPath -Raw }
if (Test-Path $clientPath) { $client = Get-Content $clientPath -Raw }

$lines = @()
$lines += "ASTRODDS 308 FINAL PRODUCTION ONE COMMAND"
$lines += ""
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$lines += ""
$lines += "STEPS"
foreach ($s in $steps) { $lines += "- $($s.Name): $($s.Status) | Exit=$($s.ExitCode) | Duration=$($s.DurationSec)s" }
$lines += ""
$lines += "READINESS"
$lines += $readiness
$lines += ""
$lines += "CLIENT SUMMARY"
$lines += $client
$lines += ""
$lines += "FILES"
$lines += "- Client report: $clientPath"
$lines += "- Admin report: $adminPath"
$lines += "- Child log: $outChildLog"

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    steps=@($steps)
    readinessFile=$readinessPath
    clientReport=$clientPath
    adminReport=$adminPath
    childLog=$outChildLog
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
