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

$outTxt = Join-Path $astro "ASTRODDS-285-start-server-and-autoscan-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 285F START SERVER + AUTOSCAN FIXED" -ForegroundColor Cyan
Write-Host ""

$serverStarted = "NO"
$serverCmd = ""

if (Test-Path (Join-Path $root "package.json")) {
    $serverCmd = "cd `"$root`"; npm run dev"
    Start-Process powershell -ArgumentList "-NoExit","-Command",$serverCmd
    $serverStarted = "YES"
} elseif (Test-Path (Join-Path $root "frontend\package.json")) {
    $frontend = Join-Path $root "frontend"
    $serverCmd = "cd `"$frontend`"; npm run dev"
    Start-Process powershell -ArgumentList "-NoExit","-Command",$serverCmd
    $serverStarted = "YES"
} else {
    Write-Host "No package.json found. Server not started automatically." -ForegroundColor Yellow
}

Start-Sleep -Seconds 3

$loopScript = Join-Path $scripts "284_auto_scan_loop_credit_safe.ps1"

$lines = @()
$lines += "ASTRODDS 285F START SERVER + AUTOSCAN FIXED"
$lines += ""
$lines += "Server started: $serverStarted"
$lines += "Server command: $serverCmd"
$lines += "Loop script: $loopScript"
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Starting autoscan loop now. Stop with CTRL+C." -ForegroundColor Yellow

& powershell -ExecutionPolicy Bypass -File $loopScript
exit 0
