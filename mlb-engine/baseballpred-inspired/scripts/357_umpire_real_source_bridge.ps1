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

function Find-HomePlateUmpire($feed) {
    $paths = @()
    try { $paths += @($feed.liveData.boxscore.officials) } catch {}
    try { $paths += @($feed.gameData.officials) } catch {}
    try { $paths += @($feed.liveData.officials) } catch {}

    foreach ($o in $paths) {
        if ($null -eq $o) { continue }
        $type = Get-Val $o @("officialType","type","position","title","assignment")
        $name = ""
        try { $name = "$($o.official.fullName)".Trim() } catch {}
        if ($name -eq "") { $name = Get-Val $o @("fullName","name","officialName") }
        if ($type -match "Home|Plate|HP" -and $name -ne "") { return $name }
    }

    # Last-resort JSON text search for officialType/name shape; no fabricated value.
    try {
        $json = $feed | ConvertTo-Json -Depth 100
        if ($json -match '"officialType"\s*:\s*"Home Plate"[\s\S]{0,250}?"fullName"\s*:\s*"([^"]+)"') {
            return $matches[1]
        }
        if ($json -match '"fullName"\s*:\s*"([^"]+)"[\s\S]{0,250}?"officialType"\s*:\s*"Home Plate"') {
            return $matches[1]
        }
    } catch {}

    return ""
}

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$plannerCsv = Join-Path $astro "ASTRODDS-smart-scan-window-plan-latest.csv"
$ratingsCsv = Join-Path $astro "ASTRODDS-premium-input-umpire-ratings.csv"
$outCsv = Join-Path $astro "ASTRODDS-357-umpire-real-source-bridge-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-357-umpire-real-source-bridge-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-357-umpire-real-source-bridge-latest.json"

Write-Host ""
Write-Host "ASTRODDS 357 UMPIRE REAL SOURCE BRIDGE" -ForegroundColor Cyan
Write-Host "Uses MLB feed/live officials when available. Optional rating CSV only. No fake umpire values." -ForegroundColor Cyan
Write-Host ""

if (!(Test-Path $ratingsCsv)) {
    "HomePlateUmpire,UmpireRunsPlusMinus,OverPct,HomeWinPct,StrikeZoneGrade,Source,UpdatedAt" | Set-Content -Encoding UTF8 $ratingsCsv
}

$ratings = Safe-Csv $ratingsCsv
$plan = Safe-Csv $plannerCsv

# If planner missing, fetch today's schedule.
if ($plan.Count -eq 0) {
    $date = (Get-Date).ToString("yyyy-MM-dd")
    $resp = Invoke-Json "https://statsapi.mlb.com/api/v1/schedule?sportId=1&date=$date&hydrate=team" 30
    foreach ($d in @($resp.dates)) {
        foreach ($g in @($d.games)) {
            $away = "$($g.teams.away.team.name)"
            $homeTeam = "$($g.teams.home.team.name)"
            $plan += ,[pscustomobject]@{ GamePk="$($g.gamePk)"; Game="$away @ $homeTeam"; MlbStatus="$($g.status.detailedState)" }
        }
    }
}

$out = @()

foreach ($g in $plan) {
    $gamePk = Get-Val $g @("GamePk")
    $game = Get-Val $g @("Game")
    if ($gamePk -eq "") {
        $out += ,[pscustomobject]@{
            Game=$game; GamePk=""; MlbStatus=Get-Val $g @("MlbStatus")
            HomePlateUmpire=""; UmpireSourceStatus="MISSING_GAMEPK"
            UmpireRatingStatus="MISSING_SOURCE"; UmpireRunsPlusMinus=""; OverPct=""; HomeWinPct=""; StrikeZoneGrade=""
            Source=""; UpdatedAt=(Get-Date).ToString("o")
        }
        continue
    }

    $feed = Invoke-Json "https://statsapi.mlb.com/api/v1.1/game/$gamePk/feed/live" 30
    $ump = ""
    if ($null -ne $feed) { $ump = Find-HomePlateUmpire $feed }

    $sourceStatus = if ($ump -ne "") { "MLB_STATSAPI_HOME_PLATE_UMPIRE_CONNECTED" } else { "MISSING_OR_NOT_POSTED_YET" }

    $rating = $null
    if ($ump -ne "") {
        $norm = Normalize-Name $ump
        foreach ($r in $ratings) {
            if ((Normalize-Name (Get-Val $r @("HomePlateUmpire","Umpire","Name"))) -eq $norm) { $rating = $r; break }
        }
    }

    $ratingStatus = if ($null -ne $rating) { "CSV_RATING_CONNECTED" } else { "MISSING_RATING_SOURCE" }

    $out += ,[pscustomobject]@{
        Game=$game
        GamePk=$gamePk
        MlbStatus=Get-Val $g @("MlbStatus")
        HomePlateUmpire=$ump
        UmpireSourceStatus=$sourceStatus
        UmpireRatingStatus=$ratingStatus
        UmpireRunsPlusMinus=Get-Val $rating @("UmpireRunsPlusMinus")
        OverPct=Get-Val $rating @("OverPct")
        HomeWinPct=Get-Val $rating @("HomeWinPct")
        StrikeZoneGrade=Get-Val $rating @("StrikeZoneGrade")
        Source=if ($ump -ne "") { "MLB StatsAPI feed/live officials" } else { "" }
        RatingCsv=$ratingsCsv
        UpdatedAt=(Get-Date).ToString("o")
    }
}

$out | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$connected = @($out | Where-Object { $_.UmpireSourceStatus -eq "MLB_STATSAPI_HOME_PLATE_UMPIRE_CONNECTED" }).Count
$rated = @($out | Where-Object { $_.UmpireRatingStatus -eq "CSV_RATING_CONNECTED" }).Count

$lines = @()
$lines += "ASTRODDS 357 UMPIRE REAL SOURCE BRIDGE"
$lines += ""
$lines += "Rows: $($out.Count)"
$lines += "Home plate umpire connected: $connected"
$lines += "Umpire rating CSV connected: $rated"
$lines += "Rating CSV template: $ratingsCsv"
$lines += ""
$lines += "RULE"
$lines += "- If MLB feed does not post home plate umpire yet, status stays MISSING_OR_NOT_POSTED_YET."
$lines += "- If rating CSV is empty, no strike-zone advantage is created."
$lines += ""
foreach ($r in $out) {
    $lines += "- $($r.UmpireSourceStatus) | $($r.Game) | HP=$($r.HomePlateUmpire) | rating=$($r.UmpireRatingStatus)"
}

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    rows=$out.Count
    homePlateConnected=$connected
    ratingConnected=$rated
    outputCsv=$outCsv
    ratingCsv=$ratingsCsv
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
