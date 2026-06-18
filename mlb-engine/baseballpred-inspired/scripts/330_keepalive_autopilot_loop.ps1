$ErrorActionPreference = "Continue"

param(
    [int]$IntervalMinutes = 30,
    [int]$MaxRuns = 0
)


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

$heartbeat = Join-Path $astro "ASTRODDS-330-autopilot-heartbeat-latest.txt"
$loopLog = Join-Path $astro "ASTRODDS-330-autopilot-loop-log-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 330 KEEPALIVE AUTOPILOT LOOP" -ForegroundColor Cyan
Write-Host "Interval: $IntervalMinutes minutes | MaxRuns: $MaxRuns (0 = infinite)" -ForegroundColor Cyan
Write-Host ""

$runs = 0

while ($true) {
    $runs++
    $started = Get-Date

    $msg = @()
    $msg += "ASTRODDS AUTOPILOT HEARTBEAT"
    $msg += "Started: $($started.ToString('o'))"
    $msg += "Run: $runs"
    $msg += "IntervalMinutes: $IntervalMinutes"
    $msg += "TelegramSend: $env:ASTRODDS_TELEGRAM_SEND"
    $msg += "Status: RUNNING"
    $msg | Set-Content -Encoding UTF8 $heartbeat

    Add-Content -Encoding UTF8 $loopLog ""
    Add-Content -Encoding UTF8 $loopLog "============================================================"
    Add-Content -Encoding UTF8 $loopLog "RUN $runs START $($started.ToString('o'))"
    Add-Content -Encoding UTF8 $loopLog "============================================================"

    $out = & powershell -ExecutionPolicy Bypass -File (Join-Path $scripts "329_run_final_with_env_autoload.ps1") 2>&1
    $exit = $LASTEXITCODE

    Add-Content -Encoding UTF8 $loopLog ($out | ForEach-Object { "$_" })
    Add-Content -Encoding UTF8 $loopLog "EXIT=$exit"

    $finished = Get-Date
    $msg = @()
    $msg += "ASTRODDS AUTOPILOT HEARTBEAT"
    $msg += "Started: $($started.ToString('o'))"
    $msg += "Finished: $($finished.ToString('o'))"
    $msg += "Run: $runs"
    $msg += "LastExit: $exit"
    $msg += "NextRunApprox: $($finished.AddMinutes($IntervalMinutes).ToString('o'))"
    $msg += "Status: SLEEPING"
    $msg | Set-Content -Encoding UTF8 $heartbeat

    if ($MaxRuns -gt 0 -and $runs -ge $MaxRuns) {
        Add-Content -Encoding UTF8 $loopLog "MAX RUNS REACHED. EXITING."
        break
    }

    Start-Sleep -Seconds ([math]::Max(60, $IntervalMinutes * 60))
}
exit 0
