param([switch]$Force)
$ErrorActionPreference = "Continue"

function Ensure-Dir($path) {
    if (!(Test-Path $path)) { New-Item -ItemType Directory -Force -Path $path | Out-Null }
}
function Count-RealRows($path, $requiredCols) {
    if (!(Test-Path $path)) { return 0 }
    try {
        $rows = @(Import-Csv $path)
        $count = 0
        foreach ($r in $rows) {
            $ok = $true
            foreach ($c in $requiredCols) {
                $v = ""
                try { $v = "$($r.$c)".Trim() } catch {}
                if ($v -eq "") { $ok = $false; break }
            }
            if ($ok) { $count++ }
        }
        return $count
    } catch { return 0 }
}
function Is-FreshTodayWithRows($path, $requiredCols) {
    if (!(Test-Path $path)) { return $false }
    try {
        $fresh = ((Get-Item $path).LastWriteTime.Date -eq (Get-Date).Date)
        $rows = Count-RealRows $path $requiredCols
        return ($fresh -and $rows -gt 0)
    } catch { return $false }
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
$scripts = Join-Path $root "mlb-engine\baseballpred-inspired\scripts"
Ensure-Dir $astro

$outCsv = Join-Path $astro "ASTRODDS-premium-input-bullpen-leverage-availability.csv"
$outTxt = Join-Path $astro "ASTRODDS-381-fetch-true-leverage-fangraphs-pybaseball-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-381-fetch-true-leverage-fangraphs-pybaseball-latest.json"
$py = Join-Path $scripts "381_fetch_true_leverage_fangraphs_pybaseball.py"

Write-Host ""
Write-Host "ASTRODDS 381F TRUE LEVERAGE FETCH - EMPTY CSV REFRESH FIX" -ForegroundColor Cyan
Write-Host ""

$existingRows = Count-RealRows $outCsv @("Team","Reliever","LeverageIndex")
if ((Is-FreshTodayWithRows $outCsv @("Team","Reliever","LeverageIndex")) -and -not $Force) {
    $status = "SKIPPED_FRESH_TODAY_WITH_ROWS"
    $msg = "Output already refreshed today and contains $existingRows real rows. Use -Force to refetch."
} else {
    $pythonCmd = "python"
    try { & $pythonCmd --version | Out-Null } catch { $pythonCmd = "py" }
    $year = (Get-Date).Year
    $result = & $pythonCmd $py --year $year --out $outCsv 2>&1
    $exit = $LASTEXITCODE
    $status = if ($exit -eq 0) { "OK" } else { "ERROR" }
    $msg = ($result -join [Environment]::NewLine)
}

$rows = Count-RealRows $outCsv @("Team","Reliever","LeverageIndex")
$lines = @(
    "ASTRODDS 381F TRUE LEVERAGE FETCH - EMPTY CSV REFRESH FIX",
    "",
    "Status: $status",
    "Rows: $rows",
    "Output: $outCsv",
    "",
    "DETAIL",
    $msg,
    "",
    "RULE",
    "- Empty fresh CSV does not skip anymore.",
    "- Leverage index only connects if FanGraphs/pybaseball exposes gmLI/inLI/exLI.",
    "- If not available, true leverage remains MISSING_SOURCE."
)

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    status=$status
    rows=$rows
    outputCsv=$outCsv
    detail=$msg
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
if ($status -eq "ERROR") { exit 1 } else { exit 0 }
