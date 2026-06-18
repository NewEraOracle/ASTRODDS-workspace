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

function Normalize-Name($s) {
    $x = "$s".ToLower().Trim()
    $x = $x -replace "[^a-z0-9 ]", ""
    $x = $x -replace "\s+", " "
    return $x
}

function Read-JsonSafe($path) {
    if (!(Test-Path $path)) { return $null }
    try { return Get-Content $path -Raw | ConvertFrom-Json } catch { return $null }
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
        return [pscustomobject]@{Name=$name;Status="ERROR";ExitCode="1";DurationSec=$dur}
    }
}

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$outTxt = Join-Path $astro "ASTRODDS-369-daily-230am-report-router-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-369-daily-230am-report-router-latest.json"
$dailyReport = Join-Path $astro "ASTRODDS-DAILY-230AM-REPORT-latest.txt"
$sentState = Join-Path $astro "ASTRODDS-369-daily-230am-last-run-date.txt"

Write-Host ""
Write-Host "ASTRODDS 369 DAILY 2:30AM REPORT ROUTER" -ForegroundColor Cyan
Write-Host "2:30 AM is report/settlement only. It never creates a new Moneyline pick." -ForegroundColor Cyan
Write-Host ""

$now = Get-Date
$dateKey = $now.ToString("yyyy-MM-dd")
$minutesNow = ($now.Hour * 60) + $now.Minute
$target = (2 * 60) + 30
$windowStart = $target - 15
$windowEnd = $target + 25

$lastRunDate = ""
if (Test-Path $sentState) { $lastRunDate = (Get-Content $sentState -Raw).Trim() }

$inWindow = ($minutesNow -ge $windowStart -and $minutesNow -le $windowEnd)
$alreadyDone = ($lastRunDate -eq $dateKey)

$action = "NO_230AM_ACTION"
if ($inWindow -and -not $alreadyDone) { $action = "RUN_230AM_REPORT_ONLY" }
elseif ($inWindow -and $alreadyDone) { $action = "230AM_REPORT_ALREADY_DONE" }

$client = Join-Path $astro "ASTRODDS-FINAL-client-summary-latest.txt"
$admin = Join-Path $astro "ASTRODDS-FINAL-admin-report-latest.txt"
$settle = Join-Path $astro "ASTRODDS-349-settlement-integrity-report-latest.txt"
$score = Join-Path $astro "ASTRODDS-367-final-11-of-11-scorecard-latest.txt"
$premium = Join-Path $astro "ASTRODDS-362-premium-readiness-report-latest.txt"
$milestone = Join-Path $astro "ASTRODDS-374-settled-results-milestone-promoter-latest.txt"

$sections = @(
    @("CLIENT SUMMARY", $client),
    @("ADMIN REPORT", $admin),
    @("SETTLEMENT", $settle),
    @("11/11 SCORECARD", $score),
    @("PREMIUM READINESS", $premium),
    @("MILESTONE", $milestone)
)

$reportLines = @()
$reportLines += "ASTRODDS DAILY 2:30AM REPORT"
$reportLines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$reportLines += ""
$reportLines += "Purpose:"
$reportLines += "- Settlement, ROI, performance, readiness."
$reportLines += "- This report never sends new Moneyline picks."
$reportLines += "- Moneyline picks are only sent through pre-game market/lineup/edge gates."
$reportLines += ""

foreach ($s in $sections) {
    $title = $s[0]; $path = $s[1]
    $reportLines += ""
    $reportLines += "===== $title ====="
    if (Test-Path $path) { $reportLines += (Get-Content $path -Raw) }
    else { $reportLines += "MISSING: $path" }
}

if ($action -eq "RUN_230AM_REPORT_ONLY") {
    $reportLines | Set-Content -Encoding UTF8 $dailyReport
    $dateKey | Set-Content -Encoding UTF8 $sentState
}

$lines = @()
$lines += "ASTRODDS 369 DAILY 2:30AM REPORT ROUTER"
$lines += ""
$lines += "Now: $($now.ToString('yyyy-MM-dd HH:mm:ss'))"
$lines += "Window: 02:15 to 02:55"
$lines += "In window: $inWindow"
$lines += "Already done today: $alreadyDone"
$lines += "Action: $action"
$lines += "Daily report: $dailyReport"
$lines += ""
$lines += "MONEYLINE SAFETY"
$lines += "- 2:30 AM report does NOT send picks."
$lines += "- New Moneyline send remains pre-game only."
$lines += "- No picks after game start."

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    now=$now.ToString("o")
    dateKey=$dateKey
    inWindow=$inWindow
    alreadyDoneToday=$alreadyDone
    action=$action
    dailyReport=$dailyReport
    sendMoneylineAt230am=$false
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
