$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$currentSlate = Join-Path $astro "ASTRODDS-full-slate-context-final-latest.csv"
$backupLedger = Join-Path $astro "ASTRODDS-engine-signal-ledger.backup-before-clean-full-slate.json"

$outTxt  = Join-Path $astro "ASTRODDS-lineup-confirmed-source-match-FIXED-latest.txt"
$outCsv  = Join-Path $astro "ASTRODDS-lineup-confirmed-source-match-FIXED-latest.csv"
$outJson = Join-Path $astro "ASTRODDS-lineup-confirmed-source-match-FIXED-latest.json"

Write-Host ""
Write-Host "ASTRODDS 223B FIXED LINEUP BACKUP MATCH AUDIT" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - NO FALSE BACKUP MATCHES" -ForegroundColor Cyan
Write-Host ""

function Read-JsonSafe($path) {
    if (!(Test-Path $path)) { return $null }
    try { return Get-Content $path -Raw | ConvertFrom-Json }
    catch { return $null }
}

function Normalize-Rows($data) {
    if ($null -eq $data) { return @() }
    if ($data -is [System.Array]) { return @($data) }

    if ($data.rows) { return @(Normalize-Rows $data.rows) }
    if ($data.signals) { return @(Normalize-Rows $data.signals) }
    if ($data.ledger) { return @(Normalize-Rows $data.ledger) }
    if ($data.gameBoard) { return @(Normalize-Rows $data.gameBoard) }

    return @($data)
}

function Get-Prop($obj, $name) {
    if ($null -eq $obj) { return "" }
    $p = $obj.PSObject.Properties[$name]
    if ($null -eq $p) { return "" }
    if ($null -eq $p.Value) { return "" }
    return "$($p.Value)".Trim()
}

function First-Val($obj, $names) {
    foreach ($n in @($names)) {
        $v = Get-Prop $obj $n
        if ($v -ne "") { return $v }
    }
    return ""
}

function Norm-Game($s) {
    $x = "$s".ToLower().Trim()
    $x = $x.Replace(" vs ", " @ ")
    $x = $x -replace "\s+", " "
    return $x
}

if (!(Test-Path $currentSlate)) {
    Write-Host "ERROR: current slate missing:" -ForegroundColor Red
    Write-Host $currentSlate
    exit 0
}

$currentRows = @(Import-Csv $currentSlate)
$backupRows = @(Normalize-Rows (Read-JsonSafe $backupLedger))

$backupConfirmed = @($backupRows | Where-Object {
    (First-Val $_ @("awayLineupStatus", "away_lineup_status") -eq "confirmed") -and
    (First-Val $_ @("homeLineupStatus", "home_lineup_status") -eq "confirmed")
})

$resultRows = @()

foreach ($cur in $currentRows) {
    $curGame = First-Val $cur @("game", "Game", "matchup")
    $curPick = First-Val $cur @("pick", "Pick")
    $curGamePk = First-Val $cur @("gamePk", "gamePk", "game_id", "gameId")
    $curDate = First-Val $cur @("date", "GameTime", "commence_time")
    $curNorm = Norm-Game $curGame

    $candidateMatches = @()

    if ($curGamePk -ne "") {
        $candidateMatches = @($backupConfirmed | Where-Object {
            $bPk = First-Val $_ @("gamePk", "gamePk", "game_id", "gameId")
            $bPk -ne "" -and $bPk -eq $curGamePk
        })
    }

    $matchType = "NO_MATCH"
    if ($candidateMatches.Count -gt 0) {
        $matchType = "MATCH_BY_GAMEPK_REVIEW"
    } else {
        $candidateMatches = @($backupConfirmed | Where-Object {
            $bGame = First-Val $_ @("game", "Game", "matchup")
            $bNorm = Norm-Game $bGame
            $bNorm -ne "" -and $bNorm -eq $curNorm
        })

        if ($candidateMatches.Count -gt 0) {
            $matchType = "MATCH_BY_GAME_NAME_REVIEW"
        }
    }

    $best = $null
    if ($candidateMatches.Count -gt 0) {
        $best = $candidateMatches[0]
    }

    $backupGame = ""
    $backupDate = ""
    $backupGamePk = ""
    $backupAway = ""
    $backupHome = ""

    if ($null -ne $best) {
        $backupGame = First-Val $best @("game", "Game", "matchup")
        $backupDate = First-Val $best @("date", "GameTime", "commence_time", "snapshotTime")
        $backupGamePk = First-Val $best @("gamePk", "gamePk", "game_id", "gameId")
        $backupAway = First-Val $best @("awayLineupStatus", "away_lineup_status")
        $backupHome = First-Val $best @("homeLineupStatus", "home_lineup_status")
    }

    $recommendation = "No confirmed lineup backup matched this current game. Keep current lineup status as missing."
    if ($matchType -ne "NO_MATCH") {
        $recommendation = "Backup matched, but it is still backup data. Do not use for CLIENT_OFFICIAL unless freshness is proven."
    }

    $resultRows += ,[pscustomobject]@{
        Game = $curGame
        Pick = $curPick
        CurrentDate = $curDate
        CurrentGamePk = $curGamePk
        CurrentAwayLineup = First-Val $cur @("awayLineupStatus", "away_lineup_status")
        CurrentHomeLineup = First-Val $cur @("homeLineupStatus", "home_lineup_status")
        MatchType = $matchType
        BackupGame = $backupGame
        BackupDate = $backupDate
        BackupGamePk = $backupGamePk
        BackupAwayLineup = $backupAway
        BackupHomeLineup = $backupHome
        Recommendation = $recommendation
    }
}

$matched = @($resultRows | Where-Object { $_.MatchType -ne "NO_MATCH" })
$byPk = @($resultRows | Where-Object { $_.MatchType -eq "MATCH_BY_GAMEPK_REVIEW" })
$byName = @($resultRows | Where-Object { $_.MatchType -eq "MATCH_BY_GAME_NAME_REVIEW" })

$lines = @()
$lines += "ASTRODDS 223B FIXED LINEUP BACKUP MATCH AUDIT"
$lines += ""
$lines += "Current slate rows: $($currentRows.Count)"
$lines += "Backup rows: $($backupRows.Count)"
$lines += "Backup confirmed lineup rows: $($backupConfirmed.Count)"
$lines += "Matched current rows: $($matched.Count)"
$lines += "Matched by gamePk: $($byPk.Count)"
$lines += "Matched by game name: $($byName.Count)"
$lines += ""

$lines += "MATCH RESULTS"
foreach ($r in $resultRows) {
    $lines += "- $($r.Game) | Pick=$($r.Pick)"
    $lines += "  Current lineups: away=$($r.CurrentAwayLineup) home=$($r.CurrentHomeLineup)"
    $lines += "  MatchType: $($r.MatchType)"
    if ($r.BackupGame -ne "") {
        $lines += "  Backup: $($r.BackupGame) | away=$($r.BackupAwayLineup) home=$($r.BackupHomeLineup) | date=$($r.BackupDate)"
    }
    $lines += "  Recommendation: $($r.Recommendation)"
}
$lines += ""

$lines += "FINAL DECISION"
if ($matched.Count -eq 0) {
    $lines += "No live/current lineup confirmation is connected for today's slate."
    $lines += "Keep client official picks blocked or review-only until a real live lineup source is connected."
} else {
    $lines += "Some backup rows match, but backup data is not enough to unblock client official picks."
}
$lines += ""
$lines += "Never use stale backup lineups to unlock official client picks."

$resultRows | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    currentSlateRows = $currentRows.Count
    backupRows = $backupRows.Count
    backupConfirmedRows = $backupConfirmed.Count
    matchedCurrentRows = $matched.Count
    matchedByGamePk = $byPk.Count
    matchedByGameName = $byName.Count
    finalDecision = if ($matched.Count -eq 0) { "NO_CURRENT_LINEUP_SOURCE_CONNECTED" } else { "BACKUP_MATCH_REVIEW_ONLY" }
} | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output CSV: $outCsv"
Write-Host "Output JSON: $outJson"
Write-Host ""
