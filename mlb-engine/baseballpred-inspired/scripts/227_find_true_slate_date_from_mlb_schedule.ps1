$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$fullSlate = Join-Path $astro "ASTRODDS-full-slate-context-final-latest.csv"

$outTxt  = Join-Path $astro "ASTRODDS-true-slate-date-match-audit-latest.txt"
$outCsv  = Join-Path $astro "ASTRODDS-true-slate-date-match-audit-latest.csv"
$outJson = Join-Path $astro "ASTRODDS-true-slate-date-match-audit-latest.json"

Write-Host ""
Write-Host "ASTRODDS 227 TRUE SLATE DATE MATCH AUDIT" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - FIND WHY MLB SCHEDULE DID NOT MATCH" -ForegroundColor Cyan
Write-Host ""

function Normalize-Team($s) {
    $x = "$s".ToLower().Trim()
    $x = $x -replace "[^a-z0-9 ]", ""
    $x = $x -replace "\s+", " "
    return $x
}

function Split-Game($game) {
    $awayTeam = ""
    $homeTeam = ""

    if ($game -match "\s@\s") {
        $parts = $game -split "\s@\s", 2
        $awayTeam = "$($parts[0])".Trim()
        $homeTeam = "$($parts[1])".Trim()
    } elseif ($game -match "\svs\s") {
        $parts = $game -split "\svs\s", 2
        $awayTeam = "$($parts[0])".Trim()
        $homeTeam = "$($parts[1])".Trim()
    }

    return [pscustomobject]@{
        Away = $awayTeam
        Home = $homeTeam
        AwayNorm = Normalize-Team $awayTeam
        HomeNorm = Normalize-Team $homeTeam
        Key = (Normalize-Team $awayTeam) + " @ " + (Normalize-Team $homeTeam)
    }
}

function Get-MlbSchedule($date) {
    $url = "https://statsapi.mlb.com/api/v1/schedule?sportId=1&date=$date&hydrate=probablePitcher"
    try {
        return Invoke-RestMethod -Uri $url -Method Get -TimeoutSec 15
    } catch {
        return $null
    }
}

if (!(Test-Path $fullSlate)) {
    Write-Host "ERROR: Missing full slate file:" -ForegroundColor Red
    Write-Host $fullSlate
    exit 0
}

$slateRows = @(Import-Csv $fullSlate)

$slateGames = @()
$seen = @{}

foreach ($r in $slateRows) {
    $game = "$($r.game)".Trim()
    if ($game -eq "") { continue }

    if (!$seen.ContainsKey($game)) {
        $seen[$game] = $true
        $s = Split-Game $game

        $slateGames += ,[pscustomobject]@{
            Game = $game
            Away = $s.Away
            Home = $s.Home
            AwayNorm = $s.AwayNorm
            HomeNorm = $s.HomeNorm
            Key = $s.Key
        }
    }
}

# Search +/- 10 days around current date because the slate may be stale or generated for another day.
$center = Get-Date
$dateCandidates = @()

for ($i = -10; $i -le 10; $i++) {
    $dateCandidates += $center.AddDays($i).ToString("yyyy-MM-dd")
}

$matchRows = @()
$dateSummary = @()

foreach ($date in $dateCandidates) {
    Write-Host "Checking MLB schedule date: $date" -ForegroundColor DarkGray

    $sched = Get-MlbSchedule $date
    $scheduleGames = @()

    if ($null -ne $sched -and $sched.dates) {
        foreach ($d in @($sched.dates)) {
            foreach ($g in @($d.games)) {
                $away = "$($g.teams.away.team.name)"
                $homeTeamName = "$($g.teams.home.team.name)"
                $scheduleGames += ,[pscustomobject]@{
                    Date = $date
                    GamePk = "$($g.gamePk)"
                    Away = $away
                    Home = $homeTeamName
                    AwayNorm = Normalize-Team $away
                    HomeNorm = Normalize-Team $homeTeamName
                    Key = (Normalize-Team $away) + " @ " + (Normalize-Team $homeTeamName)
                    Status = "$($g.status.detailedState)"
                    GameDate = "$($g.gameDate)"
                }
            }
        }
    }

    $matchedCount = 0

    foreach ($sg in $slateGames) {
        $match = $scheduleGames | Where-Object {
            $_.AwayNorm -eq $sg.AwayNorm -and $_.HomeNorm -eq $sg.HomeNorm
        } | Select-Object -First 1

        if ($null -ne $match) {
            $matchedCount++

            $matchRows += ,[pscustomobject]@{
                Date = $date
                SlateGame = $sg.Game
                ScheduleGame = "$($match.Away) @ $($match.Home)"
                GamePk = $match.GamePk
                Status = $match.Status
                GameDate = $match.GameDate
                MatchType = "EXACT_AWAY_HOME"
            }
        }
    }

    $dateSummary += ,[pscustomobject]@{
        Date = $date
        ScheduleGames = $scheduleGames.Count
        SlateGames = $slateGames.Count
        MatchedGames = $matchedCount
    }
}

$bestDate = $dateSummary | Sort-Object MatchedGames -Descending | Select-Object -First 1

$lines = @()
$lines += "ASTRODDS 227 TRUE SLATE DATE MATCH AUDIT"
$lines += ""
$lines += "Slate games found: $($slateGames.Count)"
$lines += "Dates checked: $($dateCandidates.Count)"
$lines += ""
$lines += "BEST DATE"
$lines += "Date: $($bestDate.Date)"
$lines += "Schedule games: $($bestDate.ScheduleGames)"
$lines += "Matched slate games: $($bestDate.MatchedGames) / $($bestDate.SlateGames)"
$lines += ""

$lines += "SLATE GAMES"
foreach ($g in $slateGames) {
    $lines += "- $($g.Game)"
}
$lines += ""

$lines += "DATE SUMMARY"
foreach ($d in ($dateSummary | Sort-Object @{Expression="MatchedGames";Descending=$true}, @{Expression="Date";Ascending=$true} | Select-Object -First 21)) {
    $lines += "- $($d.Date) | MLB games=$($d.ScheduleGames) | matched=$($d.MatchedGames)/$($d.SlateGames)"
}
$lines += ""

$lines += "MATCHES FOUND"
if ($matchRows.Count -eq 0) {
    $lines += "- No exact away/home matches found in +/- 10 days."
} else {
    foreach ($m in ($matchRows | Sort-Object Date, SlateGame)) {
        $lines += "- $($m.Date) | $($m.SlateGame) => gamePk=$($m.GamePk) | status=$($m.Status)"
    }
}
$lines += ""

$lines += "INTERPRETATION"
if ([int]$bestDate.MatchedGames -eq 0) {
    $lines += "- MLB schedule API worked, but none of the current slate games matched the schedule in the search window."
    $lines += "- This may mean team names, stale files, or generated slate source are wrong."
} elseif ([int]$bestDate.MatchedGames -lt $slateGames.Count) {
    $lines += "- Some games matched, but not all. Use the best date for lineup patch and inspect missing games."
} else {
    $lines += "- All slate games matched one MLB schedule date. Use this date in the live lineup connector."
}

$dateSummary | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    slateGames = $slateGames.Count
    bestDate = "$($bestDate.Date)"
    bestDateMatchedGames = [int]$bestDate.MatchedGames
    bestDateScheduleGames = [int]$bestDate.ScheduleGames
    matchRows = @($matchRows)
    recommendation = if ([int]$bestDate.MatchedGames -gt 0) { "Use bestDate in script 226." } else { "Inspect stale slate/team-name source before lineup connector." }
} | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output CSV: $outCsv"
Write-Host "Output JSON: $outJson"
Write-Host ""


