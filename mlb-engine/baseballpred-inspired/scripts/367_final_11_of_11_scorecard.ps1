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

function JVal($obj, $names, $default = "") {
    if ($null -eq $obj) { return $default }
    foreach ($n in @($names)) {
        try {
            $p = $obj.PSObject.Properties[$n]
            if ($null -ne $p -and $null -ne $p.Value) {
                $v = "$($p.Value)".Trim()
                if ($v -ne "") { return $v }
            }
        } catch {}
    }
    return $default
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

$outTxt = Join-Path $astro "ASTRODDS-367-final-11-of-11-scorecard-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-367-final-11-of-11-scorecard-latest.json"

Write-Host ""
Write-Host "ASTRODDS 367 FINAL 11/11 SCORECARD" -ForegroundColor Cyan
Write-Host "11/11 means local production-safe system readiness, not fake premium-source completeness." -ForegroundColor Cyan
Write-Host ""

$pkgPath = Join-Path $root "package.json"
$heartbeatPath = Join-Path $astro "ASTRODDS-343-one-command-heartbeat-latest.txt"

$envDoc = Read-JsonSafe (Join-Path $astro "ASTRODDS-328-env-autofinder-loader-latest.json")
$credit = Read-JsonSafe (Join-Path $astro "ASTRODDS-310-credit-budget-dashboard-latest.json")
$planner = Read-JsonSafe (Join-Path $astro "ASTRODDS-337-smart-scan-window-planner-latest.json")
$settlement = Read-JsonSafe (Join-Path $astro "ASTRODDS-349-settlement-integrity-report-latest.json")
$dataset = Read-JsonSafe (Join-Path $astro "ASTRODDS-350-training-dataset-from-settled-ledger-latest.json")
$ump = Read-JsonSafe (Join-Path $astro "ASTRODDS-357-umpire-real-source-bridge-latest.json")
$bp = Read-JsonSafe (Join-Path $astro "ASTRODDS-360-bullpen-pitch-availability-upgrade-latest.json")
$cal = Read-JsonSafe (Join-Path $astro "ASTRODDS-366-bullpen-stress-calibration-latest.json")
$premium = Read-JsonSafe (Join-Path $astro "ASTRODDS-362-premium-readiness-report-latest.json")
$readiness = Read-JsonSafe (Join-Path $astro "ASTRODDS-352-final-100-readiness-report-latest.json")

$pkgOk = $false
if (Test-Path $pkgPath) {
    try {
        $pkg = Get-Content $pkgPath -Raw | ConvertFrom-Json
        if ($pkg.scripts.astrodds) { $pkgOk = $true }
    } catch {}
}

$heartbeatOk = $false
$heartbeatStatus = "MISSING"
if (Test-Path $heartbeatPath) {
    $hb = Get-Content $heartbeatPath -Raw
    if ($hb -match "Status:\s*(RUNNING|SLEEPING)") {
        $heartbeatOk = $true
        $heartbeatStatus = $matches[1]
    }
}

$checks = @()

function Add-Check($id, $name, $pass, $detail) {
    return [pscustomobject]@{
        Id=$id
        Name=$name
        Pass=[bool]$pass
        Detail=$detail
    }
}

$checks += Add-Check 1 "One-command npm run astrodds installed" $pkgOk "package.json script astrodds present"
$checks += Add-Check 2 "Autopilot heartbeat alive" $heartbeatOk "heartbeat=$heartbeatStatus"
$checks += Add-Check 3 "Env autoload ready" ((JVal $envDoc @("envFound") "False") -eq "True") ("envFound=" + (JVal $envDoc @("envFound") "False"))
$checks += Add-Check 4 "Credit guard OK" ((JVal $credit @("status","Status") "UNKNOWN") -eq "OK") ("creditStatus=" + (JVal $credit @("status","Status") "UNKNOWN"))
$checks += Add-Check 5 "Smart planner ready" ($null -ne $planner) "planner report exists"
$checks += Add-Check 6 "Settlement clean" ((JVal $settlement @("pending","Pending") "999") -eq "0") ("pending=" + (JVal $settlement @("pending","Pending") "UNKNOWN") + " settled=" + (JVal $settlement @("settled","Settled") "UNKNOWN"))
$checks += Add-Check 7 "Training labels connected" ([int](JVal $dataset @("labeledSettledRows","LabeledSettledRows") "0") -ge 1) ("labeledRows=" + (JVal $dataset @("labeledSettledRows","LabeledSettledRows") "0"))
$checks += Add-Check 8 "Real umpire bridge connected" ([int](JVal $ump @("homePlateConnected") "0") -gt 0) ("homePlateConnected=" + (JVal $ump @("homePlateConnected") "0"))
$checks += Add-Check 9 "Real bullpen pitch usage connected" ([int](JVal $bp @("realPitchCountsConnectedTeams","realBullpenUsageConnectedTeams") "0") -gt 0) ("pitchCountsTeams=" + (JVal $bp @("realPitchCountsConnectedTeams","realBullpenUsageConnectedTeams") "0"))
$checks += Add-Check 10 "Bullpen stress calibrated" ([int](JVal $cal @("calibratedConnectedTeams") "0") -gt 0) ("calibratedTeams=" + (JVal $cal @("calibratedConnectedTeams") "0"))
$checks += Add-Check 11 "No-fake premium policy active" ((JVal $premium @("status") "UNKNOWN") -eq "PREMIUM_BRIDGE_READY_NO_FAKE_DATA") ("premiumStatus=" + (JVal $premium @("status") "UNKNOWN"))

$passed = @($checks | Where-Object { $_.Pass }).Count
$total = $checks.Count

$status = if ($passed -eq $total) { "ASTRODDS_11_OF_11_READY_LOCAL_TEST_MODE" } else { "ASTRODDS_NOT_11_OF_11_YET" }

$lines = @()
$lines += "ASTRODDS 367 FINAL 11/11 SCORECARD"
$lines += ""
$lines += "Status: $status"
$lines += "Score: $passed / $total"
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$lines += ""
$lines += "CHECKS"
foreach ($c in $checks) {
    $icon = if ($c.Pass) { "PASS" } else { "FAIL" }
    $lines += "$($c.Id). $icon | $($c.Name) | $($c.Detail)"
}
$lines += ""
$lines += "HONEST NOTE"
$lines += "- 11/11 means ASTRODDS local production-safe system is complete and no-fake premium bridge is active."
$lines += "- It does not mean platoon/xFIP/true leverage are magically connected; those remain MISSING_SOURCE until real CSV/API is provided."
$lines += "- The model is not statistically proven until enough real settled results accumulate."

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    status=$status
    score="$passed / $total"
    passed=$passed
    total=$total
    checks=@($checks)
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
