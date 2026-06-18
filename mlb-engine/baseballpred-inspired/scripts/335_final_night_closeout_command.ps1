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

$outTxt = Join-Path $astro "ASTRODDS-335-FINAL-NIGHT-CLOSEOUT-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-335-FINAL-NIGHT-CLOSEOUT-latest.json"
$outChild = Join-Path $astro "ASTRODDS-335-child-log-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 335 FINAL NIGHT CLOSEOUT COMMAND" -ForegroundColor Cyan
Write-Host "Runs env finder, final scan, smoke test, reports. Does not enable real Telegram send." -ForegroundColor Cyan
Write-Host ""

$child = @()
$ref = [ref]$child

$steps = @()
$steps += ,(Run-Step "334 force Telegram dry-run" (Join-Path $scripts "334_telegram_send_mode_toggle.ps1") $ref)
$steps += ,(Run-Step "329 final with env autoload" (Join-Path $scripts "329_run_final_with_env_autoload.ps1") $ref)
$steps += ,(Run-Step "331 smoke test" (Join-Path $scripts "331_final_system_smoke_test.ps1") $ref)
$steps += ,(Run-Step "333 open reports helper" (Join-Path $scripts "333_open_final_reports.ps1") $ref)

$child | Set-Content -Encoding UTF8 $outChild

$readiness = Join-Path $astro "ASTRODDS-312-final-readiness-gate-latest.txt"
$client = Join-Path $astro "ASTRODDS-FINAL-client-summary-latest.txt"
$admin = Join-Path $astro "ASTRODDS-FINAL-admin-report-latest.txt"
$heartbeat = Join-Path $astro "ASTRODDS-330-autopilot-heartbeat-latest.txt"

$readyText = ""
$clientText = ""
if (Test-Path $readiness) { $readyText = Get-Content $readiness -Raw }
if (Test-Path $client) { $clientText = Get-Content $client -Raw }

$lines = @()
$lines += "ASTRODDS 335 FINAL NIGHT CLOSEOUT COMMAND"
$lines += ""
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$lines += ""
$lines += "STEPS"
foreach ($s in $steps) { $lines += "- $($s.Name): $($s.Status) | Exit=$($s.ExitCode) | Duration=$($s.DurationSec)s" }
$lines += ""
$lines += "READINESS"
$lines += $readyText
$lines += ""
$lines += "CLIENT SUMMARY"
$lines += $clientText
$lines += ""
$lines += "FINAL COMMANDS TO LEAVE RUNNING"
$lines += "Foreground loop every 30 min:"
$lines += 'powershell -ExecutionPolicy Bypass -File ".\mlb-engine\baseballpred-inspired\scripts\330_keepalive_autopilot_loop.ps1" -IntervalMinutes 30'
$lines += ""
$lines += "Or install Windows scheduled task:"
$lines += 'powershell -ExecutionPolicy Bypass -File ".\mlb-engine\baseballpred-inspired\scripts\332_install_final_autopilot_task.ps1"'
$lines += ""
$lines += "FILES"
$lines += "- Client report: $client"
$lines += "- Admin report: $admin"
$lines += "- Child log: $outChild"
$lines += "- Heartbeat: $heartbeat"

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    steps=@($steps)
    readiness=$readiness
    clientReport=$client
    adminReport=$admin
    childLog=$outChild
    heartbeat=$heartbeat
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
