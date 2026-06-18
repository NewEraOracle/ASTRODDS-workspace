$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$currentSlate = Join-Path $astro "ASTRODDS-full-slate-context-final-latest.csv"
$backupLedger = Join-Path $astro "ASTRODDS-engine-signal-ledger.backup-before-clean-full-slate.json"
$clientSafeBoard = Join-Path $astro "ASTRODDS-client-safe-public-board-latest.csv"

$outTxt  = Join-Path $astro "ASTRODDS-lineup-confirmed-source-match-latest.txt"
$outCsv  = Join-Path $astro "ASTRODDS-lineup-confirmed-source-match-latest.csv"
$outJson = Join-Path $astro "ASTRODDS-lineup-confirmed-source-match-latest.json"

Write-Host ""
Write-Host "ASTRODDS 223 MATCH CONFIRMED LINEUP SOURCE TO CURRENT SLATE" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - DO NOT TRUST STALE BACKUP BLINDLY" -ForegroundColor Cyan
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

    $props = @($data.PSObject.Properties)
    $arrayProps = @($props | Where-Object {
        ($_.Value -is [System.Array]) -or (($_.Value -is [System.Collections.IEnumerable]) -and !($_.Value -is [string]))
    })

    if ($arrayProps.Count -gt 0) {
        $max = 0
        foreach ($p in $arrayProps) {
            $count = @($p.Value).Count
            if ($count -gt $max) { $max = $count }
        }

        if ($max -gt 1) {
            $rows = @()
            for ($i = 0; $i -lt $max; $i++) {
                $h = [ordered]@{}
                foreach ($p in $props) {
                    $v = $p.Value
                    if (($v -is [System.Array]) -or (($v -is [System.Collections.IEnumerable]) -and !($v -is [string]))) {
                        $arr = @($v)
                        if ($i -lt $arr.Count) { $h[$p.Name] = $arr[$i] }
                        else { $h[$p.Name] = "" }
                    } else {
                        $h[$p.Name] = $v
                    }
                }
                $rows += ,([pscustomobject]$h)
            }
            return @($rows)
        }
    }

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
$backupRaw = Read-JsonSafe $backupLedger
$backupRows = @(Normalize-Rows $backupRaw)

$clientSafeRows = @()
if (Test-Path $clientSafeBoard) {
    try { $clientSafeRows = @(Import-Csv $clientSafeBoard) }
    catch { $clientSafeRows = @() }
}

$backupConfirmed = @($backupRows | Where-Object {
    (First-Val $_ @("awayLineupStatus", "away_lineup_status") -eq "confirmed") -or
    (First-Val $_ @("homeLineupStatus", "home_lineup_status") -eq "confirmed")
})

$matchRows = @()

foreach ($cur in $currentRows) {
    $game = First-Val $cur @("game", "Game")
    $pick = First-Val $cur @("pick", "Pick")
    $gamePk = First-Val $cur @("gamePk", "gamePk", "game_id", "gameId")
    $date = First-Val $cur @("date", "GameTime", "commence_time")

    $matches = @()

    if ($gamePk -ne "") {
        $matches = @($backupConfirmed | Where-Object {
            (First-Val $_ @("gamePk", "gamePk", "game_id", "gameId") -eq $gamePk)
        })
    }

    if ($matches.Count -eq 0) {
        $ng = Norm-Game $game
        $matches = @($backupConfirmed | Where-Object {
            (Norm-Game (First-Val $_ @("game", "Game", "matchup"))) -eq $ng
        })
    }

    $best = $matches | Select-Object -First 1

    $awayCur = First-Val $cur @("awayLineupStatus", "away_lineup_status")
    $homeCur = First-Val $cur @("homeLineupStatus", "home_lineup_status")

    $awayBackup = ""
    $homeBackup = ""
    $backupGame = ""
    $backupDate = ""
    $backupGamePk = ""
    $trust = "NO_MATCH"
    $reason = "No confirmed lineup backup matched this current slate row."

    if ($null -ne $best) {
        $awayBackup = First-Val $best @("awayLineupStatus", "away_lineup_status")
        $homeBackup = First-Val $best @("homeLineupStatus", "home_lineup_status")
        $backupGame = First-Val $best @("game", "Game", "matchup")
        $backupDate = First-Val $best @("date", "GameTime", "commence_time", "snapshotTime")
        $backupGamePk = First-Val $best @("gamePk", "gamePk", "game_id", "gameId")

        $trust = "MATCH_FOUND_REVIEW"
        $reason = "Confirmed lineup exists in backup, but backup source must be reviewed before live use."

        if ($gamePk -ne "" -and $backupGamePk -ne "" -and $gamePk -eq $backupGamePk) {
            $trust = "MATCH_BY_GAMEPK_REVIEW"
            $reason = "Confirmed lineup matched by gamePk, but still review because file is backup."
        } elseif ((Norm-Game $game) -eq (Norm-Game $backupGame)) {
            $trust = "MATCH_BY_GAME_REVIEW"
            $reason = "Confirmed lineup matched by game name, but still review because file is backup."
        }
    }

    $clientDecision = ""
    $safe = $clientSafeRows | Where-Object {
        "$($_.Game)".Trim() -eq $game -and "$($_.Pick)".Trim() -eq $pick
    } | Select-Object -First 1

    if ($null -ne $safe) {
        $clientDecision = "$($safe.Decision)"
    }

    $matchRows += ,[pscustomobject]@{
        Game = $game
        Pick = $pick
        CurrentDate = $date
        CurrentGamePk = $gamePk
        CurrentAwayLineup = $awayCur
        CurrentHomeLineup = $homeCur
        BackupMatchedGame = $backupGame
        BackupDate = $backupDate
        BackupGamePk = $backupGamePk
        BackupAwayLineup = $awayBackup
        BackupHomeLineup = $homeBackup
        MatchTrust = $trust
        ClientSafeDecision = $clientDecision
        Recommendation = $reason
    }
}

$matched = @($matchRows | Where-Object { $_.MatchTrust -ne "NO_MATCH" })
$gamePkMatched = @($matchRows | Where-Object { $_.MatchTrust -eq "MATCH_BY_GAMEPK_REVIEW" })
$gameNameMatched = @($matchRows | Where-Object { $_.MatchTrust -eq "MATCH_BY_GAME_REVIEW" })

$lines = @()
$lines += "ASTRODDS 223 MATCH CONFIRMED LINEUP SOURCE TO CURRENT SLATE"
$lines += ""
$lines += "Current slate rows: $($currentRows.Count)"
$lines += "Backup ledger rows: $($backupRows.Count)"
$lines += "Backup confirmed lineup rows: $($backupConfirmed.Count)"
$lines += "Current rows matched to confirmed backup: $($matched.Count)"
$lines += "Matched by gamePk: $($gamePkMatched.Count)"
$lines += "Matched by game name: $($gameNameMatched.Count)"
$lines += ""

$lines += "MATCH RESULTS"
foreach ($r in $matchRows) {
    $lines += "- $($r.Game) | Pick=$($r.Pick)"
    $lines += "  Current lineups: away=$($r.CurrentAwayLineup) home=$($r.CurrentHomeLineup)"
    $lines += "  MatchTrust: $($r.MatchTrust)"
    if ($r.BackupMatchedGame -ne "") {
        $lines += "  Backup: $($r.BackupMatchedGame) | away=$($r.BackupAwayLineup) home=$($r.BackupHomeLineup) | date=$($r.BackupDate)"
    }
    $lines += "  Recommendation: $($r.Recommendation)"
}
$lines += ""

$lines += "INTERPRETATION"
if ($matched.Count -eq 0) {
    $lines += "- No current slate games matched the confirmed lineup backup."
    $lines += "- Do not connect the backup. Keep lineups missing."
} else {
    $lines += "- Confirmed lineup backup matched some current slate rows."
    $lines += "- Because the source is a backup, do not use it for CLIENT_OFFICIAL automatically."
    $lines += "- Next step: create a live lineup updater or time-aware lineup rule."
}
$lines += ""

$lines += "NEXT STEP"
$lines += "224 should create a safe lineup policy:"
$lines += "- Before confirmed lineups: REVIEW_ONLY or BLOCKED."
$lines += "- After live confirmed lineups are available from a current file/source: allow gate evaluation."
$lines += "- Never use stale backup lineups for client official picks."

$matchRows | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    currentSlateRows = $currentRows.Count
    backupRows = $backupRows.Count
    backupConfirmedRows = $backupConfirmed.Count
    currentRowsMatched = $matched.Count
    matchedByGamePk = $gamePkMatched.Count
    matchedByGameName = $gameNameMatched.Count
    recommendation = "Do not trust backup lineups for client official picks unless timestamp/gamePk proves freshness."
} | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output CSV: $outCsv"
Write-Host "Output JSON: $outJson"
Write-Host ""
