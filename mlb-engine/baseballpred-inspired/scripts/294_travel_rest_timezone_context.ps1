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

function Clamp($x, $lo, $hi) {
    if ($x -lt $lo) { return $lo }
    if ($x -gt $hi) { return $hi }
    return $x
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

function Avg($arr) {
    $vals = @()
    foreach ($x in @($arr)) {
        $n = Num $x
        if ($null -ne $n) {
            if ($n -gt 1) { $n = $n / 100.0 }
            if ($n -gt 0 -and $n -lt 1) { $vals += $n }
        }
    }
    if ($vals.Count -eq 0) { return $null }
    return (($vals | Measure-Object -Average).Average)
}

function Load-EnvLocal($root) {
    $envFile = Join-Path $root ".env.local"
    if (Test-Path $envFile) {
        Get-Content $envFile | ForEach-Object {
            if ($_ -match "^\s*([^#][A-Za-z0-9_]+)\s*=\s*(.+)\s*$") {
                $name = $matches[1].Trim()
                $value = $matches[2].Trim().Trim('"').Trim("'")
                [Environment]::SetEnvironmentVariable($name, $value, "Process")
            }
        }
    }
    if ($env:THE_ODDS_API_KEY -and -not $env:ODDS_API_KEY) { $env:ODDS_API_KEY = $env:THE_ODDS_API_KEY }
    if ($env:ASTRODDS_ODDS_API_KEY -and -not $env:ODDS_API_KEY) { $env:ODDS_API_KEY = $env:ASTRODDS_ODDS_API_KEY }
}

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$scheduleCsv = Join-Path $astro "ASTRODDS-source-mlb-schedule-latest.csv"
$outCsv = Join-Path $astro "ASTRODDS-travel-rest-timezone-context-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-294-travel-rest-timezone-context-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-294-travel-rest-timezone-context-latest.json"

Write-Host ""
Write-Host "ASTRODDS 294 TRAVEL / REST / TIMEZONE CONTEXT" -ForegroundColor Cyan
Write-Host "Free proxy using recent schedule dates." -ForegroundColor Cyan
Write-Host ""

$schedule = Safe-Csv $scheduleCsv
$today = Get-Date
$teamStats = @{}

foreach ($g in $schedule) {
    foreach ($team in @((Get-Val $g @("AwayTeam")), (Get-Val $g @("HomeTeam")))) {
        if ($team -ne "" -and -not $teamStats.ContainsKey($team)) {
            $teamStats[$team] = [pscustomobject]@{ Team=$team; GamesLast3=0; GamesLast7=0; PlayedYesterday="NO"; TravelStress="unknown" }
        }
    }
}

for ($i=1; $i -le 7; $i++) {
    $date = $today.AddDays(-$i).ToString("yyyy-MM-dd")
    $url = "https://statsapi.mlb.com/api/v1/schedule?sportId=1&date=$date"
    try { $resp = Invoke-RestMethod -Uri $url -TimeoutSec 20 } catch { $resp = $null }
    if ($null -eq $resp) { continue }

    foreach ($d in @($resp.dates)) {
        foreach ($gameObj in @($d.games)) {
            $awayTeamName = "$($gameObj.teams.away.team.name)"
            $homeTeamName = "$($gameObj.teams.home.team.name)"
            foreach ($team in @($awayTeamName,$homeTeamName)) {
                if ($teamStats.ContainsKey($team)) {
                    $teamStats[$team].GamesLast7 += 1
                    if ($i -le 3) { $teamStats[$team].GamesLast3 += 1 }
                    if ($i -eq 1) { $teamStats[$team].PlayedYesterday = "YES" }
                }
            }
        }
    }
}

foreach ($k in @($teamStats.Keys)) {
    $t = $teamStats[$k]
    if ($t.GamesLast7 -ge 7 -and $t.PlayedYesterday -eq "YES") { $t.TravelStress = "high_schedule_density" }
    elseif ($t.GamesLast3 -ge 3) { $t.TravelStress = "medium_schedule_density" }
    else { $t.TravelStress = "low_or_normal" }
}

$out = @()
foreach ($g in $schedule) {
    $away = Get-Val $g @("AwayTeam")
    $homeTeamName = Get-Val $g @("HomeTeam")
    $a = $teamStats[$away]
    $h = $teamStats[$homeTeamName]

    $out += ,[pscustomobject]@{
        Source = "MLB_SCHEDULE_TRAVEL_REST_PROXY"
        Game = Get-Val $g @("Game")
        GamePk = Get-Val $g @("GamePk")
        AwayTeam = $away
        HomeTeam = $homeTeamName
        AwayGamesLast3 = $a.GamesLast3
        AwayGamesLast7 = $a.GamesLast7
        AwayPlayedYesterday = $a.PlayedYesterday
        AwayTravelStress = $a.TravelStress
        HomeGamesLast3 = $h.GamesLast3
        HomeGamesLast7 = $h.GamesLast7
        HomePlayedYesterday = $h.PlayedYesterday
        HomeTravelStress = $h.TravelStress
        Note = "Proxy; not full distance/time-zone calculation yet."
    }
}

$out | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv
$out | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

$lines = @()
$lines += "ASTRODDS 294 TRAVEL / REST / TIMEZONE CONTEXT"
$lines += ""
$lines += "Rows: $($out.Count)"
foreach ($r in $out) {
    $lines += "- $($r.Game) | awayStress=$($r.AwayTravelStress) | homeStress=$($r.HomeTravelStress) | awayLast7=$($r.AwayGamesLast7) homeLast7=$($r.HomeGamesLast7)"
}
($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
