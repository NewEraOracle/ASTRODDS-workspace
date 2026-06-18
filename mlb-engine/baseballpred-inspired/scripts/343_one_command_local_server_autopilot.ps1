param(
    [int]$IntervalMinutes = 10,
    [switch]$SendTelegram
)

$ErrorActionPreference = "Continue"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
$scripts = Join-Path $root "mlb-engine\baseballpred-inspired\scripts"

if (!(Test-Path $astro)) { New-Item -ItemType Directory -Force -Path $astro | Out-Null }

$heartbeat = Join-Path $astro "ASTRODDS-343-one-command-heartbeat-latest.txt"
$loopLog = Join-Path $astro "ASTRODDS-343-one-command-loop-log-latest.txt"
$pidFile = Join-Path $astro "ASTRODDS-343-one-command-pid-latest.txt"

$PID | Set-Content -Encoding UTF8 $pidFile

function Write-Heartbeat($status, $run, $extra = "") {
    @(
        "ASTRODDS 343 ONE-COMMAND LOCAL SERVER AUTOPILOT",
        "Status: $status",
        "Time: $((Get-Date).ToString('o'))",
        "PID: $PID",
        "Run: $run",
        "IntervalMinutes: $IntervalMinutes",
        "TelegramSend: $env:ASTRODDS_TELEGRAM_SEND",
        $extra
    ) | Set-Content -Encoding UTF8 $heartbeat
}

function Test-Port($port) {
    try {
        $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
        return @($conn).Count -gt 0
    } catch { return $false }
}

function Start-LocalServerOnce {
    $ports = @(3000,3001,3002,5173)
    foreach ($p in $ports) {
        if (Test-Port $p) {
            Write-Host "Server already running on port $p. No new server started." -ForegroundColor Green
            return "ALREADY_RUNNING_PORT_$p"
        }
    }

    $serverPath = ""
    foreach ($c in @($root, (Join-Path $root "frontend"), (Join-Path $root "app"), (Join-Path $root "web"))) {
        if (Test-Path (Join-Path $c "package.json")) {
            $serverPath = $c
            break
        }
    }

    if ($serverPath -eq "") {
        Write-Host "No package.json found. Server not started, autopilot still runs reports/scans." -ForegroundColor Yellow
        return "NO_PACKAGE_JSON"
    }

    $pkg = Get-Content (Join-Path $serverPath "package.json") -Raw
    $cmd = "npm run dev"
    if ($pkg -notmatch '"dev"\s*:' -and $pkg -match '"start"\s*:') { $cmd = "npm start" }

    Write-Host "Starting local server once: $cmd in $serverPath" -ForegroundColor Cyan
    Start-Process powershell -ArgumentList "-NoExit","-Command","cd `"$serverPath`"; $cmd" | Out-Null
    Start-Sleep -Seconds 5

    foreach ($p in $ports) {
        if (Test-Port $p) { return "STARTED_PORT_$p" }
    }

    return "STARTED_BUT_PORT_NOT_CONFIRMED"
}

Clear-Host
Write-Host ""
Write-Host "ASTRODDS 343 ONE-COMMAND LOCAL SERVER AUTOPILOT" -ForegroundColor Cyan
Write-Host "One command. One server. One autopilot loop. No 20 commands." -ForegroundColor Cyan
Write-Host ""

if ($SendTelegram) {
    $env:ASTRODDS_TELEGRAM_SEND = "YES"
    Write-Host "Telegram mode: REAL SEND enabled by parameter." -ForegroundColor Yellow
} else {
    $env:ASTRODDS_TELEGRAM_SEND = "NO"
    Write-Host "Telegram mode: DRY-RUN safe mode." -ForegroundColor Green
}

$serverStatus = Start-LocalServerOnce

Write-Host ""
Write-Host "Server status: $serverStatus" -ForegroundColor Cyan
Write-Host "Autopilot interval: $IntervalMinutes minutes" -ForegroundColor Cyan
Write-Host ""
Write-Host "Leave this window open. Press CTRL+C to stop." -ForegroundColor Yellow
Write-Host ""

$runs = 0

while ($true) {
    $runs++
    $start = Get-Date
    Write-Heartbeat "RUNNING" $runs "ServerStatus: $serverStatus"

    Add-Content -Encoding UTF8 $loopLog ""
    Add-Content -Encoding UTF8 $loopLog "============================================================"
    Add-Content -Encoding UTF8 $loopLog "RUN $runs START $($start.ToString('o'))"
    Add-Content -Encoding UTF8 $loopLog "SERVER_STATUS=$serverStatus"
    Add-Content -Encoding UTF8 $loopLog "============================================================"

    $cycleScript = Join-Path $scripts "338_autopilot_server_scan_cycle.ps1"

    if (!(Test-Path $cycleScript)) {
        $msg = "MISSING 338_autopilot_server_scan_cycle.ps1"
        Write-Host $msg -ForegroundColor Red
        Add-Content -Encoding UTF8 $loopLog $msg
    } else {
        $out = & powershell -ExecutionPolicy Bypass -File $cycleScript -NoStartServer 2>&1
        $exit = $LASTEXITCODE
        Add-Content -Encoding UTF8 $loopLog ($out | ForEach-Object { "$_" })
        Add-Content -Encoding UTF8 $loopLog "EXIT=$exit"

        if ($exit -eq 0 -or $null -eq $exit) {
            Write-Host "Run $runs OK at $(Get-Date -Format 'HH:mm:ss')" -ForegroundColor Green
        } else {
            Write-Host "Run $runs ended with exit $exit at $(Get-Date -Format 'HH:mm:ss')" -ForegroundColor Yellow
        }
    }

    $finish = Get-Date
    $next = $finish.AddMinutes($IntervalMinutes)

    Write-Heartbeat "SLEEPING" $runs "ServerStatus: $serverStatus`nLastRunFinished: $($finish.ToString('o'))`nNextRunApprox: $($next.ToString('o'))"

    Write-Host "Sleeping until approx $($next.ToString('HH:mm:ss'))..." -ForegroundColor DarkCyan
    Start-Sleep -Seconds ([math]::Max(60, $IntervalMinutes * 60))
}
