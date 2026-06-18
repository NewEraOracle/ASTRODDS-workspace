$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$publicBoard = Join-Path $astro "ASTRODDS-public-board-categories-latest.json"
$fullSlate = Join-Path $astro "ASTRODDS-full-slate-context-final-latest.csv"

$outLineupCsv = Join-Path $astro "ASTRODDS-live-lineup-status-latest.csv"
$outPatchedSlateCsv = Join-Path $astro "ASTRODDS-full-slate-context-live-lineup-patched-latest.csv"
$outGateTxt = Join-Path $astro "ASTRODDS-live-integrated-client-gate-latest.txt"
$outGateCsv = Join-Path $astro "ASTRODDS-live-integrated-client-gate-latest.csv"
$outGateJson = Join-Path $astro "ASTRODDS-live-integrated-client-gate-latest.json"
$outTelegram = Join-Path $astro "ASTRODDS-telegram-live-integrated-safe-latest.txt"

$culture = [System.Globalization.CultureInfo]::InvariantCulture

Write-Host ""
Write-Host "ASTRODDS 226 LIVE LINEUP PATCH + INTEGRATED SAFE GATE" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - REAL LINEUP CONNECTION" -ForegroundColor Cyan
Write-Host ""

function Read-JsonSafe($path) {
    if (!(Test-Path $path)) { return $null }
    try { return Get-Content $path -Raw | ConvertFrom-Json }
    catch { return $null }
}

function Normalize-Rows($data) {
    if ($null -eq $data) { return @() }
    if ($data -is [System.Array]) { return @($data) }

    if ($data.aPicks) { return @(Normalize-Rows $data.aPicks) }
    if ($data.rows) { return @(Normalize-Rows $data.rows) }
    if ($data.gameBoard) { return @(Normalize-Rows $data.gameBoard) }

    return @($data)
}

function Num($v) {
    if ($null -eq $v) { return $null }
    $s = "$v".Trim()
    if ($s -eq "") { return $null }
    $s = $s.Replace(",", ".")
    $n = 0.0
    if ([double]::TryParse($s, [System.Globalization.NumberStyles]::Any, $culture, [ref]$n)) {
        return $n
    }
    return $null
}

function Is-Prob($v) {
    $n = Num $v
    return ($null -ne $n -and $n -gt 0 -and $n -lt 1)
}

function Pct($v) {
    $n = Num $v
    if ($null -eq $n) { return "N/A" }
    if ($n -le 1) { $n = $n * 100 }
    return $n.ToString("0.0", $culture) + "%"
}

function Cents($v) {
    $n = Num $v
    if ($null -eq $n) { return "N/A" }
    if ($n -le 1) { $n = $n * 100 }
    return $n.ToString("0.0", $culture) + "¢"
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

function Is-TrueText($v) {
    $s = "$v".Trim().ToLower()
    return ($s -eq "true" -or $s -eq "1" -or $s -eq "yes")
}

function Normalize-Team($s) {
    $x = "$s".ToLower().Trim()
    $x = $x -replace "[^a-z0-9 ]", ""
    $x = $x -replace "\s+", " "
    return $x
}

function Split-Game($game) {
    $away = ""
    $homeTeam = ""

    if ($game -match "\s@\s") {
        $parts = $game -split "\s@\s", 2
        $away = "$($parts[0])".Trim()
        $homeTeam = "$($parts[1])".Trim()
    } elseif ($game -match "\svs\s") {
        $parts = $game -split "\svs\s", 2
        $away = "$($parts[0])".Trim()
        $homeTeam = "$($parts[1])".Trim()
    }

    return [pscustomobject]@{
        Away = $away
        Home = $homeTeam
        AwayNorm = Normalize-Team $away
        HomeNorm = Normalize-Team $homeTeam
    }
}

function Ensure-Prop($obj, $name, $value) {
    if ($null -eq $obj.PSObject.Properties[$name]) {
        $obj | Add-Member -NotePropertyName $name -NotePropertyValue $value
    } else {
        $obj.$name = $value
    }
}

function Get-MlbSchedule($date) {
    $url = "https://statsapi.mlb.com/api/v1/schedule?sportId=1&date=$date&hydrate=probablePitcher"
    try {
        return Invoke-RestMethod -Uri $url -Method Get -TimeoutSec 15
    } catch {
        Write-Host "WARNING: Could not fetch MLB schedule for $date" -ForegroundColor Yellow
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

function Count-ArraySafe($v) {
    if ($null -eq $v) { return 0 }
    return @($v).Count
}

if (!(Test-Path $fullSlate)) {
    Write-Host "ERROR: Missing full slate file:" -ForegroundColor Red
    Write-Host $fullSlate
    exit 0
}

$public = Read-JsonSafe $publicBoard
$publicAPicks = @()
if ($null -ne $public -and $public.aPicks) {
    $publicAPicks = @(Normalize-Rows $public.aPicks)
}

$slateRows = @(Import-Csv $fullSlate)

$today = Get-Date -Format "yyyy-MM-dd"

# If the slate has a date column, try using it. Otherwise use today.
$firstDate = ""
if ($slateRows.Count -gt 0) {
    $firstDate = First-Val $slateRows[0] @("date", "gameDate", "commenceDate")
}
if ($firstDate -match "^\d{4}-\d{2}-\d{2}") {
    $today = $matches[0]
}

$schedule = Get-MlbSchedule $today
$scheduleGames = @()

if ($null -ne $schedule -and $schedule.dates) {
    foreach ($d in @($schedule.dates)) {
        foreach ($g in @($d.games)) {
            $awayName = "$($g.teams.away.team.name)"
            $homeName = "$($g.teams.home.team.name)"
            $scheduleGames += ,[pscustomobject]@{
                GamePk = "$($g.gamePk)"
                Away = $awayName
                Home = $homeTeamName
                AwayNorm = Normalize-Team $awayName
                HomeNorm = Normalize-Team $homeTeamName
                Status = "$($g.status.detailedState)"
                GameDate = "$($g.gameDate)"
            }
        }
    }
}

$lineupRows = @()
$patchedRows = @()

foreach ($row in $slateRows) {
    $game = First-Val $row @("game", "Game")
    $pick = First-Val $row @("pick", "Pick")
    $split = Split-Game $game

    $sched = $scheduleGames | Where-Object {
        $_.AwayNorm -eq $split.AwayNorm -and $_.HomeNorm -eq $split.HomeNorm
    } | Select-Object -First 1

    $gamePk = ""
    $mlbStatus = ""
    $awayLineup = "missing"
    $homeLineup = "missing"
    $awayOrderCount = 0
    $homeOrderCount = 0
    $lineupSource = "NONE"
    $lineupReason = "No MLB schedule match."

    if ($null -ne $sched) {
        $gamePk = "$($sched.GamePk)"
        $mlbStatus = "$($sched.Status)"
        $lineupReason = "MLB schedule matched."

        $box = Get-MlbBoxscore $gamePk

        if ($null -ne $box) {
            $awayOrderCount = Count-ArraySafe $box.teams.away.battingOrder
            $homeOrderCount = Count-ArraySafe $box.teams.home.battingOrder

            $awayBattersCount = Count-ArraySafe $box.teams.away.batters
            $homeBattersCount = Count-ArraySafe $box.teams.home.batters

            if ($awayOrderCount -ge 9 -or $awayBattersCount -ge 9) {
                $awayLineup = "confirmed"
            }

            if ($homeOrderCount -ge 9 -or $homeBattersCount -ge 9) {
                $homeLineup = "confirmed"
            }

            $lineupSource = "MLB_STATS_API_BOXSCORE"
            $lineupReason = "Boxscore checked. awayOrder=$awayOrderCount homeOrder=$homeOrderCount."
        } else {
            $lineupSource = "MLB_STATS_API_SCHEDULE_ONLY"
            $lineupReason = "Schedule matched but boxscore not available."
        }
    }

    Ensure-Prop $row "liveLineupGamePk" $gamePk
    Ensure-Prop $row "liveMlbStatus" $mlbStatus
    Ensure-Prop $row "lineupSource" $lineupSource
    Ensure-Prop $row "lineupUpdatedAt" (Get-Date).ToString("o")
    Ensure-Prop $row "lineupReason" $lineupReason

    Ensure-Prop $row "awayLineupStatus" $awayLineup
    Ensure-Prop $row "homeLineupStatus" $homeLineup

    $modelOk = Is-Prob $row.modelProbability
    $marketOk = Is-Prob $row.marketProbability

    if ($awayLineup -eq "confirmed" -and $homeLineup -eq "confirmed" -and $modelOk -and $marketOk) {
        Ensure-Prop $row "paperOnly" "False"
    } else {
        Ensure-Prop $row "paperOnly" "True"
    }

    $lineupRows += ,[pscustomobject]@{
        Game = $game
        Pick = $pick
        GamePk = $gamePk
        MlbStatus = $mlbStatus
        AwayLineupStatus = $awayLineup
        HomeLineupStatus = $homeLineup
        AwayOrderCount = $awayOrderCount
        HomeOrderCount = $homeOrderCount
        Source = $lineupSource
        Reason = $lineupReason
    }

    $patchedRows += ,$row
}

$patchedRows | Export-Csv -NoTypeInformation -Encoding UTF8 $outPatchedSlateCsv
$lineupRows | Export-Csv -NoTypeInformation -Encoding UTF8 $outLineupCsv

$gateRows = @()

foreach ($p in $publicAPicks) {
    $game = First-Val $p @("game", "Game")
    $pick = First-Val $p @("pick", "Pick")

    if ($game -eq "" -or $pick -eq "") { continue }

    $slate = $patchedRows | Where-Object {
        (First-Val $_ @("game", "Game")) -eq $game -and
        (First-Val $_ @("pick", "Pick")) -eq $pick
    } | Select-Object -First 1

    if ($null -eq $slate) {
        $slate = $patchedRows | Where-Object {
            (First-Val $_ @("game", "Game")) -eq $game
        } | Select-Object -First 1
    }

    $hard = @()
    $warn = @()

    $marketConnected = First-Val $p @("marketConnected")
    $market = Num (First-Val $p @("market", "marketProbability", "price"))
    $publicModel = Num (First-Val $p @("model", "modelProbability", "ModelProbability"))
    $publicEdge = Num (First-Val $p @("edge", "edgePct", "EdgePct"))

    if (!(Is-TrueText $marketConnected)) {
        $hard += "marketConnected is not true"
    }

    if ($null -eq $market -or $market -le 0 -or $market -ge 1) {
        $hard += "invalid market price"
    }

    if ($null -eq $publicModel -or $publicModel -le 0 -or $publicModel -ge 1) {
        $hard += "invalid public model probability"
    }

    if ($null -eq $publicEdge -or $publicEdge -le 0) {
        $hard += "invalid or non-positive public edge"
    }

    $fullModel = $null
    $paperOnly = "True"
    $awayStatus = "missing"
    $homeStatus = "missing"
    $gamePk = ""
    $mlbStatus = ""

    if ($null -eq $slate) {
        $hard += "missing patched full slate row"
    } else {
        $fullModel = Num $slate.modelProbability
        $paperOnly = "$($slate.paperOnly)"
        $awayStatus = "$($slate.awayLineupStatus)"
        $homeStatus = "$($slate.homeLineupStatus)"
        $gamePk = "$($slate.liveLineupGamePk)"
        $mlbStatus = "$($slate.liveMlbStatus)"

        if (Is-TrueText $paperOnly) {
            $hard += "patched full slate paperOnly=True"
        }

        if ($awayStatus -ne "confirmed" -or $homeStatus -ne "confirmed") {
            $warn += "live/current lineups not confirmed"
        }

        if ($null -eq $fullModel -or $fullModel -le 0 -or $fullModel -ge 1) {
            $hard += "patched full slate modelProbability missing or invalid"
        }
    }

    if ($null -ne $publicModel -and $null -ne $fullModel) {
        $diff = [math]::Abs($publicModel - $fullModel)
        if ($diff -gt 0.05) {
            $hard += "model mismatch above 5%: public $(Pct $publicModel) vs fullSlate $(Pct $fullModel)"
        }
    }

    $decision = "CLIENT_OFFICIAL_SEND_OK"
    if ($hard.Count -gt 0) {
        $decision = "BLOCKED_FOR_REVIEW"
    } elseif ($warn.Count -gt 0) {
        $decision = "REVIEW_ONLY"
    }

    $gateRows += ,[pscustomobject]@{
        Decision = $decision
        Pick = $pick
        Game = $game
        Price = Cents $market
        PublicModel = Pct $publicModel
        FullSlateModel = Pct $fullModel
        Edge = Pct $publicEdge
        AwayLineupStatus = $awayStatus
        HomeLineupStatus = $homeStatus
        GamePk = $gamePk
        MlbStatus = $mlbStatus
        PaperOnly = $paperOnly
        HardBlocks = ($hard -join " | ")
        Warnings = ($warn -join " | ")
    }
}

$sendOk = @($gateRows | Where-Object { $_.Decision -eq "CLIENT_OFFICIAL_SEND_OK" }).Count
$review = @($gateRows | Where-Object { $_.Decision -eq "REVIEW_ONLY" }).Count
$blocked = @($gateRows | Where-Object { $_.Decision -eq "BLOCKED_FOR_REVIEW" }).Count

$clientDecision = "CLIENT_DROP_ALLOWED"
if ($blocked -gt 0) {
    $clientDecision = "CLIENT_DROP_BLOCKED"
} elseif ($review -gt 0) {
    $clientDecision = "CLIENT_DROP_REVIEW_ONLY"
}

$gateRows | Export-Csv -NoTypeInformation -Encoding UTF8 $outGateCsv

$telegramLines = @()

if ($clientDecision -eq "CLIENT_DROP_ALLOWED" -and $sendOk -gt 0) {
    $telegramLines += "🚀 ASTRODDS OFFICIAL PICKS"
    $telegramLines += "MLB MONEYLINE ONLY"
    $telegramLines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
    $telegramLines += ""
    $telegramLines += "Rules:"
    $telegramLines += "• No parlays"
    $telegramLines += "• 5% bankroll max"
    $telegramLines += "• Live lineups confirmed"
    $telegramLines += ""

    $i = 1
    foreach ($r in ($gateRows | Where-Object { $_.Decision -eq "CLIENT_OFFICIAL_SEND_OK" })) {
        $telegramLines += "✅ OFFICIAL BUY #$i"
        $telegramLines += "$($r.Pick) ML"
        $telegramLines += "Game: $($r.Game)"
        $telegramLines += "Entry: $($r.Price)"
        $telegramLines += "Model: $($r.PublicModel)"
        $telegramLines += "Full slate model: $($r.FullSlateModel)"
        $telegramLines += "Edge: $($r.Edge)"
        $telegramLines += "Lineups: confirmed / confirmed"
        $telegramLines += ""
        $i++
    }

    $telegramLines += "⚠️ Risk note:"
    $telegramLines += "These are data-driven value spots, not guaranteed wins."
    $telegramLines += ""
    $telegramLines += "ASTRODDS"
} else {
    $telegramLines += "🚫 ASTRODDS CLIENT DROP BLOCKED"
    $telegramLines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
    $telegramLines += ""
    $telegramLines += "No official client picks will be sent."
    $telegramLines += ""
    $telegramLines += "Reason:"
    $telegramLines += "• Client decision: $clientDecision"
    $telegramLines += "• SEND_OK picks: $sendOk"
    $telegramLines += "• REVIEW_ONLY picks: $review"
    $telegramLines += "• BLOCKED picks: $blocked"
    $telegramLines += ""

    foreach ($r in $gateRows) {
        $telegramLines += "- $($r.Decision) | $($r.Pick) | $($r.Game)"
        $telegramLines += "  Lineups: away=$($r.AwayLineupStatus) home=$($r.HomeLineupStatus)"
        if ($r.HardBlocks -ne "") { $telegramLines += "  Hard blocks: $($r.HardBlocks)" }
        if ($r.Warnings -ne "") { $telegramLines += "  Warnings: $($r.Warnings)" }
    }

    $telegramLines += ""
    $telegramLines += "Action:"
    $telegramLines += "Run this again closer to game time, after lineups are confirmed."
}

$telegramMessage = $telegramLines -join [Environment]::NewLine
$telegramMessage | Set-Content -Encoding UTF8 $outTelegram

$lines = @()
$lines += "ASTRODDS 226 LIVE LINEUP PATCH + INTEGRATED SAFE GATE"
$lines += ""
$lines += "Date used: $today"
$lines += "Schedule games found: $($scheduleGames.Count)"
$lines += "Slate rows patched: $($patchedRows.Count)"
$lines += "Public aPicks checked: $($gateRows.Count)"
$lines += ""
$lines += "CLIENT DECISION: $clientDecision"
$lines += "SEND_OK: $sendOk"
$lines += "REVIEW_ONLY: $review"
$lines += "BLOCKED: $blocked"
$lines += ""
$lines += "LINEUP STATUS"
foreach ($l in $lineupRows) {
    $lines += "- $($l.Game) | away=$($l.AwayLineupStatus) home=$($l.HomeLineupStatus) | gamePk=$($l.GamePk) | $($l.Reason)"
}
$lines += ""
$lines += "GATE RESULTS"
foreach ($g in $gateRows) {
    $lines += "- $($g.Decision) | $($g.Pick) | $($g.Game)"
    $lines += "  Price=$($g.Price) PublicModel=$($g.PublicModel) FullSlateModel=$($g.FullSlateModel) Edge=$($g.Edge)"
    $lines += "  Lineups: away=$($g.AwayLineupStatus) home=$($g.HomeLineupStatus) paperOnly=$($g.PaperOnly)"
    if ($g.HardBlocks -ne "") { $lines += "  Hard: $($g.HardBlocks)" }
    if ($g.Warnings -ne "") { $lines += "  Warn: $($g.Warnings)" }
}
$lines += ""
$lines += "TELEGRAM OUTPUT"
$lines += $outTelegram

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    dateUsed = $today
    scheduleGamesFound = $scheduleGames.Count
    slateRowsPatched = $patchedRows.Count
    publicAPicksChecked = $gateRows.Count
    clientDecision = $clientDecision
    sendOk = $sendOk
    reviewOnly = $review
    blocked = $blocked
    lineupCsv = $outLineupCsv
    patchedSlateCsv = $outPatchedSlateCsv
    telegramOutput = $outTelegram
    gateRows = @($gateRows)
} | ConvertTo-Json -Depth 20 | Set-Content -Encoding UTF8 $outGateJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outGateTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outGateTxt"
Write-Host "Output CSV: $outGateCsv"
Write-Host "Output JSON: $outGateJson"
Write-Host "Lineup CSV: $outLineupCsv"
Write-Host "Patched slate CSV: $outPatchedSlateCsv"
Write-Host "Telegram/blocked message: $outTelegram"
Write-Host ""

