$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$currentSlate = Join-Path $astro "ASTRODDS-full-slate-context-final-latest.csv"
$smartGateCsv = Join-Path $astro "ASTRODDS-smart-live-client-gate-latest.csv"

$outMasterCsv = Join-Path $astro "ASTRODDS-mlb-schedule-lineup-master-latest.csv"
$outMergedCsv = Join-Path $astro "ASTRODDS-complete-mlb-slate-merged-latest.csv"
$outTxt       = Join-Path $astro "ASTRODDS-complete-mlb-slate-merged-latest.txt"
$outJson      = Join-Path $astro "ASTRODDS-complete-mlb-slate-merged-latest.json"

Write-Host ""
Write-Host "ASTRODDS 233 COMPLETE MLB SLATE + LIVE LINEUPS" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - BUILD ALL 15 GAMES MASTER SLATE" -ForegroundColor Cyan
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

function Safe-Csv($path) {
    if (!(Test-Path $path)) { return @() }
    try { return @(Import-Csv $path) }
    catch { return @() }
}

function Get-Val($row, $names) {
    if ($null -eq $row) { return "" }

    foreach ($n in @($names)) {
        $p = $row.PSObject.Properties[$n]
        if ($null -ne $p -and $null -ne $p.Value -and "$($p.Value)".Trim() -ne "") {
            return "$($p.Value)".Trim()
        }
    }

    return ""
}

function Get-MlbSchedule($date) {
    $url = "https://statsapi.mlb.com/api/v1/schedule?sportId=1&date=$date&hydrate=probablePitcher"
    try {
        return Invoke-RestMethod -Uri $url -Method Get -TimeoutSec 15
    } catch {
        Write-Host "ERROR: Cannot fetch MLB schedule for $date" -ForegroundColor Red
        Write-Host $_.Exception.Message
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

$date = Get-Date -Format "yyyy-MM-dd"

$schedule = Get-MlbSchedule $date
$scheduleRows = @()

if ($null -ne $schedule -and $schedule.dates) {
    foreach ($d in @($schedule.dates)) {
        foreach ($g in @($d.games)) {
            $awayTeamName = "$($g.teams.away.team.name)"
            $homeTeamName = "$($g.teams.home.team.name)"
            $gamePk = "$($g.gamePk)"
            $status = "$($g.status.detailedState)"
            $gameDate = "$($g.gameDate)"
            $key = (Normalize-Team $awayTeamName) + " @ " + (Normalize-Team $homeTeamName)

            $awayLineupStatus = "missing"
            $homeLineupStatus = "missing"
            $awayOrderCount = 0
            $homeOrderCount = 0

            $box = Get-MlbBoxscore $gamePk

            if ($null -ne $box) {
                $awayOrderCount = Count-Safe $box.teams.away.battingOrder
                $homeOrderCount = Count-Safe $box.teams.home.battingOrder

                $awayBattersCount = Count-Safe $box.teams.away.batters
                $homeBattersCount = Count-Safe $box.teams.home.batters

                if ($awayOrderCount -ge 9 -or $awayBattersCount -ge 9) {
                    $awayLineupStatus = "confirmed"
                }

                if ($homeOrderCount -ge 9 -or $homeBattersCount -ge 9) {
                    $homeLineupStatus = "confirmed"
                }
            }

            $scheduleRows += ,[pscustomobject]@{
                Date = $date
                GamePk = $gamePk
                Game = "$awayTeamName @ $homeTeamName"
                AwayTeam = $awayTeamName
                HomeTeam = $homeTeamName
                Key = $key
                MlbStatus = $status
                GameDate = $gameDate
                AwayLineupStatus = $awayLineupStatus
                HomeLineupStatus = $homeLineupStatus
                AwayOrderCount = $awayOrderCount
                HomeOrderCount = $homeOrderCount
            }
        }
    }
}

$currentRows = Safe-Csv $currentSlate
$smartGateRows = Safe-Csv $smartGateCsv

$currentByKey = @{}

foreach ($r in $currentRows) {
    $game = Get-Val $r @("game", "Game")
    if ($game -eq "") { continue }

    $split = Split-Game $game
    if ($split.Key -ne " @ ") {
        $currentByKey[$split.Key] = $r
    }
}

$smartByKey = @{}

foreach ($r in $smartGateRows) {
    $game = Get-Val $r @("Game", "game")
    if ($game -eq "") { continue }

    $split = Split-Game $game
    if ($split.Key -ne " @ ") {
        $smartByKey[$split.Key] = $r
    }
}

$mergedRows = @()

foreach ($s in $scheduleRows) {
    $key = "$($s.Key)"
    $current = $null
    $smart = $null

    if ($currentByKey.ContainsKey($key)) {
        $current = $currentByKey[$key]
    }

    if ($smartByKey.ContainsKey($key)) {
        $smart = $smartByKey[$key]
    }

    $inAstroddsSlate = if ($null -ne $current) { "YES" } else { "NO" }
    $hasSmartGate = if ($null -ne $smart) { "YES" } else { "NO" }

    $pick = ""
    $modelProbability = ""
    $marketProbability = ""
    $edgePct = ""
    $decision = "NO_ASTRODDS_MODEL_YET"
    $hardBlocks = ""
    $warnings = ""

    if ($null -ne $current) {
        $pick = Get-Val $current @("pick", "Pick")
        $modelProbability = Get-Val $current @("modelProbability", "ModelProbability")
        $marketProbability = Get-Val $current @("marketProbability", "MarketProbability")
        $edgePct = Get-Val $current @("edgePct", "EdgePct", "edge")
    }

    if ($null -ne $smart) {
        $decision = Get-Val $smart @("Decision")
        $hardBlocks = Get-Val $smart @("HardBlocks")
        $warnings = Get-Val $smart @("Warnings")
        if ($pick -eq "") { $pick = Get-Val $smart @("Pick") }
    } elseif ($null -ne $current) {
        $decision = "ASTRODDS_CONTEXT_ONLY_NEEDS_GATE"
    }

    $missingReason = @()

    if ($inAstroddsSlate -eq "NO") {
        $missingReason += "missing_from_current_astrodds_slate"
    }

    if ($s.AwayLineupStatus -ne "confirmed" -or $s.HomeLineupStatus -ne "confirmed") {
        $missingReason += "lineup_not_confirmed"
    }

    if ($hasSmartGate -eq "NO") {
        $missingReason += "not_scored_by_smart_gate"
    }

    $mergedRows += ,[pscustomobject]@{
        Date = $s.Date
        GamePk = $s.GamePk
        Game = $s.Game
        AwayTeam = $s.AwayTeam
        HomeTeam = $s.HomeTeam
        MlbStatus = $s.MlbStatus
        InAstroddsSlate = $inAstroddsSlate
        HasSmartGate = $hasSmartGate
        Pick = $pick
        ModelProbability = $modelProbability
        MarketProbability = $marketProbability
        EdgePct = $edgePct
        AwayLineupStatus = $s.AwayLineupStatus
        HomeLineupStatus = $s.HomeLineupStatus
        AwayOrderCount = $s.AwayOrderCount
        HomeOrderCount = $s.HomeOrderCount
        Decision = $decision
        HardBlocks = $hardBlocks
        Warnings = $warnings
        MissingReason = ($missingReason -join " | ")
    }
}

$scheduleRows | Export-Csv -NoTypeInformation -Encoding UTF8 $outMasterCsv
$mergedRows | Export-Csv -NoTypeInformation -Encoding UTF8 $outMergedCsv

$total = $mergedRows.Count
$inSlate = @($mergedRows | Where-Object { $_.InAstroddsSlate -eq "YES" }).Count
$missing = @($mergedRows | Where-Object { $_.InAstroddsSlate -ne "YES" }).Count
$confirmed = @($mergedRows | Where-Object { $_.AwayLineupStatus -eq "confirmed" -and $_.HomeLineupStatus -eq "confirmed" }).Count
$notConfirmed = @($mergedRows | Where-Object { $_.AwayLineupStatus -ne "confirmed" -or $_.HomeLineupStatus -ne "confirmed" }).Count
$sendOk = @($mergedRows | Where-Object { $_.Decision -eq "CLIENT_OFFICIAL_SEND_OK" }).Count

$decision = "READY_FOR_SELECTIVE_OFFICIAL_ONLY"

if ($missing -gt 0) {
    $decision = "FULL_SLATE_MODEL_INCOMPLETE"
}

if ($missing -eq 0 -and $notConfirmed -gt 0) {
    $decision = "FULL_SLATE_WAIT_FOR_LINEUPS"
}

if ($missing -eq 0 -and $notConfirmed -eq 0) {
    $decision = "FULL_SLATE_READY"
}

$lines = @()
$lines += "ASTRODDS 233 COMPLETE MLB SLATE + LIVE LINEUPS"
$lines += ""
$lines += "Date: $date"
$lines += "MLB schedule games: $total"
$lines += "Games in current ASTRODDS slate: $inSlate"
$lines += "Games missing from ASTRODDS slate: $missing"
$lines += "Games with confirmed lineups: $confirmed"
$lines += "Games still missing lineups: $notConfirmed"
$lines += "SEND_OK picks available: $sendOk"
$lines += ""
$lines += "DECISION: $decision"
$lines += ""

$lines += "FULL MLB SLATE MASTER"
foreach ($r in $mergedRows) {
    $lines += "- $($r.Game) | status=$($r.MlbStatus) | inSlate=$($r.InAstroddsSlate) | lineups=$($r.AwayLineupStatus)/$($r.HomeLineupStatus) | decision=$($r.Decision)"
    if ($r.MissingReason -ne "") {
        $lines += "  Issue: $($r.MissingReason)"
    }
}
$lines += ""

$lines += "ACTION"
if ($decision -eq "FULL_SLATE_MODEL_INCOMPLETE") {
    $lines += "The MLB live schedule has games that ASTRODDS did not model/score yet."
    $lines += "Next fix: build missing games into the ASTRODDS model/market slate before claiming full-slate best bets."
    $lines += "Selective official picks may still be sent only when SEND_OK."
} elseif ($decision -eq "FULL_SLATE_WAIT_FOR_LINEUPS") {
    $lines += "All games are in the ASTRODDS slate, but some lineups are not confirmed yet."
    $lines += "Run again closer to game time."
} else {
    $lines += "Full slate is complete. You can run best-bet selection safely."
}

$lines += ""
$lines += "Output master schedule CSV: $outMasterCsv"
$lines += "Output merged full slate CSV: $outMergedCsv"

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    date = $date
    decision = $decision
    mlbScheduleGames = $total
    gamesInCurrentAstroddsSlate = $inSlate
    gamesMissingFromAstroddsSlate = $missing
    confirmedLineupGames = $confirmed
    missingLineupGames = $notConfirmed
    sendOkPicksAvailable = $sendOk
    masterCsv = $outMasterCsv
    mergedCsv = $outMergedCsv
} | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output JSON: $outJson"
Write-Host "Master CSV: $outMasterCsv"
Write-Host "Merged CSV: $outMergedCsv"
Write-Host ""
