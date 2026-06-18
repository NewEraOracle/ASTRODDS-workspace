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

function Set-Prop($obj, $name, $value) {
    if ($obj.PSObject.Properties[$name]) {
        $obj.$name = $value
    } else {
        $obj | Add-Member -MemberType NoteProperty -Name $name -Value $value -Force
    }
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
        Write-Host "ERROR: $name $($_.Exception.Message)" -ForegroundColor Red
        return [pscustomobject]@{Name=$name;Status="ERROR";ExitCode="1";DurationSec=$dur}
    }
}

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$outTxt = Join-Path $astro "ASTRODDS-353-final-autopilot-command-check-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 353 FINAL AUTOPILOT COMMAND CHECK" -ForegroundColor Cyan
Write-Host ""

$pkg = Join-Path $root "package.json"
$hasAstrodds = $false
$hasStatus = $false
$hasReports = $false

if (Test-Path $pkg) {
    try {
        $json = Get-Content $pkg -Raw | ConvertFrom-Json
        if ($json.scripts.astrodds) { $hasAstrodds = $true }
        if ($json.scripts.'astrodds:status') { $hasStatus = $true }
        if ($json.scripts.'astrodds:reports') { $hasReports = $true }
    } catch {}
}

$heartbeat = Join-Path $astro "ASTRODDS-343-one-command-heartbeat-latest.txt"
$hb = ""
if (Test-Path $heartbeat) { $hb = Get-Content $heartbeat -Raw }

$lines = @()
$lines += "ASTRODDS 353 FINAL AUTOPILOT COMMAND CHECK"
$lines += ""
$lines += "npm run astrodds installed: $hasAstrodds"
$lines += "npm run astrodds:status installed: $hasStatus"
$lines += "npm run astrodds:reports installed: $hasReports"
$lines += ""
$lines += "Heartbeat:"
$lines += $hb
$lines += ""
$lines += "Use only:"
$lines += "npm run astrodds"
$lines += ""
$lines += "Check status:"
$lines += "npm run astrodds:status"

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
