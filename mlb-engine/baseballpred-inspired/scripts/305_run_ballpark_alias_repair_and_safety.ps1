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

$outTxt = Join-Path $astro "ASTRODDS-305-BALLPARK-ALIAS-REPAIR-SAFETY-RUN-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-305-BALLPARK-ALIAS-REPAIR-SAFETY-RUN-latest.json"
$outChildLog = Join-Path $astro "ASTRODDS-305-child-log-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 305 BALLPARK ALIAS REPAIR + SAFETY RUNNER" -ForegroundColor Cyan
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

$run = @(
    @{Name="304 ballpark alias repair"; Path=Join-Path $scripts "304_ballpark_alias_repair.ps1"},
    @{Name="300 strict plus context merge"; Path=Join-Path $scripts "300_strict_plus_context_merge.ps1"},
    @{Name="303 BaseballPred++ safety report"; Path=Join-Path $scripts "303_baseballpred_plus_safety_report.ps1"}
)

$steps = @()
foreach ($s in $run) { $steps += ,(Run-Step $s.Name $s.Path) }
$childLog | Set-Content -Encoding UTF8 $outChildLog

$report = Join-Path $astro "ASTRODDS-303-baseballpred-plus-safety-report-latest.txt"
$rep = ""
if (Test-Path $report) { $rep = Get-Content $report -Raw }

$partial = 0
try {
    $plus = Safe-Csv (Join-Path $astro "ASTRODDS-baseballpred-plus-context-latest.csv")
    $partial = @($plus | Where-Object { (Get-Val $_ @("PlusStatus")) -ne "BASEBALLPRED_PLUS_CONNECTED" }).Count
} catch {}

$lines = @()
$lines += "ASTRODDS 305 BALLPARK ALIAS REPAIR + SAFETY RUNNER"
$lines += ""
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$lines += "Partial plus-context rows after alias repair: $partial"
$lines += ""
$lines += "STEPS"
foreach ($s in $steps) { $lines += "- $($s.Name): $($s.Status) | Exit=$($s.ExitCode) | Duration=$($s.DurationSec)s" }
$lines += ""
$lines += "REPORT"
$lines += $rep

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    partialPlusRowsAfterAliasRepair=$partial
    steps=@($steps)
    report=$report
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
