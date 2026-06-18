$ErrorActionPreference = "Continue"

function Ensure-Dir($path) {
    if (!(Test-Path $path)) { New-Item -ItemType Directory -Force -Path $path | Out-Null }
}
function Is-FreshToday($path) {
    if (!(Test-Path $path)) { return $false }
    try { return ((Get-Item $path).LastWriteTime.Date -eq (Get-Date).Date) } catch { return $false }
}
function Run-Step($name, $path, [ref]$childLog) {
    $start = Get-Date
    Write-Host "Running $name..." -ForegroundColor Cyan
    if (!(Test-Path $path)) {
        Write-Host "MISSING: $path" -ForegroundColor Yellow
        return [pscustomobject]@{Name=$name;Status="MISSING";ExitCode="";DurationSec=0}
    }
    $output = & powershell -ExecutionPolicy Bypass -File $path 2>&1
    $exit = $LASTEXITCODE
    $dur = [math]::Round(((Get-Date)-$start).TotalSeconds,2)
    $childLog.Value += ""
    $childLog.Value += "==== $name | Exit=$exit | Duration=$dur ===="
    $childLog.Value += @($output | ForEach-Object { "$_" })
    if ($exit -eq 0 -or $null -eq $exit) {
        Write-Host "OK: $name ($dur sec)" -ForegroundColor Green
        return [pscustomobject]@{Name=$name;Status="OK";ExitCode="0";DurationSec=$dur}
    } else {
        Write-Host "ERROR: $name ($exit)" -ForegroundColor Red
        return [pscustomobject]@{Name=$name;Status="ERROR";ExitCode="$exit";DurationSec=$dur}
    }
}

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro
$outTxt = Join-Path $astro "ASTRODDS-378-python-pybaseball-tools-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-378-python-pybaseball-tools-latest.json"
Write-Host ""
Write-Host "ASTRODDS 378 PYTHON + PYBASEBALL TOOLS CHECK" -ForegroundColor Cyan
Write-Host ""
$pythonCmd = "python"
$pyOk = $false
$version = ""
try {
    $version = & $pythonCmd --version 2>&1
    if ($LASTEXITCODE -eq 0 -or "$version" -match "Python") { $pyOk = $true }
} catch {}
if (-not $pyOk) {
    $pythonCmd = "py"
    try {
        $version = & $pythonCmd --version 2>&1
        if ($LASTEXITCODE -eq 0 -or "$version" -match "Python") { $pyOk = $true }
    } catch {}
}
$installStatus = "SKIPPED"
$moduleOk = $false
if ($pyOk) {
    $test = & $pythonCmd -c "import pandas, pybaseball; print('OK')" 2>&1
    if ("$test" -match "OK") {
        $moduleOk = $true
        $installStatus = "ALREADY_INSTALLED"
    } else {
        Write-Host "Installing pybaseball pandas..." -ForegroundColor Yellow
        $pip = & $pythonCmd -m pip install --user --upgrade pandas pybaseball 2>&1
        $installStatus = "INSTALL_ATTEMPTED"
        $test2 = & $pythonCmd -c "import pandas, pybaseball; print('OK')" 2>&1
        if ("$test2" -match "OK") { $moduleOk = $true }
    }
}
$lines = @()
$lines += "ASTRODDS 378 PYTHON + PYBASEBALL TOOLS CHECK"
$lines += ""
$lines += "Python command: $pythonCmd"
$lines += "Python OK: $pyOk"
$lines += "Version: $version"
$lines += "pybaseball/pandas OK: $moduleOk"
$lines += "Install status: $installStatus"
$lines += ""
$lines += "RULE"
$lines += "- This uses public baseball data tools only."
$lines += "- No Odds API credits are used."
[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    pythonCommand=$pythonCmd
    pythonOk=$pyOk
    pythonVersion="$version"
    modulesOk=$moduleOk
    installStatus=$installStatus
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson
($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
if ($pyOk -and $moduleOk) { exit 0 } else { exit 1 }
