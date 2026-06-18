param(
    [switch]$NoStartServer
)

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

function Normalize-Name($s) {
    $x = "$s".ToLower().Trim()
    $x = $x -replace "[^a-z0-9 ]", ""
    $x = $x -replace "\s+", " "
    return $x
}

function Read-JsonSafe($path) {
    if (!(Test-Path $path)) { return $null }
    try { return Get-Content $path -Raw | ConvertFrom-Json } catch { return $null }
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
        $exit = $LASTEXITCODE
        $dur = [math]::Round(((Get-Date)-$start).TotalSeconds,2)

        $childLog.Value += ""
        $childLog.Value += "============================================================"
        $childLog.Value += "STEP: $name"
        $childLog.Value += "PATH: $path"
        $childLog.Value += "EXIT: $exit"
        $childLog.Value += "DURATION: $dur sec"
        $childLog.Value += "============================================================"
        $childLog.Value += @($output | ForEach-Object { "$_" })

        if ($exit -eq 0 -or $null -eq $exit) {
            Write-Host "OK: $name ($dur sec)" -ForegroundColor Green
            return [pscustomobject]@{Name=$name;Status="OK";ExitCode="0";DurationSec=$dur}
        } else {
            Write-Host "ERROR: $name ($exit)" -ForegroundColor Red
            return [pscustomobject]@{Name=$name;Status="ERROR";ExitCode="$exit";DurationSec=$dur}
        }
    } catch {
        $dur = [math]::Round(((Get-Date)-$start).TotalSeconds,2)
        $childLog.Value += ""
        $childLog.Value += "ERROR STEP: $name"
        $childLog.Value += "$($_.Exception.Message)"
        return [pscustomobject]@{Name=$name;Status="ERROR";ExitCode="1";DurationSec=$dur}
    }
}

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
$scripts = Join-Path $root "mlb-engine\baseballpred-inspired\scripts"
Ensure-Dir $astro

$outTxt = Join-Path $astro "ASTRODDS-338-AUTOPILOT-SERVER-SCAN-CYCLE-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-338-AUTOPILOT-SERVER-SCAN-CYCLE-latest.json"
$outChild = Join-Path $astro "ASTRODDS-338-child-log-latest.txt"
$heartbeat = Join-Path $astro "ASTRODDS-338-heartbeat-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 338H AUTOPILOT SERVER + 2:30AM REPORT + REAL PREMIUM FINISH" -ForegroundColor Cyan
Write-Host ""

$child = @()
$ref = [ref]$child
$steps = @()

if (-not $NoStartServer) {
    $steps += ,(Run-Step "336 start server legacy mode" (Join-Path $scripts "336_start_server_legacy_mode.ps1") $ref)
}

$steps += ,(Run-Step "328 env autofinder" (Join-Path $scripts "328_env_autofinder_loader.ps1") $ref)

$runtime = Join-Path $astro "ASTRODDS-runtime-env-loader.ps1"
$envSource = ""
if (Test-Path $runtime) {
    . $runtime
    $envSource = Load-AstroddsRuntimeEnv $root
}

$steps += ,(Run-Step "337 smart scan window planner" (Join-Path $scripts "337_smart_scan_window_planner.ps1") $ref)

$plannerJson = Join-Path $astro "ASTRODDS-337-smart-scan-window-planner-latest.json"
$globalAction = "UNKNOWN"
try {
    $plan = Get-Content $plannerJson -Raw | ConvertFrom-Json
    $globalAction = "$($plan.globalAction)"
} catch {}

if ($globalAction -eq "RUN_FULL_PRODUCTION_SCAN") {
    $steps += ,(Run-Step "329 final production with env autoload + sync" (Join-Path $scripts "329_run_final_with_env_autoload.ps1") $ref)
} else {
    $steps += ,(Run-Step "351 final sync + 2:30AM + real premium finish" (Join-Path $scripts "351_final_settlement_training_sync.ps1") $ref)
}

$steps += ,(Run-Step "331 smoke test" (Join-Path $scripts "331_final_system_smoke_test.ps1") $ref)

$child | Set-Content -Encoding UTF8 $outChild

$client = Join-Path $astro "ASTRODDS-FINAL-client-summary-latest.txt"
$guard = Join-Path $astro "ASTRODDS-375-moneyline-send-guard-and-daily-report-audit-latest.txt"
$clientText = ""
$guardText = ""
if (Test-Path $client) { $clientText = Get-Content $client -Raw }
if (Test-Path $guard) { $guardText = Get-Content $guard -Raw }

$lines = @()
$lines += "ASTRODDS 338H AUTOPILOT SERVER + 2:30AM REPORT + REAL PREMIUM FINISH"
$lines += ""
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$lines += "Env source: $envSource"
$lines += "Global action: $globalAction"
$lines += ""
$lines += "STEPS"
foreach ($s in $steps) { $lines += "- $($s.Name): $($s.Status) | Exit=$($s.ExitCode) | Duration=$($s.DurationSec)s" }
$lines += ""
$lines += "MONEYLINE GUARD"
$lines += $guardText
$lines += ""
$lines += "CLIENT SUMMARY"
$lines += $clientText

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    envSource=$envSource
    globalAction=$globalAction
    steps=@($steps)
    clientReport=$client
    guardReport=$guard
    childLog=$outChild
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

@(
    "ASTRODDS 338H HEARTBEAT",
    "Time: $((Get-Date).ToString('o'))",
    "GlobalAction: $globalAction",
    "LastReport: $outTxt",
    "ClientReport: $client",
    "Moneyline230AM: FALSE_REPORT_ONLY"
) | Set-Content -Encoding UTF8 $heartbeat

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
