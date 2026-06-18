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

function Normalize-Team($s) {
    $x = "$s".ToLower().Trim()
    $x = $x -replace "[^a-z0-9 ]", ""
    $x = $x -replace "\s+", " "
    return $x
}

function Game-Key($game) {
    $g = "$game"
    if ($g -match "\s@\s") {
        $parts = $g -split "\s@\s", 2
        return (Normalize-Team $parts[0]) + " @ " + (Normalize-Team $parts[1])
    }
    return (Normalize-Team $g)
}

function Find-By-Game($rows, $game) {
    $k = Game-Key $game
    foreach ($r in @($rows)) {
        $g = Get-Val $r @("Game","game")
        if ($g -eq "") { continue }
        if ((Game-Key $g) -eq $k) { return $r }
    }
    return $null
}

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
$scripts = Join-Path $root "mlb-engine\baseballpred-inspired\scripts"
Ensure-Dir $astro

$outTxt = Join-Path $astro "ASTRODDS-327-ELITE-CLASSIFICATION-FIX-RUN-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-327-ELITE-CLASSIFICATION-FIX-RUN-latest.json"
$outChild = Join-Path $astro "ASTRODDS-327-child-log-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 327 ELITE CLASSIFICATION FIX RUNNER" -ForegroundColor Cyan
Write-Host ""

$child = @()
function Run-StepLocal($name, $path) {
    $start = Get-Date
    Write-Host "Running $name..." -ForegroundColor Cyan

    if (!(Test-Path $path)) {
        Write-Host "MISSING: $path" -ForegroundColor Yellow
        return [pscustomobject]@{Name=$name;Status="MISSING";ExitCode="";DurationSec=0}
    }

    $output = & powershell -ExecutionPolicy Bypass -File $path 2>&1
    $exit = $LASTEXITCODE
    $dur = [math]::Round(((Get-Date)-$start).TotalSeconds,2)
    $script:child += ""
    $script:child += "==== $name | Exit=$exit | Duration=$dur ===="
    $script:child += @($output | ForEach-Object { "$_" })

    if ($exit -eq 0 -or $null -eq $exit) {
        Write-Host "OK: $name ($dur sec)" -ForegroundColor Green
        return [pscustomobject]@{Name=$name;Status="OK";ExitCode="0";DurationSec=$dur}
    } else {
        Write-Host "ERROR: $name ($exit)" -ForegroundColor Red
        return [pscustomobject]@{Name=$name;Status="ERROR";ExitCode="$exit";DurationSec=$dur}
    }
}

$steps = @()
$steps += ,(Run-StepLocal "323B elite official gate clean classification" (Join-Path $scripts "323_elite_official_gate.ps1"))
$steps += ,(Run-StepLocal "326 classification audit" (Join-Path $scripts "326_elite_gate_classification_audit.ps1"))
$steps += ,(Run-StepLocal "309 rebuild client/admin report" (Join-Path $scripts "309_client_admin_report_builder.ps1"))
$steps += ,(Run-StepLocal "312 final readiness gate" (Join-Path $scripts "312_final_readiness_gate.ps1"))

$child | Set-Content -Encoding UTF8 $outChild

$auditPath = Join-Path $astro "ASTRODDS-326-elite-gate-classification-audit-latest.txt"
$audit = ""
if (Test-Path $auditPath) { $audit = Get-Content $auditPath -Raw }

$lines = @()
$lines += "ASTRODDS 327 ELITE CLASSIFICATION FIX RUNNER"
$lines += ""
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$lines += ""
$lines += "STEPS"
foreach ($s in $steps) { $lines += "- $($s.Name): $($s.Status) | Exit=$($s.ExitCode) | Duration=$($s.DurationSec)s" }
$lines += ""
$lines += "AUDIT"
$lines += $audit

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    steps=@($steps)
    audit=$auditPath
    childLog=$outChild
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
