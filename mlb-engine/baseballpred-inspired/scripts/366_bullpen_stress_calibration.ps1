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

$rawCsv = Join-Path $astro "ASTRODDS-360-bullpen-pitch-usage-raw-latest.csv"
$plannerCsv = Join-Path $astro "ASTRODDS-smart-scan-window-plan-latest.csv"
$outCsv = Join-Path $astro "ASTRODDS-366-bullpen-stress-calibration-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-366-bullpen-stress-calibration-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-366-bullpen-stress-calibration-latest.json"

Write-Host ""
Write-Host "ASTRODDS 366 BULLPEN STRESS CALIBRATION" -ForegroundColor Cyan
Write-Host "Calibrates real MLB bullpen usage into more realistic LOW/MEDIUM/HIGH stress." -ForegroundColor Cyan
Write-Host ""

$raw = Safe-Csv $rawCsv
$planner = Safe-Csv $plannerCsv

$currentTeams = @()
foreach ($g in $planner) {
    $game = Get-Val $g @("Game")
    if ($game -match "\s@\s") {
        $p = $game -split "\s@\s", 2
        $currentTeams += $p[0]
        $currentTeams += $p[1]
    }
}
$currentTeams = @($currentTeams | Where-Object { "$_".Trim() -ne "" } | Select-Object -Unique)

function Team-Match($a, $b) {
    $na = Normalize-Name $a
    $nb = Normalize-Name $b
    if ($na -eq "" -or $nb -eq "") { return $false }
    if ($na -eq $nb) { return $true }
    if ($na.Contains($nb) -or $nb.Contains($na)) { return $true }
    $aw = @($na -split " ")
    $bw = @($nb -split " ")
    $alast = $aw[$aw.Count-1]
    $blast = $bw[$bw.Count-1]
    return ($alast -eq $blast -and $alast.Length -gt 3)
}

$today = (Get-Date).Date
$todayKey = $today.ToString("yyyy-MM-dd")
$yesterdayKey = $today.AddDays(-1).ToString("yyyy-MM-dd")

$out = @()

foreach ($team in $currentTeams) {
    $rows = @($raw | Where-Object { Team-Match (Get-Val $_ @("Team")) $team -and (Get-Val $_ @("Role")) -eq "BULLPEN_USED" })

    $todayRows = @($rows | Where-Object { (Get-Val $_ @("Date")) -eq $todayKey })
    $yesterdayRows = @($rows | Where-Object { (Get-Val $_ @("Date")) -eq $yesterdayKey })
    $last3Rows = @($rows | Where-Object {
        try { ([datetime](Get-Val $_ @("Date"))) -ge $today.AddDays(-3) } catch { $false }
    })

    $pitchesToday = 0
    $pitchesYesterday = 0
    $pitchesLast3 = 0
    $knownPitchRows = 0
    $maxPitchesSingleRelieverToday = 0
    $maxPitchesSingleRelieverYesterday = 0

    foreach ($r in $last3Rows) {
        $n = Num (Get-Val $r @("Pitches"))
        if ($null -ne $n) {
            $knownPitchRows++
            $pitchesLast3 += [int]$n
        }
    }
    foreach ($r in $todayRows) {
        $n = Num (Get-Val $r @("Pitches"))
        if ($null -ne $n) {
            $pitchesToday += [int]$n
            if ($n -gt $maxPitchesSingleRelieverToday) { $maxPitchesSingleRelieverToday = [int]$n }
        }
    }
    foreach ($r in $yesterdayRows) {
        $n = Num (Get-Val $r @("Pitches"))
        if ($null -ne $n) {
            $pitchesYesterday += [int]$n
            if ($n -gt $maxPitchesSingleRelieverYesterday) { $maxPitchesSingleRelieverYesterday = [int]$n }
        }
    }

    $relieversToday = @($todayRows | Select-Object -ExpandProperty Pitcher -Unique).Count
    $relieversYesterday = @($yesterdayRows | Select-Object -ExpandProperty Pitcher -Unique).Count
    $relieversLast3 = @($last3Rows | Select-Object -ExpandProperty Pitcher -Unique).Count

    $pitcherDates = @{}
    foreach ($r in $last3Rows) {
        $pn = Normalize-Name (Get-Val $r @("Pitcher"))
        $dt = Get-Val $r @("Date")
        if ($pn -eq "" -or $dt -eq "") { continue }
        if (-not $pitcherDates.ContainsKey($pn)) { $pitcherDates[$pn] = New-Object System.Collections.Generic.HashSet[string] }
        [void]$pitcherDates[$pn].Add($dt)
    }

    $backToBackRelievers = 0
    foreach ($k in $pitcherDates.Keys) {
        if ($pitcherDates[$k].Count -ge 2) { $backToBackRelievers++ }
    }

    $stress = "UNKNOWN"
    $stressScore = 0
    $reasons = @()

    if ($last3Rows.Count -gt 0 -and $knownPitchRows -gt 0) {
        # More realistic thresholds:
        # HIGH only for heavy recent load or multiple danger signals.
        if ($pitchesToday -ge 85) { $stressScore += 4; $reasons += "85+ bullpen pitches today" }
        elseif ($pitchesToday -ge 55) { $stressScore += 2; $reasons += "55+ bullpen pitches today" }

        if ($pitchesYesterday -ge 80) { $stressScore += 3; $reasons += "80+ bullpen pitches yesterday" }
        elseif ($pitchesYesterday -ge 50) { $stressScore += 1; $reasons += "50+ bullpen pitches yesterday" }

        if ($pitchesLast3 -ge 240) { $stressScore += 4; $reasons += "240+ bullpen pitches last 3 days" }
        elseif ($pitchesLast3 -ge 160) { $stressScore += 2; $reasons += "160+ bullpen pitches last 3 days" }

        if ($relieversToday -ge 5) { $stressScore += 3; $reasons += "5+ relievers used today" }
        elseif ($relieversToday -ge 3) { $stressScore += 1; $reasons += "3+ relievers used today" }

        if ($backToBackRelievers -ge 3) { $stressScore += 3; $reasons += "3+ relievers used multiple days" }
        elseif ($backToBackRelievers -ge 1) { $stressScore += 1; $reasons += "back-to-back reliever usage" }

        if ($maxPitchesSingleRelieverToday -ge 35 -or $maxPitchesSingleRelieverYesterday -ge 35) {
            $stressScore += 2; $reasons += "single reliever 35+ pitches recent"
        }

        if ($stressScore -ge 7) { $stress = "HIGH_CALIBRATED_REAL_PITCH_STRESS" }
        elseif ($stressScore -ge 3) { $stress = "MEDIUM_CALIBRATED_REAL_PITCH_STRESS" }
        else { $stress = "LOW_CALIBRATED_REAL_PITCH_STRESS" }
    } elseif ($last3Rows.Count -gt 0) {
        # Real usage but no pitch counts: weaker estimate.
        if ($relieversToday -ge 5 -or $relieversLast3 -ge 10) { $stress = "HIGH_CALIBRATED_REAL_USAGE_NO_PITCH_COUNTS"; $stressScore = 6 }
        elseif ($relieversToday -ge 3 -or $relieversLast3 -ge 5) { $stress = "MEDIUM_CALIBRATED_REAL_USAGE_NO_PITCH_COUNTS"; $stressScore = 3 }
        else { $stress = "LOW_CALIBRATED_REAL_USAGE_NO_PITCH_COUNTS"; $stressScore = 1 }
        $reasons += "pitcher usage connected but pitch counts missing"
    }

    if ($reasons.Count -eq 0) { $reasons += "no heavy bullpen stress signal" }

    $out += ,[pscustomobject]@{
        Team=$team
        CalibratedBullpenStress=$stress
        StressScore=$stressScore
        StressReasons=($reasons -join "; ")
        BullpenPitchesToday=if ($knownPitchRows -gt 0) { $pitchesToday } else { "" }
        BullpenPitchesYesterday=if ($knownPitchRows -gt 0) { $pitchesYesterday } else { "" }
        BullpenPitchesLast3Days=if ($knownPitchRows -gt 0) { $pitchesLast3 } else { "" }
        RelieversUsedToday=$relieversToday
        RelieversUsedYesterday=$relieversYesterday
        RelieversUsedLast3Days=$relieversLast3
        BackToBackRelievers=$backToBackRelievers
        MaxPitchesSingleRelieverToday=if ($knownPitchRows -gt 0) { $maxPitchesSingleRelieverToday } else { "" }
        MaxPitchesSingleRelieverYesterday=if ($knownPitchRows -gt 0) { $maxPitchesSingleRelieverYesterday } else { "" }
        Source="MLB boxscore pitcher usage + pitch counts"
        UpdatedAt=(Get-Date).ToString("o")
    }
}

$out | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$connected = @($out | Where-Object { $_.CalibratedBullpenStress -ne "UNKNOWN" }).Count
$high = @($out | Where-Object { $_.CalibratedBullpenStress -match "^HIGH" }).Count
$medium = @($out | Where-Object { $_.CalibratedBullpenStress -match "^MEDIUM" }).Count
$low = @($out | Where-Object { $_.CalibratedBullpenStress -match "^LOW" }).Count

$lines = @()
$lines += "ASTRODDS 366 BULLPEN STRESS CALIBRATION"
$lines += ""
$lines += "Teams: $($out.Count)"
$lines += "Calibrated connected teams: $connected"
$lines += "High stress: $high"
$lines += "Medium stress: $medium"
$lines += "Low stress: $low"
$lines += "Output: $outCsv"
$lines += ""
$lines += "RULE"
$lines += "- Uses only real boxscore pitcher usage/pitch counts."
$lines += "- No true leverage is invented."
$lines += "- HIGH is now stricter than the raw 360 rule."
$lines += ""
foreach ($r in $out) {
    $lines += "- $($r.Team) | $($r.CalibratedBullpenStress) | score=$($r.StressScore) | today=$($r.BullpenPitchesToday) | yday=$($r.BullpenPitchesYesterday) | 3d=$($r.BullpenPitchesLast3Days) | b2b=$($r.BackToBackRelievers)"
}

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    teams=$out.Count
    calibratedConnectedTeams=$connected
    highStress=$high
    mediumStress=$medium
    lowStress=$low
    outputCsv=$outCsv
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
