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
$scripts = Join-Path $root "mlb-engine\baseballpred-inspired\scripts"
Ensure-Dir $astro

$outTxt = Join-Path $astro "ASTRODDS-351-FINAL-SETTLEMENT-TRAINING-SYNC-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-351-FINAL-SETTLEMENT-TRAINING-SYNC-latest.json"
$outChild = Join-Path $astro "ASTRODDS-351-child-log-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 351D FINAL SYNC + 2:30AM + REAL PREMIUM FINISH" -ForegroundColor Cyan
Write-Host ""

$child = @()
$ref = [ref]$child

$steps = @()
$steps += ,(Run-Step "347 force settle pending officials" (Join-Path $scripts "347_force_settle_pending_officials.ps1") $ref)
$steps += ,(Run-Step "350 training dataset from settled ledger" (Join-Path $scripts "350_training_dataset_from_settled_ledger.ps1") $ref)
$steps += ,(Run-Step "322 train model policy" (Join-Path $scripts "322_train_model_when_ready_policy.ps1") $ref)
$steps += ,(Run-Step "349 settlement integrity report" (Join-Path $scripts "349_settlement_integrity_report.ps1") $ref)
$steps += ,(Run-Step "356 performance milestone tracker" (Join-Path $scripts "356_performance_milestone_tracker.ps1") $ref)
$steps += ,(Run-Step "370 real premium CSV schema validator" (Join-Path $scripts "370_real_premium_csv_schema_validator.ps1") $ref)
$steps += ,(Run-Step "357 umpire real source bridge" (Join-Path $scripts "357_umpire_real_source_bridge.ps1") $ref)
$steps += ,(Run-Step "358 platoon splits real source bridge" (Join-Path $scripts "358_platoon_splits_real_source_bridge.ps1") $ref)
$steps += ,(Run-Step "371 platoon real CSV finalizer" (Join-Path $scripts "371_platoon_real_csv_finalizer.ps1") $ref)
$steps += ,(Run-Step "359 starter xFIP real source bridge" (Join-Path $scripts "359_starter_xfip_real_source_bridge.ps1") $ref)
$steps += ,(Run-Step "372 FanGraphs xFIP real CSV finalizer" (Join-Path $scripts "372_fangraphs_xfip_real_csv_finalizer.ps1") $ref)
$steps += ,(Run-Step "360 bullpen pitch availability" (Join-Path $scripts "360_bullpen_pitch_availability_upgrade.ps1") $ref)
$steps += ,(Run-Step "366 bullpen stress calibration" (Join-Path $scripts "366_bullpen_stress_calibration.ps1") $ref)
$steps += ,(Run-Step "373 true leverage real CSV finalizer" (Join-Path $scripts "373_true_leverage_real_csv_finalizer.ps1") $ref)
$steps += ,(Run-Step "361 premium real source merge" (Join-Path $scripts "361_premium_real_source_merge.ps1") $ref)
$steps += ,(Run-Step "362 premium readiness report" (Join-Path $scripts "362_premium_readiness_report.ps1") $ref)
$steps += ,(Run-Step "374 settled results milestone promoter" (Join-Path $scripts "374_settled_results_milestone_promoter.ps1") $ref)
$steps += ,(Run-Step "309 client/admin report builder" (Join-Path $scripts "309_client_admin_report_builder.ps1") $ref)
$steps += ,(Run-Step "312 final readiness gate" (Join-Path $scripts "312_final_readiness_gate.ps1") $ref)
$steps += ,(Run-Step "352 final 100 readiness report" (Join-Path $scripts "352_final_100_readiness_report.ps1") $ref)
$steps += ,(Run-Step "367 final 11/11 scorecard" (Join-Path $scripts "367_final_11_of_11_scorecard.ps1") $ref)
$steps += ,(Run-Step "369 daily 2:30AM report router" (Join-Path $scripts "369_daily_230am_report_router.ps1") $ref)
$steps += ,(Run-Step "375 moneyline send guard audit" (Join-Path $scripts "375_moneyline_send_guard_and_daily_report_audit.ps1") $ref)

$child | Set-Content -Encoding UTF8 $outChild

$guardTxt = Join-Path $astro "ASTRODDS-375-moneyline-send-guard-and-daily-report-audit-latest.txt"
$premiumTxt = Join-Path $astro "ASTRODDS-362-premium-readiness-report-latest.txt"
$guard = ""; $premium = ""
if (Test-Path $guardTxt) { $guard = Get-Content $guardTxt -Raw }
if (Test-Path $premiumTxt) { $premium = Get-Content $premiumTxt -Raw }

$lines = @()
$lines += "ASTRODDS 351D FINAL SYNC + 2:30AM + REAL PREMIUM FINISH"
$lines += ""
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$lines += ""
$lines += "STEPS"
foreach ($s in $steps) { $lines += "- $($s.Name): $($s.Status) | Exit=$($s.ExitCode) | Duration=$($s.DurationSec)s" }
$lines += ""
$lines += "MONEYLINE / 2:30AM GUARD"
$lines += $guard
$lines += ""
$lines += "PREMIUM"
$lines += $premium

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    steps=@($steps)
    guardReport=$guardTxt
    premiumReport=$premiumTxt
    childLog=$outChild
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
