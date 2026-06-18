$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$clientSafeBoard = Join-Path $astro "ASTRODDS-client-safe-public-board-latest.csv"
$clientSafeRanker = Join-Path $astro "ASTRODDS-baseballpred-full-slate-ranker-client-safe-latest.csv"
$fullSlate = Join-Path $astro "ASTRODDS-full-slate-context-final-latest.csv"
$lineupMatchAudit = Join-Path $astro "ASTRODDS-lineup-confirmed-source-match-FIXED-latest.csv"

$outTxt  = Join-Path $astro "ASTRODDS-lineup-aware-client-policy-latest.txt"
$outCsv  = Join-Path $astro "ASTRODDS-lineup-aware-client-policy-latest.csv"
$outJson = Join-Path $astro "ASTRODDS-lineup-aware-client-policy-latest.json"

Write-Host ""
Write-Host "ASTRODDS 224 LINEUP-AWARE CLIENT POLICY" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - OFFICIAL REQUIRES LIVE LINEUPS" -ForegroundColor Cyan
Write-Host ""

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

$boardRows = Safe-Csv $clientSafeBoard
$rankerRows = Safe-Csv $clientSafeRanker
$slateRows = Safe-Csv $fullSlate
$lineupAuditRows = Safe-Csv $lineupMatchAudit

$policyRows = @()

foreach ($r in $boardRows) {
    $game = Get-Val $r @("Game", "game")
    $pick = Get-Val $r @("Pick", "pick")

    if ($game -eq "" -or $pick -eq "") { continue }

    $slate = $slateRows | Where-Object {
        (Get-Val $_ @("game", "Game")) -eq $game -and
        (Get-Val $_ @("pick", "Pick")) -eq $pick
    } | Select-Object -First 1

    if ($null -eq $slate) {
        $slate = $slateRows | Where-Object {
            (Get-Val $_ @("game", "Game")) -eq $game
        } | Select-Object -First 1
    }

    $lineupAudit = $lineupAuditRows | Where-Object {
        (Get-Val $_ @("Game", "game")) -eq $game -and
        (Get-Val $_ @("Pick", "pick")) -eq $pick
    } | Select-Object -First 1

    $awayStatus = Get-Val $slate @("awayLineupStatus", "away_lineup_status")
    $homeStatus = Get-Val $slate @("homeLineupStatus", "home_lineup_status")

    $matchType = Get-Val $lineupAudit @("MatchType")
    $backupGame = Get-Val $lineupAudit @("BackupGame")

    $baseDecision = Get-Val $r @("Decision", "clientSafeDecision")
    $hardBlocks = Get-Val $r @("HardBlocks", "hardBlocks")
    $warnings = Get-Val $r @("Warnings", "warnings")

    $lineupDecision = "LINEUP_BLOCKED"
    $lineupReason = ""

    if ($awayStatus -eq "confirmed" -and $homeStatus -eq "confirmed") {
        $lineupDecision = "LINEUP_CONFIRMED"
        $lineupReason = "Both lineups confirmed from current full slate source."
    } elseif ($matchType -ne "" -and $matchType -ne "NO_MATCH") {
        $lineupDecision = "LINEUP_REVIEW_ONLY_BACKUP_MATCH"
        $lineupReason = "Backup lineup matched, but backup is not trusted for official client picks."
    } else {
        $lineupDecision = "LINEUP_MISSING_REVIEW_ONLY"
        $lineupReason = "Live/current lineups are missing. Keep pick review-only or blocked."
    }

    $finalDecision = "BLOCKED_FOR_REVIEW"

    if ($baseDecision -eq "CLIENT_OFFICIAL_SEND_OK" -and $lineupDecision -eq "LINEUP_CONFIRMED") {
        $finalDecision = "CLIENT_OFFICIAL_SEND_OK"
    } elseif ($baseDecision -eq "CLIENT_OFFICIAL_SEND_OK" -and $lineupDecision -ne "LINEUP_CONFIRMED") {
        $finalDecision = "REVIEW_ONLY"
    } elseif ($baseDecision -eq "REVIEW_ONLY") {
        $finalDecision = "REVIEW_ONLY"
    } else {
        $finalDecision = "BLOCKED_FOR_REVIEW"
    }

    $policyRows += ,[pscustomobject]@{
        FinalDecision = $finalDecision
        BaseDecision = $baseDecision
        LineupDecision = $lineupDecision
        Game = $game
        Pick = $pick
        Price = Get-Val $r @("Price")
        ModelProbability = Get-Val $r @("ModelProbability", "modelProbabilityText")
        FullSlateModel = Get-Val $r @("FullSlateModel", "fullSlateModelProbability")
        Edge = Get-Val $r @("Edge", "edgePct")
        AwayLineupStatus = $awayStatus
        HomeLineupStatus = $homeStatus
        BackupMatchType = $matchType
        BackupGame = $backupGame
        HardBlocks = $hardBlocks
        Warnings = $warnings
        LineupReason = $lineupReason
    }
}

$sendOk = @($policyRows | Where-Object { $_.FinalDecision -eq "CLIENT_OFFICIAL_SEND_OK" }).Count
$review = @($policyRows | Where-Object { $_.FinalDecision -eq "REVIEW_ONLY" }).Count
$blocked = @($policyRows | Where-Object { $_.FinalDecision -eq "BLOCKED_FOR_REVIEW" }).Count
$missingLineups = @($policyRows | Where-Object { $_.LineupDecision -eq "LINEUP_MISSING_REVIEW_ONLY" }).Count
$confirmedLineups = @($policyRows | Where-Object { $_.LineupDecision -eq "LINEUP_CONFIRMED" }).Count

$clientDecision = "CLIENT_DROP_ALLOWED"
if ($blocked -gt 0) {
    $clientDecision = "CLIENT_DROP_BLOCKED"
} elseif ($review -gt 0) {
    $clientDecision = "CLIENT_DROP_REVIEW_ONLY"
}

$lines = @()
$lines += "ASTRODDS 224 LINEUP-AWARE CLIENT POLICY"
$lines += ""
$lines += "CLIENT DECISION: $clientDecision"
$lines += "SEND_OK: $sendOk"
$lines += "REVIEW_ONLY: $review"
$lines += "BLOCKED: $blocked"
$lines += "Confirmed lineup rows: $confirmedLineups"
$lines += "Missing lineup rows: $missingLineups"
$lines += ""

$lines += "POLICY RESULT"
if ($policyRows.Count -eq 0) {
    $lines += "- No client-safe board rows found. Run 219 first."
} else {
    foreach ($p in $policyRows) {
        $lines += "- $($p.FinalDecision) | $($p.Pick) | $($p.Game)"
        $lines += "  Lineups: away=$($p.AwayLineupStatus) home=$($p.HomeLineupStatus)"
        $lines += "  Lineup gate: $($p.LineupDecision)"
        $lines += "  Reason: $($p.LineupReason)"
        if ($p.HardBlocks -ne "") {
            $lines += "  Hard blocks: $($p.HardBlocks)"
        }
        if ($p.Warnings -ne "") {
            $lines += "  Warnings: $($p.Warnings)"
        }
    }
}
$lines += ""

$lines += "OFFICIAL RULE"
$lines += "A pick cannot become client official unless:"
$lines += "- base client-safe gate is CLIENT_OFFICIAL_SEND_OK"
$lines += "- away lineup is confirmed"
$lines += "- home lineup is confirmed"
$lines += "- no stale backup lineup is used"
$lines += ""
$lines += "Current action: if lineups are missing, do not send official Telegram picks."

$policyRows | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    clientDecision = $clientDecision
    sendOk = $sendOk
    reviewOnly = $review
    blocked = $blocked
    confirmedLineupRows = $confirmedLineups
    missingLineupRows = $missingLineups
    rule = "Client official requires current/live confirmed lineups. Backup lineups cannot unlock official picks."
} | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output CSV: $outCsv"
Write-Host "Output JSON: $outJson"
Write-Host ""
