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

$eliteCsv = Join-Path $astro "ASTRODDS-elite-factor-context-latest.csv"
$plannerCsv = Join-Path $astro "ASTRODDS-smart-scan-window-plan-latest.csv"
$inputCsv = Join-Path $astro "ASTRODDS-premium-input-team-platoon-splits.csv"
$outCsv = Join-Path $astro "ASTRODDS-358-platoon-splits-real-source-bridge-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-358-platoon-splits-real-source-bridge-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-358-platoon-splits-real-source-bridge-latest.json"

Write-Host ""
Write-Host "ASTRODDS 358 PLATOON SPLITS REAL SOURCE BRIDGE" -ForegroundColor Cyan
Write-Host "Reads real team platoon split CSV/export. Empty source = MISSING_SOURCE, not fake." -ForegroundColor Cyan
Write-Host ""

if (!(Test-Path $inputCsv)) {
    "Team,VsHand,wRCPlus,OPS,OBP,SLG,KPercent,BBPercent,Source,UpdatedAt" | Set-Content -Encoding UTF8 $inputCsv
}

$source = Safe-Csv $inputCsv
$elite = Safe-Csv $eliteCsv
$plan = Safe-Csv $plannerCsv

if ($elite.Count -eq 0) {
    foreach ($g in $plan) {
        $game = Get-Val $g @("Game")
        if ($game -match "\s@\s") {
            $parts = $game -split "\s@\s", 2
            $elite += ,[pscustomobject]@{ Game=$game; AwayTeam=$parts[0]; HomeTeam=$parts[1]; AwayStarterHand=""; HomeStarterHand="" }
        }
    }
}

function Find-Split($team, $vsHand, $rows) {
    $nt = Normalize-Name $team
    $vh = "$vsHand".ToUpper().Trim()
    foreach ($r in $rows) {
        $rt = Normalize-Name (Get-Val $r @("Team"))
        $rh = (Get-Val $r @("VsHand","Hand")).ToUpper().Trim()
        if ($rt -eq $nt -and $rh -eq $vh) { return $r }
    }
    return $null
}

$out = @()

foreach ($g in $elite) {
    $game = Get-Val $g @("Game")
    $away = Get-Val $g @("AwayTeam","Away")
    $homeTeam = Get-Val $g @("HomeTeam","Home")
    if (($away -eq "" -or $homeTeam -eq "") -and $game -match "\s@\s") {
        $parts = $game -split "\s@\s", 2
        $away = $parts[0]; $homeTeam = $parts[1]
    }

    $awayStarterHand = Get-Val $g @("AwayStarterHand","AwayPitcherHand","AwayThrows")
    $homeStarterHand = Get-Val $g @("HomeStarterHand","HomePitcherHand","HomeThrows")

    # Away hitters face home starter; home hitters face away starter.
    $awayVs = if ($homeStarterHand -match "^L") { "L" } elseif ($homeStarterHand -match "^R") { "R" } else { "" }
    $homeVs = if ($awayStarterHand -match "^L") { "L" } elseif ($awayStarterHand -match "^R") { "R" } else { "" }

    $awaySplit = if ($awayVs -ne "") { Find-Split $away $awayVs $source } else { $null }
    $homeSplit = if ($homeVs -ne "") { Find-Split $homeTeam $homeVs $source } else { $null }

    $awayStatus = if ($awayVs -eq "") { "MISSING_OPPONENT_STARTER_HAND" } elseif ($null -ne $awaySplit) { "CSV_REAL_PLATOON_CONNECTED" } else { "MISSING_SOURCE" }
    $homeStatus = if ($homeVs -eq "") { "MISSING_OPPONENT_STARTER_HAND" } elseif ($null -ne $homeSplit) { "CSV_REAL_PLATOON_CONNECTED" } else { "MISSING_SOURCE" }

    $out += ,[pscustomobject]@{
        Game=$game
        AwayTeam=$away
        HomeTeam=$homeTeam
        AwayHittersVs=$awayVs
        HomeHittersVs=$homeVs
        AwayPlatoonStatus=$awayStatus
        HomePlatoonStatus=$homeStatus
        AwayWRCPlus=Get-Val $awaySplit @("wRCPlus","WRCPlus")
        HomeWRCPlus=Get-Val $homeSplit @("wRCPlus","WRCPlus")
        AwayOPS=Get-Val $awaySplit @("OPS")
        HomeOPS=Get-Val $homeSplit @("OPS")
        AwaySource=Get-Val $awaySplit @("Source")
        HomeSource=Get-Val $homeSplit @("Source")
        InputCsv=$inputCsv
        UpdatedAt=(Get-Date).ToString("o")
    }
}

$out | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$connectedRows = @($out | Where-Object { $_.AwayPlatoonStatus -eq "CSV_REAL_PLATOON_CONNECTED" -or $_.HomePlatoonStatus -eq "CSV_REAL_PLATOON_CONNECTED" }).Count
$fullRows = @($out | Where-Object { $_.AwayPlatoonStatus -eq "CSV_REAL_PLATOON_CONNECTED" -and $_.HomePlatoonStatus -eq "CSV_REAL_PLATOON_CONNECTED" }).Count

$lines = @()
$lines += "ASTRODDS 358 PLATOON SPLITS REAL SOURCE BRIDGE"
$lines += ""
$lines += "Rows: $($out.Count)"
$lines += "Rows with any platoon source: $connectedRows"
$lines += "Rows fully connected: $fullRows"
$lines += "Input CSV template: $inputCsv"
$lines += ""
$lines += "RULE"
$lines += "- If the CSV/export is missing, platoon status stays MISSING_SOURCE."
$lines += "- No platoon edge is created from blanks."
$lines += ""
foreach ($r in $out) {
    $lines += "- $($r.Game) | away=$($r.AwayPlatoonStatus) vs $($r.AwayHittersVs) | home=$($r.HomePlatoonStatus) vs $($r.HomeHittersVs)"
}

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    rows=$out.Count
    rowsWithAnySource=$connectedRows
    rowsFullyConnected=$fullRows
    outputCsv=$outCsv
    inputCsv=$inputCsv
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
