$ErrorActionPreference = "Continue"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$outScheduleCsv = Join-Path $astro "ASTRODDS-source-mlb-schedule-latest.csv"
$outScheduleJson = Join-Path $astro "ASTRODDS-source-mlb-schedule-latest.json"
$outLineupsCsv = Join-Path $astro "ASTRODDS-source-live-lineups-latest.csv"
$outPitcherCsv = Join-Path $astro "ASTRODDS-lineup-pitcher-live-context-latest.csv"
$outBullpenCsv = Join-Path $astro "ASTRODDS-bpen-game-relief-stats-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-259-fetch-mlb-live-sources-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 259 FETCH MLB LIVE SOURCES FIXED" -ForegroundColor Cyan
Write-Host "Fixed reserved `$HOME bug: using homeTeamName variable." -ForegroundColor Cyan
Write-Host ""


function Ensure-Dir($path) {
    if (!(Test-Path $path)) { New-Item -ItemType Directory -Force -Path $path | Out-Null }
}

function Invoke-Json($url, $timeout = 20) {
    try { return Invoke-RestMethod -Uri $url -Method Get -TimeoutSec $timeout }
    catch { return $null }
}

function Write-Json($obj, $path) {
    $obj | ConvertTo-Json -Depth 20 | Set-Content -Encoding UTF8 $path
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

$date = Get-Date -Format "yyyy-MM-dd"
$scheduleUrl = "https://statsapi.mlb.com/api/v1/schedule?sportId=1&date=$date&hydrate=probablePitcher(note),linescore"
$schedule = Invoke-Json $scheduleUrl 25

$scheduleRows = @()
$lineupRows = @()
$pitcherRows = @()
$bullpenRows = @()

if ($null -ne $schedule -and $schedule.dates) {
    foreach ($d in @($schedule.dates)) {
        foreach ($g in @($d.games)) {
            $gamePk = "$($g.gamePk)"
            $awayTeamName = "$($g.teams.away.team.name)"
            $homeTeamName = "$($g.teams.home.team.name)"
            $game = "$awayTeamName @ $homeTeamName"
            $status = "$($g.status.detailedState)"
            $venue = "$($g.venue.name)"
            $gameDate = "$($g.gameDate)"

            $awayProb = ""
            $homeProb = ""
            try { $awayProb = "$($g.teams.away.probablePitcher.fullName)" } catch {}
            try { $homeProb = "$($g.teams.home.probablePitcher.fullName)" } catch {}

            $awayScore = ""
            $homeScore = ""
            try { $awayScore = "$($g.teams.away.score)" } catch {}
            try { $homeScore = "$($g.teams.home.score)" } catch {}

            $scheduleRows += ,[pscustomobject]@{
                Source = "MLB_STATSAPI_SCHEDULE"
                ScheduleDate = $date
                GamePk = $gamePk
                Game = $game
                AwayTeam = $awayTeamName
                HomeTeam = $homeTeamName
                MlbStatus = $status
                GameDateUtc = $gameDate
                Venue = $venue
                AwayProbablePitcher = $awayProb
                HomeProbablePitcher = $homeProb
                AwayScore = $awayScore
                HomeScore = $homeScore
                SourceUrl = $scheduleUrl
                FetchedAt = (Get-Date).ToString("o")
            }

            $feedUrl = "https://statsapi.mlb.com/api/v1.1/game/$gamePk/feed/live"
            $feed = Invoke-Json $feedUrl 20

            $awayCount = 0
            $homeCount = 0
            $awayNames = @()
            $homeNames = @()
            $awayStarting = @()
            $homeStarting = @()

            if ($null -ne $feed) {
                try {
                    $awayBatters = @($feed.liveData.boxscore.teams.away.batters)
                    $homeBatters = @($feed.liveData.boxscore.teams.home.batters)

                    foreach ($pid in $awayBatters) {
                        $pkey = "ID$pid"
                        $p = $feed.liveData.boxscore.teams.away.players.$pkey
                        $name = "$($p.person.fullName)"
                        $bo = "$($p.battingOrder)"
                        if ($name -ne "") { $awayNames += $name }
                        if ($bo -in @("100","200","300","400","500","600","700","800","900")) { $awayStarting += $name }
                    }

                    foreach ($pid in $homeBatters) {
                        $pkey = "ID$pid"
                        $p = $feed.liveData.boxscore.teams.home.players.$pkey
                        $name = "$($p.person.fullName)"
                        $bo = "$($p.battingOrder)"
                        if ($name -ne "") { $homeNames += $name }
                        if ($bo -in @("100","200","300","400","500","600","700","800","900")) { $homeStarting += $name }
                    }

                    $awayCount = $awayStarting.Count
                    $homeCount = $homeStarting.Count
                    if ($awayCount -eq 0) { $awayCount = $awayNames.Count }
                    if ($homeCount -eq 0) { $homeCount = $homeNames.Count }
                } catch {}
            }

            $awayLineupStatus = if ($awayCount -ge 9) { "confirmed" } else { "missing" }
            $homeLineupStatus = if ($homeCount -ge 9) { "confirmed" } else { "missing" }

            $lineupRows += ,[pscustomobject]@{
                Source = "MLB_STATSAPI_GAME_FEED_LIVE"
                ScheduleDate = $date
                GamePk = $gamePk
                Game = $game
                AwayTeam = $awayTeamName
                HomeTeam = $homeTeamName
                MlbStatus = $status
                AwayLineupStatus = $awayLineupStatus
                HomeLineupStatus = $homeLineupStatus
                AwayLineupCount = $awayCount
                HomeLineupCount = $homeCount
                AwayLineupNames = ($awayNames -join "; ")
                HomeLineupNames = ($homeNames -join "; ")
                SourceUrl = $feedUrl
                FetchedAt = (Get-Date).ToString("o")
            }

            $pitcherRows += ,[pscustomobject]@{
                Source = "MLB_STATSAPI_SCHEDULE_PROBABLE_PITCHER"
                ScheduleDate = $date
                GamePk = $gamePk
                Game = $game
                AwayTeam = $awayTeamName
                HomeTeam = $homeTeamName
                AwayProbablePitcher = $awayProb
                HomeProbablePitcher = $homeProb
                PitcherContextConnected = if ($awayProb -ne "" -or $homeProb -ne "") { "YES" } else { "NO" }
                SourceUrl = $scheduleUrl
                FetchedAt = (Get-Date).ToString("o")
            }

            $awayPitchersUsed = 0
            $homePitchersUsed = 0
            try { $awayPitchersUsed = @($feed.liveData.boxscore.teams.away.pitchers).Count } catch {}
            try { $homePitchersUsed = @($feed.liveData.boxscore.teams.home.pitchers).Count } catch {}

            $bullpenRows += ,[pscustomobject]@{
                Source = "MLB_STATSAPI_BOX_SCORE_PITCHERS_USED_PROXY"
                ScheduleDate = $date
                GamePk = $gamePk
                Game = $game
                AwayTeam = $awayTeamName
                HomeTeam = $homeTeamName
                AwayPitchersUsedToday = $awayPitchersUsed
                HomePitchersUsedToday = $homePitchersUsed
                AwayBullpenFatigueProxy = if ($awayPitchersUsed -ge 5) { "high" } elseif ($awayPitchersUsed -ge 3) { "medium" } else { "low_or_pregame" }
                HomeBullpenFatigueProxy = if ($homePitchersUsed -ge 5) { "high" } elseif ($homePitchersUsed -ge 3) { "medium" } else { "low_or_pregame" }
                SourceUrl = $feedUrl
                FetchedAt = (Get-Date).ToString("o")
            }
        }
    }
}

$scheduleRows | Export-Csv -NoTypeInformation -Encoding UTF8 $outScheduleCsv
$lineupRows | Export-Csv -NoTypeInformation -Encoding UTF8 $outLineupsCsv
$pitcherRows | Export-Csv -NoTypeInformation -Encoding UTF8 $outPitcherCsv
$bullpenRows | Export-Csv -NoTypeInformation -Encoding UTF8 $outBullpenCsv
Write-Json $schedule $outScheduleJson

$lineupRows | Export-Csv -NoTypeInformation -Encoding UTF8 (Join-Path $astro "ASTRODDS-smart-live-lineup-status-latest.csv")

$lines = @()
$lines += "ASTRODDS 259 FETCH MLB LIVE SOURCES FIXED"
$lines += ""
$lines += "Date: $date"
$lines += "Schedule games fetched: $($scheduleRows.Count)"
$lines += "Lineup rows fetched: $($lineupRows.Count)"
$lines += "Pitcher rows fetched: $($pitcherRows.Count)"
$lines += "Bullpen proxy rows fetched: $($bullpenRows.Count)"
$lines += ""
$lines += "Sample games:"
foreach ($s in ($scheduleRows | Select-Object -First 5)) {
    $lines += "- $($s.Game)"
}

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
