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

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
$scripts = Join-Path $root "mlb-engine\baseballpred-inspired\scripts"
Ensure-Dir $astro

$outTxt = Join-Path $astro "ASTRODDS-306-BASEBALLPRED-PLUS-WITH-ALIASES-RUN-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-306-BASEBALLPRED-PLUS-WITH-ALIASES-RUN-latest.json"
$outChildLog = Join-Path $astro "ASTRODDS-306-child-log-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 306 BASEBALLPRED++ RUNNER WITH BALLPARK ALIASES" -ForegroundColor Cyan
Write-Host ""

$childLog = @()
function Run-Step($name, $path) {
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
        $script:childLog += ""
        $script:childLog += "============================================================"
        $script:childLog += "STEP: $name"
        $script:childLog += "EXIT: $exitCode"
        $script:childLog += "DURATION: $duration sec"
        $script:childLog += "============================================================"
        $script:childLog += @($output | ForEach-Object { "$_" })
        if ($exitCode -eq 0 -or $null -eq $exitCode) {
            Write-Host "OK: $name ($duration sec)" -ForegroundColor Green
            return [pscustomobject]@{Name=$name;Status="OK";ExitCode="0";DurationSec=$duration}
        } else {
            Write-Host "ERROR: $name exit $exitCode" -ForegroundColor Red
            return [pscustomobject]@{Name=$name;Status="ERROR";ExitCode="$exitCode";DurationSec=$duration}
        }
    } catch {
        $duration = [math]::Round(((Get-Date)-$start).TotalSeconds,2)
        return [pscustomobject]@{Name=$name;Status="ERROR";ExitCode="1";DurationSec=$duration}
    }
}

$steps = @()
$steps += ,(Run-Step "296 BaseballPred++ base runner" (Join-Path $scripts "296_baseballpred_plus_runner.ps1"))
$steps += ,(Run-Step "305 ballpark alias repair + safety" (Join-Path $scripts "305_run_ballpark_alias_repair_and_safety.ps1"))

$childLog | Set-Content -Encoding UTF8 $outChildLog

$report = Join-Path $astro "ASTRODDS-303-baseballpred-plus-safety-report-latest.txt"
$rep = ""
if (Test-Path $report) { $rep = Get-Content $report -Raw }

$lines = @()
$lines += "ASTRODDS 306 BASEBALLPRED++ RUNNER WITH BALLPARK ALIASES"
$lines += ""
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$lines += ""
$lines += "STEPS"
foreach ($s in $steps) { $lines += "- $($s.Name): $($s.Status) | Exit=$($s.ExitCode) | Duration=$($s.DurationSec)s" }
$lines += ""
$lines += "FINAL SAFETY REPORT"
$lines += $rep

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    steps=@($steps)
    report=$report
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
