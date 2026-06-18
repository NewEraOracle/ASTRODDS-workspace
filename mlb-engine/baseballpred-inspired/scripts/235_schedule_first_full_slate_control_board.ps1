$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$currentSlate = Join-Path $astro "ASTRODDS-full-slate-context-final-latest.csv"
$smartGateCsv = Join-Path $astro "ASTRODDS-smart-live-client-gate-latest.csv"

$outCsv  = Join-Path $astro "ASTRODDS-schedule-first-full-slate-control-board-latest.csv"
$outTxt  = Join-Path $astro "ASTRODDS-schedule-first-full-slate-control-board-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-schedule-first-full-slate-control-board-latest.json"

Write-Host ""
Write-Host "ASTRODDS 235 SCHEDULE-FIRST FULL SLATE CONTROL BOARD" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - NO GAME CAN DISAPPEAR" -ForegroundColor Cyan
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

$currentRows = Safe-Csv $currentSlate
$smartRows = Safe-Csv $smartGateCsv

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
foreach ($r in $smartRows) {
    $game = Get-Val $r @("Game", "game")
    if ($game -eq "") { continue }

    $split = Split-Game $game
    if ($split.Key -ne " @ ") {
        $smartByKey[$split.Key] = $r
    }
}

$schedule = Get-MlbSchedule $date
$rows = @()

if ($null -ne $schedule -and $schedule.dates) {
    foreach ($d in @($schedule.dates)) {
        foreach ($g in @($d.games)) {
            $awayTeamName = "$($g.teams.away.team.name)"
            $homeTeamName = "$($g.teams.home.team.name)"
            $gamePk = "$($g.gamePk)"
            $gameName = "$awayTeamName @ $homeTeamName"
            $key = (Normalize-Team $awayTeamName) + " @ " + (Normalize-Team $homeTeamName)
            $mlbStatus = "$($g.status.detailedState)"
            $gameDate = "$($g.gameDate)"

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
            $decision = "NO_MODEL_YET"
            $hardBlocks = ""
            $warnings = ""
            $price = ""

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
                $price = Get-Val $smart @("Price")

                if ($pick -eq "") { $pick = Get-Val $smart @("Pick") }
                if ($modelProbability -eq "") { $modelProbability = Get-Val $smart @("PublicModel") }
                if ($edgePct -eq "") { $edgePct = Get-Val $smart @("Edge") }
            }

            $coverageStatus = "READY_TO_EVALUATE"

            if ($inAstroddsSlate -eq "NO") {
                $coverageStatus = "NO_MODEL_YET"
                $decision = "NO_MODEL_YET"
                $hardBlocks = "missing from ASTRODDS model slate"
            } elseif ($hasSmartGate -eq "NO") {
                $coverageStatus = "NEEDS_SMART_GATE"
                $decision = "NEEDS_SMART_GATE"
                $warnings = "game exists in context but was not evaluated by smart gate"
            }

            if ($awayLineupStatus -ne "confirmed" -or $homeLineupStatus -ne "confirmed") {
                if ($warnings -ne "") { $warnings += " | " }
                $warnings += "lineup not fully confirmed"
            }

            $rows += ,[pscustomobject]@{
                Date = $date
                GamePk = $gamePk
                Game = $gameName
                AwayTeam = $awayTeamName
                HomeTeam = $homeTeamName
                MlbStatus = $mlbStatus
                GameDate = $gameDate
                InAstroddsSlate = $inAstroddsSlate
                HasSmartGate = $hasSmartGate
                CoverageStatus = $coverageStatus
                Decision = $decision
                Pick = $pick
                Price = $price
                ModelProbability = $modelProbability
                MarketProbability = $marketProbability
                EdgePct = $edgePct
                AwayLineupStatus = $awayLineupStatus
                HomeLineupStatus = $homeLineupStatus
                AwayOrderCount = $awayOrderCount
                HomeOrderCount = $homeOrderCount
                HardBlocks = $hardBlocks
                Warnings = $warnings
            }
        }
    }
}

$total = $rows.Count
$inSlate = @($rows | Where-Object { $_.InAstroddsSlate -eq "YES" }).Count
$missingModel = @($rows | Where-Object { $_.CoverageStatus -eq "NO_MODEL_YET" }).Count
$needsGate = @($rows | Where-Object { $_.CoverageStatus -eq "NEEDS_SMART_GATE" }).Count
$sendOk = @($rows | Where-Object { $_.Decision -eq "CLIENT_OFFICIAL_SEND_OK" }).Count
$blocked = @($rows | Where-Object { $_.Decision -eq "BLOCKED_FOR_REVIEW" }).Count
$confirmedLineups = @($rows | Where-Object { $_.AwayLineupStatus -eq "confirmed" -and $_.HomeLineupStatus -eq "confirmed" }).Count
$missingLineups = @($rows | Where-Object { $_.AwayLineupStatus -ne "confirmed" -or $_.HomeLineupStatus -ne "confirmed" }).Count

$fullSlateDecision = "FULL_SLATE_READY"

if ($missingModel -gt 0) {
    $fullSlateDecision = "FULL_SLATE_MODEL_INCOMPLETE"
} elseif ($needsGate -gt 0) {
    $fullSlateDecision = "FULL_SLATE_NEEDS_SMART_GATE"
} elseif ($missingLineups -gt 0) {
    $fullSlateDecision = "FULL_SLATE_WAIT_FOR_LINEUPS"
}

$rows | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$lines = @()
$lines += "ASTRODDS 235 SCHEDULE-FIRST FULL SLATE CONTROL BOARD"
$lines += ""
$lines += "Date: $date"
$lines += "MLB schedule games: $total"
$lines += "Games in ASTRODDS slate: $inSlate"
$lines += "NO_MODEL_YET games: $missingModel"
$lines += "NEEDS_SMART_GATE games: $needsGate"
$lines += "SEND_OK picks: $sendOk"
$lines += "BLOCKED picks: $blocked"
$lines += "Confirmed lineup games: $confirmedLineups"
$lines += "Missing lineup games: $missingLineups"
$lines += ""
$lines += "FULL SLATE DECISION: $fullSlateDecision"
$lines += ""

$lines += "CONTROL BOARD"
foreach ($r in $rows) {
    $lines += "- $($r.Game) | status=$($r.MlbStatus) | coverage=$($r.CoverageStatus) | decision=$($r.Decision) | lineups=$($r.AwayLineupStatus)/$($r.HomeLineupStatus)"
    if ($r.Pick -ne "") {
        $lines += "  Pick: $($r.Pick) | Model=$($r.ModelProbability) | Edge=$($r.EdgePct)"
    }
    if ($r.HardBlocks -ne "") {
        $lines += "  Hard: $($r.HardBlocks)"
    }
    if ($r.Warnings -ne "") {
        $lines += "  Warn: $($r.Warnings)"
    }
}
$lines += ""

$lines += "ACTION"
if ($fullSlateDecision -eq "FULL_SLATE_MODEL_INCOMPLETE") {
    $lines += "Do not call this full-slate best bets yet."
    $lines += "Next: connect model/market scoring for NO_MODEL_YET games."
} elseif ($fullSlateDecision -eq "FULL_SLATE_NEEDS_SMART_GATE") {
    $lines += "Some games exist in ASTRODDS context but were not evaluated by the smart gate."
    $lines += "Next: make smart gate evaluate every context row, not just public aPicks."
} elseif ($fullSlateDecision -eq "FULL_SLATE_WAIT_FOR_LINEUPS") {
    $lines += "All games are modeled/gated but some lineups are missing."
    $lines += "Run again closer to game time."
} else {
    $lines += "Full slate is ready for best bet selection."
}

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    date = $date
    fullSlateDecision = $fullSlateDecision
    mlbScheduleGames = $total
    gamesInAstroddsSlate = $inSlate
    noModelYetGames = $missingModel
    needsSmartGateGames = $needsGate
    sendOkPicks = $sendOk
    blockedPicks = $blocked
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
