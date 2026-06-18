$ErrorActionPreference = "Continue"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$scheduleCsv = Join-Path $astro "ASTRODDS-source-mlb-schedule-latest.csv"
$outCsv = Join-Path $astro "ASTRODDS-bullpen-fatigue-context-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-274-rolling-bullpen-3d-7d-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-274-rolling-bullpen-3d-7d-latest.json"

Write-Host ""
Write-Host "ASTRODDS 274 ROLLING BULLPEN 3D/7D" -ForegroundColor Cyan
Write-Host "Source: MLB StatsAPI recent games + feed/live pitchers used proxy." -ForegroundColor Cyan
Write-Host ""


function Ensure-Dir($path) {
    if (!(Test-Path $path)) { New-Item -ItemType Directory -Force -Path $path | Out-Null }
}

function Invoke-Json($url, $timeout = 25) {
    try { return Invoke-RestMethod -Uri $url -Method Get -TimeoutSec $timeout }
    catch { return $null }
}

function Write-Json($obj, $path) {
    $obj | ConvertTo-Json -Depth 25 | Set-Content -Encoding UTF8 $path
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

function Normalize-Team($s) {
    $x = "$s".ToLower().Trim()
    $x = $x -replace "[^a-z0-9 ]", ""
    $x = $x -replace "\s+", " "
    return $x
}

function Game-Key($game) {
    $g = "$game"
    $awayTeamName = ""
    $homeTeamName = ""
    if ($g -match "\s@\s") {
        $parts = $g -split "\s@\s", 2
        $awayTeamName = "$($parts[0])".Trim()
        $homeTeamName = "$($parts[1])".Trim()
    } elseif ($g -match "\svs\s") {
        $parts = $g -split "\svs\s", 2
        $awayTeamName = "$($parts[0])".Trim()
        $homeTeamName = "$($parts[1])".Trim()
    } else {
        return (Normalize-Team $g)
    }
    return (Normalize-Team $awayTeamName) + " @ " + (Normalize-Team $homeTeamName)
}

function Find-By-Game($rows, $game) {
    $k = Game-Key $game
    foreach ($r in @($rows)) {
        $g = Get-Val $r @("Game","game")
        if ($g -eq "") { continue }
        if ((Game-Key $g) -eq $k) { return $r }
    }
    return $null
}

function Clamp($x, $lo, $hi) {
    if ($x -lt $lo) { return $lo }
    if ($x -gt $hi) { return $hi }
    return $x
}

$schedule = Safe-Csv $scheduleCsv
$today = Get-Date
$teams = @{}

foreach ($g in $schedule) {
    $away = Get-Val $g @("AwayTeam")
    $homeTeamName = Get-Val $g @("HomeTeam")
    if ($away -ne "") { $teams[$away] = $true }
    if ($homeTeamName -ne "") { $teams[$homeTeamName] = $true }
}

# Map team names to teamId from today's schedule rows if available from source JSON.
$scheduleJson = Join-Path $astro "ASTRODDS-source-mlb-schedule-latest.json"
$teamIds = @{}
try {
    $raw = Get-Content $scheduleJson -Raw | ConvertFrom-Json
    foreach ($d in @($raw.dates)) {
        foreach ($g in @($d.games)) {
            $teamIds["$($g.teams.away.team.name)"] = "$($g.teams.away.team.id)"
            $teamIds["$($g.teams.home.team.name)"] = "$($g.teams.home.team.id)"
        }
    }
} catch {}

$usage = @{}

foreach ($teamName in $teams.Keys) {
    $usage[$teamName] = [pscustomobject]@{
        Team = $teamName
        PitchersUsed3d = 0
        PitchersUsed7d = 0
        Games3d = 0
        Games7d = 0
        HeavyGames3d = 0
        HeavyGames7d = 0
    }
}

for ($i=1; $i -le 7; $i++) {
    $date = $today.AddDays(-$i).ToString("yyyy-MM-dd")
    $url = "https://statsapi.mlb.com/api/v1/schedule?sportId=1&date=$date"
    $sched = Invoke-Json $url 20
    if ($null -eq $sched -or $null -eq $sched.dates) { continue }

    foreach ($d in @($sched.dates)) {
        foreach ($gameObj in @($d.games)) {
            $gamePk = "$($gameObj.gamePk)"
            $awayTeamName = "$($gameObj.teams.away.team.name)"
            $homeTeamName = "$($gameObj.teams.home.team.name)"
            if (-not $usage.ContainsKey($awayTeamName) -and -not $usage.ContainsKey($homeTeamName)) { continue }

            $feedUrl = "https://statsapi.mlb.com/api/v1.1/game/$gamePk/feed/live"
            $feed = Invoke-Json $feedUrl 20
            $awayCount = 0
            $homeCount = 0
            try { $awayCount = @($feed.liveData.boxscore.teams.away.pitchers).Count } catch {}
            try { $homeCount = @($feed.liveData.boxscore.teams.home.pitchers).Count } catch {}

            if ($usage.ContainsKey($awayTeamName)) {
                $usage[$awayTeamName].PitchersUsed7d += $awayCount
                $usage[$awayTeamName].Games7d += 1
                if ($awayCount -ge 5) { $usage[$awayTeamName].HeavyGames7d += 1 }
                if ($i -le 3) {
                    $usage[$awayTeamName].PitchersUsed3d += $awayCount
                    $usage[$awayTeamName].Games3d += 1
                    if ($awayCount -ge 5) { $usage[$awayTeamName].HeavyGames3d += 1 }
                }
            }

            if ($usage.ContainsKey($homeTeamName)) {
                $usage[$homeTeamName].PitchersUsed7d += $homeCount
                $usage[$homeTeamName].Games7d += 1
                if ($homeCount -ge 5) { $usage[$homeTeamName].HeavyGames7d += 1 }
                if ($i -le 3) {
                    $usage[$homeTeamName].PitchersUsed3d += $homeCount
                    $usage[$homeTeamName].Games3d += 1
                    if ($homeCount -ge 5) { $usage[$homeTeamName].HeavyGames3d += 1 }
                }
            }
        }
    }
}

function Fatigue($pitchers, $games, $heavy) {
    if ($games -eq 0) { return "unknown" }
    $avg = $pitchers / [math]::Max(1,$games)
    if ($heavy -ge 2 -or $avg -ge 4.8) { return "high" }
    if ($heavy -ge 1 -or $avg -ge 3.6) { return "medium" }
    return "low"
}

$out = @()
foreach ($g in $schedule) {
    $game = Get-Val $g @("Game")
    $away = Get-Val $g @("AwayTeam")
    $homeTeamName = Get-Val $g @("HomeTeam")
    $a = $usage[$away]
    $h = $usage[$homeTeamName]

    $out += ,[pscustomobject]@{
        Source = "MLB_STATSAPI_ROLLING_BULLPEN_PROXY_3D_7D"
        ScheduleDate = Get-Date -Format "yyyy-MM-dd"
        GamePk = Get-Val $g @("GamePk")
        Game = $game
        AwayTeam = $away
        HomeTeam = $homeTeamName
        AwayPitchersUsed3d = if ($null -ne $a) { $a.PitchersUsed3d } else { "" }
        AwayGames3d = if ($null -ne $a) { $a.Games3d } else { "" }
        AwayHeavyGames3d = if ($null -ne $a) { $a.HeavyGames3d } else { "" }
        AwayBullpenFatigue3d = if ($null -ne $a) { Fatigue $a.PitchersUsed3d $a.Games3d $a.HeavyGames3d } else { "unknown" }
        AwayPitchersUsed7d = if ($null -ne $a) { $a.PitchersUsed7d } else { "" }
        AwayGames7d = if ($null -ne $a) { $a.Games7d } else { "" }
        AwayHeavyGames7d = if ($null -ne $a) { $a.HeavyGames7d } else { "" }
        AwayBullpenFatigue7d = if ($null -ne $a) { Fatigue $a.PitchersUsed7d $a.Games7d $a.HeavyGames7d } else { "unknown" }
        HomePitchersUsed3d = if ($null -ne $h) { $h.PitchersUsed3d } else { "" }
        HomeGames3d = if ($null -ne $h) { $h.Games3d } else { "" }
        HomeHeavyGames3d = if ($null -ne $h) { $h.HeavyGames3d } else { "" }
        HomeBullpenFatigue3d = if ($null -ne $h) { Fatigue $h.PitchersUsed3d $h.Games3d $h.HeavyGames3d } else { "unknown" }
        HomePitchersUsed7d = if ($null -ne $h) { $h.PitchersUsed7d } else { "" }
        HomeGames7d = if ($null -ne $h) { $h.Games7d } else { "" }
        HomeHeavyGames7d = if ($null -ne $h) { $h.HeavyGames7d } else { "" }
        HomeBullpenFatigue7d = if ($null -ne $h) { Fatigue $h.PitchersUsed7d $h.Games7d $h.HeavyGames7d } else { "unknown" }
        FetchedAt = (Get-Date).ToString("o")
    }
}

$out | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv
Write-Json @($usage.Values) $outJson

$lines = @()
$lines += "ASTRODDS 274 ROLLING BULLPEN 3D/7D"
$lines += ""
$lines += "Games written: $($out.Count)"
$lines += "Teams tracked: $($teams.Count)"
$lines += ""
foreach ($r in ($out | Select-Object -First 12)) {
    $lines += "- $($r.Game) | away3d=$($r.AwayBullpenFatigue3d) away7d=$($r.AwayBullpenFatigue7d) | home3d=$($r.HomeBullpenFatigue3d) home7d=$($r.HomeBullpenFatigue7d)"
}
$lines += ""
$lines += "Output: $outCsv"

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
exit 0
