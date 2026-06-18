$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
$scripts = Join-Path $root "mlb-engine\baseballpred-inspired\scripts"

$fullSlate = Join-Path $astro "ASTRODDS-full-slate-context-final-latest.csv"
$smartLineupCsv = Join-Path $astro "ASTRODDS-smart-live-lineup-status-latest.csv"
$runner230 = Join-Path $scripts "230_run_astrodds_smart_official_daily.ps1"

$outTxt  = Join-Path $astro "ASTRODDS-full-slate-lineup-completeness-gate-latest.txt"
$outCsv  = Join-Path $astro "ASTRODDS-full-slate-lineup-completeness-gate-latest.csv"
$outJson = Join-Path $astro "ASTRODDS-full-slate-lineup-completeness-gate-latest.json"

Write-Host ""
Write-Host "ASTRODDS 232 FULL SLATE + LINEUP COMPLETENESS GATE" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - VERIFY ALL GAMES BEFORE BEST BETS" -ForegroundColor Cyan
Write-Host ""

function Normalize-Team($s) {
    $x = "$s".ToLower().Trim()
    $x = $x -replace "[^a-z0-9 ]", ""
    $x = $x -replace "\s+", " "
    return $x
}

function Split-Game($game) {
    $awayTeamName = ""
    $homeTeamName = ""

    if ($game -match "\s@\s") {
        $parts = $game -split "\s@\s", 2
        $awayTeamName = "$($parts[0])".Trim()
        $homeTeamName = "$($parts[1])".Trim()
    } elseif ($game -match "\svs\s") {
        $parts = $game -split "\svs\s", 2
        $awayTeamName = "$($parts[0])".Trim()
        $homeTeamName = "$($parts[1])".Trim()
    }

    return [pscustomobject]@{
        Away = $awayTeamName
        Home = $homeTeamName
        Key = (Normalize-Team $awayTeamName) + " @ " + (Normalize-Team $homeTeamName)
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

function Get-MlbBoxscore($gamePk) {
    $url = "https://statsapi.mlb.com/api/v1/game/$gamePk/boxscore"
    try {
        return Invoke-RestMethod -Uri $url -Method Get -TimeoutSec 15
    } catch {
        return $null
    }
}

function Count-Safe($v) {
    if ($null -eq $v) { return 0 }
    return @($v).Count
}

if (!(Test-Path $fullSlate)) {
    Write-Host "ERROR: Full slate file missing:" -ForegroundColor Red
    Write-Host $fullSlate
    exit 0
}

# Use today. If you need another date, change this line.
$date = Get-Date -Format "yyyy-MM-dd"

$schedule = Get-MlbSchedule $date
$scheduleRows = @()

if ($null -ne $schedule -and $schedule.dates) {
    foreach ($d in @($schedule.dates)) {
        foreach ($g in @($d.games)) {
            $awayTeamName = "$($g.teams.away.team.name)"
            $homeTeamName = "$($g.teams.home.team.name)"
            $key = (Normalize-Team $awayTeamName) + " @ " + (Normalize-Team $homeTeamName)

            $scheduleRows += ,[pscustomobject]@{
                Source = "MLB_SCHEDULE"
                Date = $date
                GamePk = "$($g.gamePk)"
                Game = "$awayTeamName @ $homeTeamName"
                Key = $key
                Status = "$($g.status.detailedState)"
                AwayLineupStatus = "missing"
                HomeLineupStatus = "missing"
                AwayOrderCount = 0
                HomeOrderCount = 0
                InCurrentSlate = "NO"
                CompletenessIssue = ""
            }
        }
    }
}

$slateRows = @(Import-Csv $fullSlate)
$slateKeys = @{}

foreach ($r in $slateRows) {
    $game = "$($r.game)".Trim()
    if ($game -eq "") { continue }

    $split = Split-Game $game
    if ($split.Key -ne " @ ") {
        $slateKeys[$split.Key] = $true
    }
}

$checkedRows = @()

foreach ($s in $scheduleRows) {
    $inSlate = "NO"
    if ($slateKeys.ContainsKey($s.Key)) {
        $inSlate = "YES"
    }

    $awayLineup = "missing"
    $homeLineup = "missing"
    $awayOrder = 0
    $homeOrder = 0

    $box = Get-MlbBoxscore $s.GamePk

    if ($null -ne $box) {
        $awayOrder = Count-Safe $box.teams.away.battingOrder
        $homeOrder = Count-Safe $box.teams.home.battingOrder

        $awayBatters = Count-Safe $box.teams.away.batters
        $homeBatters = Count-Safe $box.teams.home.batters

        if ($awayOrder -ge 9 -or $awayBatters -ge 9) {
            $awayLineup = "confirmed"
        }

        if ($homeOrder -ge 9 -or $homeBatters -ge 9) {
            $homeLineup = "confirmed"
        }
    }

    $issue = @()

    if ($inSlate -ne "YES") {
        $issue += "missing_from_astrodds_slate"
    }

    if ($awayLineup -ne "confirmed" -or $homeLineup -ne "confirmed") {
        $issue += "lineup_not_confirmed"
    }

    $checkedRows += ,[pscustomobject]@{
        Date = $date
        GamePk = $s.GamePk
        Game = $s.Game
        Status = $s.Status
        InCurrentSlate = $inSlate
        AwayLineupStatus = $awayLineup
        HomeLineupStatus = $homeLineup
        AwayOrderCount = $awayOrder
        HomeOrderCount = $homeOrder
        CompletenessIssue = ($issue -join " | ")
    }
}

$totalGames = $checkedRows.Count
$gamesInSlate = @($checkedRows | Where-Object { $_.InCurrentSlate -eq "YES" }).Count
$missingFromSlate = @($checkedRows | Where-Object { $_.InCurrentSlate -ne "YES" }).Count
$confirmedLineups = @($checkedRows | Where-Object { $_.AwayLineupStatus -eq "confirmed" -and $_.HomeLineupStatus -eq "confirmed" }).Count
$missingLineups = @($checkedRows | Where-Object { $_.AwayLineupStatus -ne "confirmed" -or $_.HomeLineupStatus -ne "confirmed" }).Count

$decision = "READY_FOR_FULL_SLATE_BEST_BETS"

if ($missingFromSlate -gt 0) {
    $decision = "BLOCKED_SLATE_INCOMPLETE"
} elseif ($missingLineups -gt 0) {
    $decision = "WAIT_FOR_LINEUPS"
}

$lines = @()
$lines += "ASTRODDS 232 FULL SLATE + LINEUP COMPLETENESS GATE"
$lines += ""
$lines += "Date: $date"
$lines += "MLB schedule games: $totalGames"
$lines += "Games present in ASTRODDS slate: $gamesInSlate"
$lines += "Games missing from ASTRODDS slate: $missingFromSlate"
$lines += "Games with confirmed lineups: $confirmedLineups"
$lines += "Games still missing lineups: $missingLineups"
$lines += ""
$lines += "DECISION: $decision"
$lines += ""

$lines += "GAMES CHECKED"
foreach ($r in $checkedRows) {
    $lines += "- $($r.Game) | status=$($r.Status) | inSlate=$($r.InCurrentSlate) | lineups=$($r.AwayLineupStatus)/$($r.HomeLineupStatus)"
    if ($r.CompletenessIssue -ne "") {
        $lines += "  Issue: $($r.CompletenessIssue)"
    }
}
$lines += ""

if ($decision -eq "READY_FOR_FULL_SLATE_BEST_BETS") {
    $lines += "ACTION"
    $lines += "Full slate is complete and lineups are confirmed. Running 230 smart official daily runner."

    if (Test-Path $runner230) {
        powershell -ExecutionPolicy Bypass -File $runner230
    } else {
        $lines += "Runner 230 missing: $runner230"
    }
} elseif ($decision -eq "BLOCKED_SLATE_INCOMPLETE") {
    $lines += "ACTION"
    $lines += "Do not call this full-slate best bets yet. The ASTRODDS slate is missing games from the MLB schedule."
    $lines += "Next fix: repair the slate generator so it includes every MLB game for the date."
} else {
    $lines += "ACTION"
    $lines += "Wait for all lineups to be confirmed, then run this script again."
    $lines += "You can still use selective official mode for games already confirmed, but full-slate best bets should wait."
}

$checkedRows | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    date = $date
    decision = $decision
    mlbScheduleGames = $totalGames
    gamesInAstroddsSlate = $gamesInSlate
    gamesMissingFromAstroddsSlate = $missingFromSlate
    confirmedLineupGames = $confirmedLineups
    missingLineupGames = $missingLineups
    outputCsv = $outCsv
} | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output CSV: $outCsv"
Write-Host "Output JSON: $outJson"
Write-Host ""
