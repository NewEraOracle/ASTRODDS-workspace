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
}


$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$scripts = Join-Path $root "mlb-engine\baseballpred-inspired\scripts"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro
Load-EnvLocal $root

$outTxt = Join-Path $astro "ASTRODDS-284-auto-scan-loop-credit-safe-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 284F AUTO SCAN LOOP CREDIT SAFE FIXED" -ForegroundColor Cyan
Write-Host "Runs 283F. Paid odds only through credit-aware 281." -ForegroundColor Cyan
Write-Host ""
Write-Host "Stop with CTRL+C." -ForegroundColor Yellow
Write-Host ""

$intervalMinutes = 10
if ($env:ASTRODDS_SCAN_INTERVAL_MINUTES) {
    try { $intervalMinutes = [int]$env:ASTRODDS_SCAN_INTERVAL_MINUTES } catch {}
}

$maxLoops = 0
if ($env:ASTRODDS_MAX_LOOPS) {
    try { $maxLoops = [int]$env:ASTRODDS_MAX_LOOPS } catch {}
}

$loop = 0
$runScript = Join-Path $scripts "283_credit_safe_pregame_rescan.ps1"

while ($true) {
    $loop++
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor DarkGray
    Write-Host "ASTRODDS AUTO LOOP #$loop at $stamp" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor DarkGray

    try {
        & powershell -ExecutionPolicy Bypass -File $runScript
    } catch {
        Write-Host "Loop error: $($_.Exception.Message)" -ForegroundColor Red
    }

    Add-Content -Encoding UTF8 $outTxt "Loop #$loop completed at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"

    if ($maxLoops -gt 0 -and $loop -ge $maxLoops) {
        Write-Host "Max loops reached: $maxLoops"
        break
    }

    Write-Host "Next scan in $intervalMinutes minutes..."
    Start-Sleep -Seconds ($intervalMinutes * 60)
}

exit 0
