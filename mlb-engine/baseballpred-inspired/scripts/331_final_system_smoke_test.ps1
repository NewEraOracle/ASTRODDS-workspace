$ErrorActionPreference = "Continue"


function Ensure-Dir($path) {
    if (!(Test-Path $path)) { New-Item -ItemType Directory -Force -Path $path | Out-Null }
}

function Safe-Read($path) {
    if (!(Test-Path $path)) { return @() }
    try { return @(Get-Content $path -ErrorAction Stop) } catch { return @() }
}

function Parse-EnvFile($path) {
    $rows = @()
    foreach ($line in (Safe-Read $path)) {
        if ($line -match "^\s*#") { continue }
        if ($line -match "^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$") {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim().Trim('"').Trim("'")
            $rows += ,[pscustomobject]@{ Name=$name; Value=$value }
        }
    }
    return @($rows)
}

function Load-EnvFromFile($path) {
    if (!(Test-Path $path)) { return $false }
    foreach ($r in (Parse-EnvFile $path)) {
        [Environment]::SetEnvironmentVariable($r.Name, $r.Value, "Process")
    }

    if ($env:THE_ODDS_API_KEY -and -not $env:ODDS_API_KEY) { $env:ODDS_API_KEY = $env:THE_ODDS_API_KEY }
    if ($env:ASTRODDS_ODDS_API_KEY -and -not $env:ODDS_API_KEY) { $env:ODDS_API_KEY = $env:ASTRODDS_ODDS_API_KEY }

    if ($env:ASTRODDS_TELEGRAM_BOT_TOKEN -and -not $env:TELEGRAM_BOT_TOKEN) { $env:TELEGRAM_BOT_TOKEN = $env:ASTRODDS_TELEGRAM_BOT_TOKEN }
    if ($env:ASTRODDS_TELEGRAM_CHAT_ID -and -not $env:TELEGRAM_CHAT_ID) { $env:TELEGRAM_CHAT_ID = $env:ASTRODDS_TELEGRAM_CHAT_ID }

    return $true
}

function Score-EnvFile($path) {
    $score = 0
    $keys = Parse-EnvFile $path
    $names = @($keys | Select-Object -ExpandProperty Name)
    foreach ($n in $names) {
        if ($n -match "ODDS_API|THE_ODDS|ASTRODDS_ODDS") { $score += 100 }
        if ($n -match "TELEGRAM.*TOKEN|BOT_TOKEN") { $score += 30 }
        if ($n -match "TELEGRAM.*CHAT|CHAT_ID") { $score += 30 }
        if ($n -match "ASTRODDS") { $score += 10 }
    }
    try { $score += [int]((Get-Item $path).LastWriteTime.Ticks % 1000) / 1000 } catch {}
    return $score
}

function Find-BestEnvFile($root) {
    $candidates = @()

    $fixed = @(
        (Join-Path $root ".env.local"),
        (Join-Path $root ".env"),
        (Join-Path $root "mlb-engine\.env.local"),
        (Join-Path $root "mlb-engine\.env"),
        (Join-Path $root "mlb-engine\baseballpred-inspired\.env.local"),
        (Join-Path $root "mlb-engine\baseballpred-inspired\.env"),
        (Join-Path $env:USERPROFILE ".astrodds\.env"),
        (Join-Path $env:USERPROFILE ".env")
    )

    foreach ($p in $fixed) {
        if (Test-Path $p) { $candidates += (Get-Item $p) }
    }

    try {
        $recursive = Get-ChildItem $root -Recurse -Force -File -Include ".env",".env.local",".env.production","*.env" -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -notmatch "\\node_modules\\|\\.next\\|\\dist\\|\\build\\" }
        $candidates += @($recursive)
    } catch {}

    $unique = @{}
    foreach ($c in $candidates) { $unique[$c.FullName] = $c }

    $scored = @()
    foreach ($p in $unique.Keys) {
        $score = Score-EnvFile $p
        $scored += ,[pscustomobject]@{ Path=$p; Score=$score; LastWriteTime=(Get-Item $p).LastWriteTime }
    }

    $best = $scored | Sort-Object Score, LastWriteTime -Descending | Select-Object -First 1
    return $best
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

$outTxt = Join-Path $astro "ASTRODDS-331-final-system-smoke-test-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-331-final-system-smoke-test-latest.json"

Write-Host ""
Write-Host "ASTRODDS 331 FINAL SYSTEM SMOKE TEST" -ForegroundColor Cyan
Write-Host ""

$critical = @(
    "308_final_production_one_command.ps1",
    "324_run_elite_factors_runner.ps1",
    "329_run_final_with_env_autoload.ps1",
    "330_keepalive_autopilot_loop.ps1",
    "291_enhanced_settlement_roi_clv.ps1",
    "297_telegram_auto_send_safe.ps1"
)

$checks = @()
foreach ($s in $critical) {
    $p = Join-Path $scripts $s
    $checks += ,[pscustomobject]@{ Item=$s; OK=(Test-Path $p); Path=$p }
}

$envJson = Join-Path $astro "ASTRODDS-328-env-autofinder-loader-latest.json"
$envOk = $false
if (Test-Path $envJson) {
    try {
        $e = Get-Content $envJson -Raw | ConvertFrom-Json
        $envOk = [bool]$e.envFound
    } catch {}
}
$checks += ,[pscustomobject]@{ Item="env file found by 328"; OK=$envOk; Path=$envJson }

$admin = Join-Path $astro "ASTRODDS-FINAL-admin-report-latest.txt"
$client = Join-Path $astro "ASTRODDS-FINAL-client-summary-latest.txt"
$checks += ,[pscustomobject]@{ Item="client report exists"; OK=(Test-Path $client); Path=$client }
$checks += ,[pscustomobject]@{ Item="admin report exists"; OK=(Test-Path $admin); Path=$admin }

$fail = @($checks | Where-Object { -not $_.OK }).Count
$status = if ($fail -eq 0) { "SMOKE_TEST_PASS" } else { "SMOKE_TEST_WARNINGS" }

$lines = @()
$lines += "ASTRODDS 331 FINAL SYSTEM SMOKE TEST"
$lines += ""
$lines += "Status: $status"
$lines += "Failed/warning checks: $fail"
$lines += ""
foreach ($c in $checks) {
    $lines += "- $($c.Item): $($c.OK) | $($c.Path)"
}

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    status=$status
    failedChecks=$fail
    checks=@($checks)
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
