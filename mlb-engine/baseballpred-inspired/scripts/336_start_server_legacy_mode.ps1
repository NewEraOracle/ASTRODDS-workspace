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

function Invoke-Json($url, $timeout = 25) {
    try { return Invoke-RestMethod -Uri $url -Method Get -TimeoutSec $timeout }
    catch { return $null }
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
        return [pscustomobject]@{Name=$name;Status="ERROR";ExitCode="1";DurationSec=$duration}
    }
}

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$outTxt = Join-Path $astro "ASTRODDS-336-start-server-legacy-mode-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-336-start-server-legacy-mode-latest.json"

Write-Host ""
Write-Host "ASTRODDS 336 START SERVER LEGACY MODE" -ForegroundColor Cyan
Write-Host ""

function Test-Port($port) {
    try {
        $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
        return @($conn).Count -gt 0
    } catch { return $false }
}

$ports = @(3000,3001,3002,5173)
$listening = @()
foreach ($p in $ports) {
    if (Test-Port $p) { $listening += $p }
}

$serverPath = ""
$serverCmd = ""
$started = "NO"
$reason = ""

if ($listening.Count -gt 0) {
    $reason = "server already appears listening on port(s): $($listening -join ',')"
} else {
    $candidates = @(
        $root,
        (Join-Path $root "frontend"),
        (Join-Path $root "app"),
        (Join-Path $root "web")
    )

    foreach ($c in $candidates) {
        if (Test-Path (Join-Path $c "package.json")) {
            $serverPath = $c
            break
        }
    }

    if ($serverPath -eq "") {
        $reason = "No package.json found in root/frontend/app/web."
    } else {
        $pkg = Get-Content (Join-Path $serverPath "package.json") -Raw
        $cmd = "npm run dev"
        if ($pkg -match '"dev"\s*:') { $cmd = "npm run dev" }
        elseif ($pkg -match '"start"\s*:') { $cmd = "npm start" }

        $serverCmd = "cd `"$serverPath`"; $cmd"
        Start-Process powershell -ArgumentList "-NoExit","-Command",$serverCmd | Out-Null
        $started = "YES"
        $reason = "started server in new PowerShell window"
        Start-Sleep -Seconds 5
    }
}

$after = @()
foreach ($p in $ports) {
    if (Test-Port $p) { $after += $p }
}

$lines = @()
$lines += "ASTRODDS 336 START SERVER LEGACY MODE"
$lines += ""
$lines += "Started new server window: $started"
$lines += "Reason: $reason"
$lines += "Server path: $serverPath"
$lines += "Server command: $serverCmd"
$lines += "Listening ports after check: $($after -join ',')"
$lines += ""
$lines += "Note: this does not block PowerShell. It starts the server like the old workflow."

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    started=$started
    reason=$reason
    serverPath=$serverPath
    serverCommand=$serverCmd
    listeningPorts=$after
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
