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

function Invoke-Json($url, $timeout = 30) {
    try { return Invoke-RestMethod -Uri $url -Method Get -TimeoutSec $timeout }
    catch { return $null }
}

function Get-DateKey($d) {
    try { return ([datetime]$d).ToString("yyyy-MM-dd") } catch { return (Get-Date).ToString("yyyy-MM-dd") }
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

$plannerCsv = Join-Path $astro "ASTRODDS-smart-scan-window-plan-latest.csv"
$umpCsv = Join-Path $astro "ASTRODDS-357-umpire-real-source-bridge-latest.csv"
$platoonCsv = Join-Path $astro "ASTRODDS-358-platoon-splits-real-source-bridge-latest.csv"
$xfipCsv = Join-Path $astro "ASTRODDS-359-starter-xfip-real-source-bridge-latest.csv"
$bullpenCsv = Join-Path $astro "ASTRODDS-360-bullpen-pitch-availability-upgrade-latest.csv"
$outCsv = Join-Path $astro "ASTRODDS-361-premium-real-source-merge-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-361-premium-real-source-merge-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-361-premium-real-source-merge-latest.json"

Write-Host ""
Write-Host "ASTRODDS 361 PREMIUM REAL SOURCE MERGE" -ForegroundColor Cyan
Write-Host "Merges only real connected premium sources. Missing sources stay missing." -ForegroundColor Cyan
Write-Host ""

$plan = Safe-Csv $plannerCsv
$ump = Safe-Csv $umpCsv
$platoon = Safe-Csv $platoonCsv
$xfip = Safe-Csv $xfipCsv
$bullpen = Safe-Csv $bullpenCsv

function Find-GameRow($rows, $game) {
    $kg = Normalize-Name $game
    foreach ($r in $rows) {
        if ((Normalize-Name (Get-Val $r @("Game"))) -eq $kg) { return $r }
    }
    return $null
}

function Find-TeamBullpen($team) {
    $nt = Normalize-Name $team
    foreach ($r in $bullpen) {
        if ((Normalize-Name (Get-Val $r @("Team"))) -eq $nt) { return $r }
    }
    return $null
}

$out = @()

foreach ($g in $plan) {
    $game = Get-Val $g @("Game")
    $away = ""; $homeTeam = ""
    if ($game -match "\s@\s") {
        $p = $game -split "\s@\s", 2
        $away = $p[0]; $homeTeam = $p[1]
    }

    $u = Find-GameRow $ump $game
    $pRow = Find-GameRow $platoon $game
    $x = Find-GameRow $xfip $game
    $awayBp = Find-TeamBullpen $away
    $homeBp = Find-TeamBullpen $homeTeam

    $checks = @()
    $checks += (Get-Val $u @("UmpireSourceStatus"))
    $checks += (Get-Val $pRow @("AwayPlatoonStatus"))
    $checks += (Get-Val $pRow @("HomePlatoonStatus"))
    $checks += (Get-Val $x @("AwayXfipStatus"))
    $checks += (Get-Val $x @("HomeXfipStatus"))
    $checks += (Get-Val $awayBp @("PitchUsageStatus"))
    $checks += (Get-Val $homeBp @("PitchUsageStatus"))
    $checks += (Get-Val $awayBp @("TrueLeverageStatus"))
    $checks += (Get-Val $homeBp @("TrueLeverageStatus"))

    $realConnected = 0
    foreach ($c in $checks) {
        if ($c -match "CONNECTED") { $realConnected++ }
    }

    $premiumStatus = "PREMIUM_MISSING_REAL_SOURCES"
    if ($realConnected -ge 7) { $premiumStatus = "PREMIUM_REAL_CORE_CONNECTED" }
    elseif ($realConnected -ge 3) { $premiumStatus = "PREMIUM_PARTIAL_REAL_CONNECTED" }

    $out += ,[pscustomobject]@{
        Game=$game
        MlbStatus=Get-Val $g @("MlbStatus")
        PremiumRealSourceStatus=$premiumStatus
        RealConnectedSignals=$realConnected
        HomePlateUmpire=Get-Val $u @("HomePlateUmpire")
        UmpireSourceStatus=Get-Val $u @("UmpireSourceStatus")
        UmpireRatingStatus=Get-Val $u @("UmpireRatingStatus")
        AwayPlatoonStatus=Get-Val $pRow @("AwayPlatoonStatus")
        HomePlatoonStatus=Get-Val $pRow @("HomePlatoonStatus")
        AwayXfipStatus=Get-Val $x @("AwayXfipStatus")
        HomeXfipStatus=Get-Val $x @("HomeXfipStatus")
        AwayxFIP=Get-Val $x @("AwayxFIP")
        HomexFIP=Get-Val $x @("HomexFIP")
        AwayBullpenPitchUsageStatus=Get-Val $awayBp @("PitchUsageStatus")
        HomeBullpenPitchUsageStatus=Get-Val $homeBp @("PitchUsageStatus")
        AwayBullpenStress=Get-Val $awayBp @("BullpenStressFromRealPitches")
        HomeBullpenStress=Get-Val $homeBp @("BullpenStressFromRealPitches")
        AwayTrueLeverageStatus=Get-Val $awayBp @("TrueLeverageStatus")
        HomeTrueLeverageStatus=Get-Val $homeBp @("TrueLeverageStatus")
        SafetyRule="Missing premium data does not create official edge."
        UpdatedAt=(Get-Date).ToString("o")
    }
}

$out | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$core = @($out | Where-Object { $_.PremiumRealSourceStatus -eq "PREMIUM_REAL_CORE_CONNECTED" }).Count
$partial = @($out | Where-Object { $_.PremiumRealSourceStatus -eq "PREMIUM_PARTIAL_REAL_CONNECTED" }).Count
$missing = @($out | Where-Object { $_.PremiumRealSourceStatus -eq "PREMIUM_MISSING_REAL_SOURCES" }).Count

$lines = @()
$lines += "ASTRODDS 361 PREMIUM REAL SOURCE MERGE"
$lines += ""
$lines += "Rows: $($out.Count)"
$lines += "Premium real core connected: $core"
$lines += "Premium partial real connected: $partial"
$lines += "Premium missing real sources: $missing"
$lines += ""
$lines += "RULE"
$lines += "- Missing premium data does not create official edge."
$lines += "- This board is context/readiness only until sources are real."
$lines += ""
foreach ($r in $out) {
    $lines += "- $($r.PremiumRealSourceStatus) | $($r.Game) | signals=$($r.RealConnectedSignals) | ump=$($r.UmpireSourceStatus) | xFIP=$($r.AwayXfipStatus)/$($r.HomeXfipStatus) | BP=$($r.AwayBullpenPitchUsageStatus)/$($r.HomeBullpenPitchUsageStatus)"
}

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    rows=$out.Count
    premiumRealCoreConnected=$core
    premiumPartialRealConnected=$partial
    premiumMissingRealSources=$missing
    outputCsv=$outCsv
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
