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

function Set-Prop($obj, $name, $value) {
    if ($obj.PSObject.Properties[$name]) {
        $obj.$name = $value
    } else {
        $obj | Add-Member -MemberType NoteProperty -Name $name -Value $value -Force
    }
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

function Normalize-Team($s) {
    $x = "$s".ToLower().Trim()
    $x = $x -replace "[^a-z0-9 ]", ""
    $x = $x -replace "\s+", " "
    return $x
}

function Game-Key($game) {
    $g = "$game"
    if ($g -match "\s@\s") {
        $parts = $g -split "\s@\s", 2
        return (Normalize-Team $parts[0]) + " @ " + (Normalize-Team $parts[1])
    }
    return (Normalize-Team $g)
}

function Invoke-Json($url, $timeout = 30) {
    try { return Invoke-RestMethod -Uri $url -Method Get -TimeoutSec $timeout }
    catch { return $null }
}

function Parse-Prob($row) {
    $candidates = @(
        (Get-Val $row @("FullSlateModel")),
        (Get-Val $row @("PublicModel")),
        (Get-Val $row @("ModelProbability")),
        (Get-Val $row @("Model"))
    )
    foreach ($c in $candidates) {
        $n = Num $c
        if ($null -ne $n) {
            if ($n -gt 1) { return ($n / 100.0) }
            return $n
        }
    }
    return $null
}

function Parse-EntryDecimal($row) {
    $n = Num (Get-Val $row @("EntryPrice","Entry","BestEntry"))
    if ($null -eq $n) { return $null }
    if ($n -gt 1) { return ($n / 100.0) }
    return $n
}

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$ledgerCsv = Join-Path $astro "ASTRODDS-official-picks-ledger-latest.csv"
$ledgerJson = Join-Path $astro "ASTRODDS-official-picks-ledger-latest.json"
$outTxt = Join-Path $astro "ASTRODDS-347-force-settle-pending-officials-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-347-force-settle-pending-officials-latest.json"
$backup = Join-Path $astro ("ASTRODDS-official-picks-ledger-backup-before-347-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".csv")

Write-Host ""
Write-Host "ASTRODDS 347 FORCE SETTLE PENDING OFFICIALS" -ForegroundColor Cyan
Write-Host "Matches pending ledger rows to MLB final/game-over schedule by GamePk or game name." -ForegroundColor Cyan
Write-Host ""

$ledger = Safe-Csv $ledgerCsv
if ($ledger.Count -eq 0) {
    "No ledger rows found." | Set-Content -Encoding UTF8 $outTxt
    Write-Host "No ledger rows found." -ForegroundColor Yellow
    exit 0
}

Copy-Item $ledgerCsv $backup -Force

# Fetch schedule for relevant dates from pending rows + today/yesterday for safety.
$dates = New-Object System.Collections.Generic.HashSet[string]
[void]$dates.Add((Get-Date).ToString("yyyy-MM-dd"))
[void]$dates.Add((Get-Date).AddDays(-1).ToString("yyyy-MM-dd"))
[void]$dates.Add((Get-Date).AddDays(1).ToString("yyyy-MM-dd"))

foreach ($r in $ledger) {
    $d = Get-Val $r @("ScheduleDate","Date")
    if ($d -match "^\d{4}-\d{2}-\d{2}$") { [void]$dates.Add($d) }
}

$games = @()
foreach ($date in $dates) {
    $url = "https://statsapi.mlb.com/api/v1/schedule?sportId=1&date=$date&hydrate=team"
    $resp = Invoke-Json $url 30
    if ($null -eq $resp) { continue }

    foreach ($dd in @($resp.dates)) {
        foreach ($g in @($dd.games)) {
            $awayTeam = "$($g.teams.away.team.name)"
            $homeTeam = "$($g.teams.home.team.name)"
            $awayScore = Num "$($g.teams.away.score)"
            $homeScore = Num "$($g.teams.home.score)"
            $status = "$($g.status.detailedState)"
            $gamePk = "$($g.gamePk)"
            $gameName = "$awayTeam @ $homeTeam"

            $winner = ""
            if ($status -match "Final|Game Over|Completed" -and $null -ne $awayScore -and $null -ne $homeScore) {
                if ($awayScore -gt $homeScore) { $winner = $awayTeam }
                elseif ($homeScore -gt $awayScore) { $winner = $homeTeam }
            }

            $games += ,[pscustomobject]@{
                Date = $date
                GamePk = $gamePk
                Game = $gameName
                GameKey = Game-Key $gameName
                AwayTeam = $awayTeam
                HomeTeam = $homeTeam
                AwayScore = $awayScore
                HomeScore = $homeScore
                MlbStatus = $status
                Winner = $winner
                FinalScore = "$awayTeam $awayScore - $homeTeam $homeScore"
            }
        }
    }
}

function Find-Game($row, $games) {
    $gamePk = Get-Val $row @("GamePk")
    $game = Get-Val $row @("Game")
    if ($gamePk -ne "") {
        $m = @($games | Where-Object { "$($_.GamePk)" -eq "$gamePk" } | Select-Object -First 1)
        if ($m.Count -gt 0) { return $m[0] }
    }

    $key = Game-Key $game
    $m2 = @($games | Where-Object { $_.GameKey -eq $key } | Select-Object -First 1)
    if ($m2.Count -gt 0) { return $m2[0] }

    # Very soft fallback: both teams included.
    $ng = Normalize-Team $game
    foreach ($g in $games) {
        $ak = Normalize-Team $g.AwayTeam
        $hk = Normalize-Team $g.HomeTeam
        if ($ng -like "*$ak*" -and $ng -like "*$hk*") { return $g }
    }

    return $null
}

$settledNow = 0
$stillPending = 0
$notMatched = 0
$alreadySettled = 0
$changes = @()

foreach ($r in $ledger) {
    $status = Get-Val $r @("Status")
    if ($status -eq "SETTLED") {
        $alreadySettled++
        continue
    }

    if ($status -ne "PENDING_RESULT" -and $status -ne "") {
        continue
    }

    $match = Find-Game $r $games
    if ($null -eq $match) {
        $notMatched++
        $changes += ,[pscustomobject]@{
            Pick = Get-Val $r @("Pick")
            Game = Get-Val $r @("Game")
            Action = "NO_MATCH"
            Reason = "No matching MLB game found by GamePk or game string."
        }
        continue
    }

    if ($match.MlbStatus -notmatch "Final|Game Over|Completed" -or $match.Winner -eq "") {
        $stillPending++
        Set-Prop $r "MlbStatusAtSettleCheck" $match.MlbStatus
        $changes += ,[pscustomobject]@{
            Pick = Get-Val $r @("Pick")
            Game = Get-Val $r @("Game")
            Action = "STILL_PENDING"
            Reason = "Matched game but status=$($match.MlbStatus)."
        }
        continue
    }

    $pick = Get-Val $r @("Pick")
    $result = "LOSS"
    $outcome = 0
    if ((Normalize-Team $pick) -eq (Normalize-Team $match.Winner)) {
        $result = "WIN"
        $outcome = 1
    }

    $prob = Parse-Prob $r
    $entry = Parse-EntryDecimal $r

    $roi = ""
    if ($null -ne $entry -and $entry -gt 0) {
        if ($result -eq "WIN") {
            $roiVal = ((1.0 - $entry) / $entry) * 100.0
            $roi = ([math]::Round($roiVal, 1)).ToString() + "%"
        } else {
            $roi = "-100%"
        }
    }

    $brier = ""
    $logloss = ""
    if ($null -ne $prob -and $prob -gt 0 -and $prob -lt 1) {
        $brier = [math]::Round([math]::Pow(($prob - $outcome), 2), 4)
        if ($outcome -eq 1) {
            $logloss = [math]::Round(-[math]::Log($prob), 4)
        } else {
            $logloss = [math]::Round(-[math]::Log(1.0 - $prob), 4)
        }
    }

    Set-Prop $r "Status" "SETTLED"
    Set-Prop $r "Result" $result
    Set-Prop $r "Winner" $match.Winner
    Set-Prop $r "FinalScore" $match.FinalScore
    Set-Prop $r "MlbStatusAtSettle" $match.MlbStatus
    Set-Prop $r "SettledAt" (Get-Date).ToString("o")
    Set-Prop $r "ROI" $roi
    Set-Prop $r "BrierComponent" "$brier"
    Set-Prop $r "LogLossComponent" "$logloss"
    if ((Get-Val $r @("GamePk")) -eq "") { Set-Prop $r "GamePk" $match.GamePk }
    if ((Get-Val $r @("ScheduleDate")) -eq "") { Set-Prop $r "ScheduleDate" $match.Date }

    $settledNow++
    $changes += ,[pscustomobject]@{
        Pick = $pick
        Game = Get-Val $r @("Game")
        MatchedGame = $match.Game
        Action = "SETTLED_$result"
        Winner = $match.Winner
        FinalScore = $match.FinalScore
        ROI = $roi
        Brier = "$brier"
        LogLoss = "$logloss"
    }
}

$ledger | Export-Csv -NoTypeInformation -Encoding UTF8 $ledgerCsv
$ledger | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $ledgerJson

$pendingAfter = @($ledger | Where-Object { (Get-Val $_ @("Status")) -eq "PENDING_RESULT" }).Count
$settledAfter = @($ledger | Where-Object { (Get-Val $_ @("Status")) -eq "SETTLED" }).Count
$wins = @($ledger | Where-Object { (Get-Val $_ @("Status")) -eq "SETTLED" -and (Get-Val $_ @("Result")) -eq "WIN" }).Count
$losses = @($ledger | Where-Object { (Get-Val $_ @("Status")) -eq "SETTLED" -and (Get-Val $_ @("Result")) -eq "LOSS" }).Count

$lines = @()
$lines += "ASTRODDS 347 FORCE SETTLE PENDING OFFICIALS"
$lines += ""
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$lines += "Ledger rows: $($ledger.Count)"
$lines += "Already settled before run: $alreadySettled"
$lines += "Settled now: $settledNow"
$lines += "Still pending matched but not final: $stillPending"
$lines += "Not matched: $notMatched"
$lines += "Pending after: $pendingAfter"
$lines += "Settled after: $settledAfter"
$lines += "Wins: $wins"
$lines += "Losses: $losses"
$lines += "Backup: $backup"
$lines += ""
$lines += "CHANGES"
foreach ($c in $changes) {
    $lines += "- $($c.Action) | $($c.Pick) | $($c.Game)"
    if ($c.Winner) { $lines += "  Winner=$($c.Winner) | Final=$($c.FinalScore) | ROI=$($c.ROI) | Brier=$($c.Brier) | LogLoss=$($c.LogLoss)" }
    if ($c.Reason) { $lines += "  Reason=$($c.Reason)" }
}

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    ledgerRows=$ledger.Count
    alreadySettledBeforeRun=$alreadySettled
    settledNow=$settledNow
    stillPendingMatchedNotFinal=$stillPending
    notMatched=$notMatched
    pendingAfter=$pendingAfter
    settledAfter=$settledAfter
    wins=$wins
    losses=$losses
    backup=$backup
    changes=@($changes)
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0
