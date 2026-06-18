$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"

$ledgerCsv = Join-Path $astro "ASTRODDS-official-picks-ledger-latest.csv"
$ledgerJson = Join-Path $astro "ASTRODDS-official-picks-ledger-latest.json"
$outTxt = Join-Path $astro "ASTRODDS-250-settle-official-picks-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-250-settle-official-picks-latest.json"

Write-Host ""
Write-Host "ASTRODDS 250 SETTLE OFFICIAL PICKS" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - WIN/LOSS/ROI/BRIER/LOGLOSS" -ForegroundColor Cyan
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

function Num-Prob($v) {
    if ($null -eq $v) { return $null }
    $s = "$v".Trim()
    if ($s -eq "") { return $null }
    $s = $s.Replace("%","").Replace("¢","").Replace(",", ".")
    $n = 0.0
    $culture = [System.Globalization.CultureInfo]::InvariantCulture
    if ([double]::TryParse($s, [System.Globalization.NumberStyles]::Any, $culture, [ref]$n)) {
        if ($n -gt 1) { $n = $n / 100.0 }
        if ($n -gt 0 -and $n -lt 1) { return $n }
    }
    return $null
}

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
    return [pscustomobject]@{ Away=$awayTeamName; Home=$homeTeamName; AwayNorm=(Normalize-Team $awayTeamName); HomeNorm=(Normalize-Team $homeTeamName) }
}

function Get-MlbSchedule($date) {
    $url = "https://statsapi.mlb.com/api/v1/schedule?sportId=1&date=$date"
    try { return Invoke-RestMethod -Uri $url -Method Get -TimeoutSec 15 }
    catch { return $null }
}

function Find-GameResult($date, $game, $gamePk) {
    $sched = Get-MlbSchedule $date
    if ($null -eq $sched -or $null -eq $sched.dates) { return $null }

    $split = Split-Game $game

    foreach ($d in @($sched.dates)) {
        foreach ($g in @($d.games)) {
            $pk = "$($g.gamePk)"
            $awayTeamName = "$($g.teams.away.team.name)"
            $homeTeamName = "$($g.teams.home.team.name)"
            $awayNorm = Normalize-Team $awayTeamName
            $homeNorm = Normalize-Team $homeTeamName

            $match = $false
            if ($gamePk -ne "" -and $pk -eq "$gamePk") { $match = $true }
            if ($awayNorm -eq $split.AwayNorm -and $homeNorm -eq $split.HomeNorm) { $match = $true }

            if ($match) {
                $status = "$($g.status.detailedState)"
                $awayScore = $null
                $homeScore = $null
                try { $awayScore = [int]$g.teams.away.score } catch {}
                try { $homeScore = [int]$g.teams.home.score } catch {}

                $winner = ""
                if ($status -match "Final" -and $null -ne $awayScore -and $null -ne $homeScore) {
                    if ($awayScore -gt $homeScore) { $winner = $awayTeamName }
                    elseif ($homeScore -gt $awayScore) { $winner = $homeTeamName }
                }

                return [pscustomobject]@{
                    GamePk = $pk
                    Status = $status
                    AwayTeam = $awayTeamName
                    HomeTeam = $homeTeamName
                    AwayScore = $awayScore
                    HomeScore = $homeScore
                    Winner = $winner
                    FinalScore = if ($null -ne $awayScore -and $null -ne $homeScore) { "$awayTeamName $awayScore - $homeScore $homeTeamName" } else { "" }
                }
            }
        }
    }

    return $null
}

$rows = Safe-Csv $ledgerCsv
if ($rows.Count -eq 0) {
    Write-Host "No ledger rows found."
    exit 0
}

$updated = @()
$settledCount = 0
$pendingCount = 0

foreach ($r in $rows) {
    $status = Get-Val $r @("Status")
    $game = Get-Val $r @("Game")
    $pick = Get-Val $r @("Pick")
    $date = Get-Val $r @("ScheduleDate")
    if ($date -eq "") {
        $logged = Get-Val $r @("LoggedAt")
        if ($logged -match "^\d{4}-\d{2}-\d{2}") { $date = $matches[0] }
        else { $date = Get-Date -Format "yyyy-MM-dd" }
    }

    $gamePk = Get-Val $r @("GamePk")

    if ($status -eq "PENDING_RESULT" -or (Get-Val $r @("Result")) -eq "") {
        $res = Find-GameResult $date $game $gamePk

        if ($null -ne $res -and $res.Status -match "Final" -and $res.Winner -ne "") {
            $entryProb = Num-Prob (Get-Val $r @("EntryPrice"))
            $modelProb = Num-Prob (Get-Val $r @("ModelProbability","PublicModel","FullSlateModel"))

            $outcome = 0
            $result = "LOSS"
            if ((Normalize-Team $res.Winner) -eq (Normalize-Team $pick)) {
                $outcome = 1
                $result = "WIN"
            }

            $roi = ""
            if ($null -ne $entryProb) {
                if ($outcome -eq 1) { $roi = ([math]::Round(((1.0 / $entryProb) - 1.0) * 100.0, 2)).ToString() + "%" }
                else { $roi = "-100%" }
            }

            $brier = ""
            $logLoss = ""
            if ($null -ne $modelProb) {
                $brier = [math]::Round([math]::Pow(($modelProb - $outcome), 2), 5)
                $p = [math]::Min(0.999999, [math]::Max(0.000001, $modelProb))
                if ($outcome -eq 1) { $logLoss = [math]::Round(-[math]::Log($p), 5) }
                else { $logLoss = [math]::Round(-[math]::Log(1.0 - $p), 5) }
            }

            $updated += ,[pscustomobject]@{
                LedgerKey = Get-Val $r @("LedgerKey")
                LoggedAt = Get-Val $r @("LoggedAt")
                Status = "SETTLED"
                Sport = Get-Val $r @("Sport")
                MarketType = Get-Val $r @("MarketType")
                Pick = $pick
                Game = $game
                ScheduleDate = $date
                GamePk = if ($gamePk -ne "") { $gamePk } else { $res.GamePk }
                MlbStatusAtLog = Get-Val $r @("MlbStatusAtLog")
                EntryPrice = Get-Val $r @("EntryPrice")
                ModelProbability = Get-Val $r @("ModelProbability")
                FullSlateModel = Get-Val $r @("FullSlateModel")
                MarketProbability = Get-Val $r @("MarketProbability")
                Edge = Get-Val $r @("Edge")
                Stake = Get-Val $r @("Stake")
                AwayLineupStatus = Get-Val $r @("AwayLineupStatus")
                HomeLineupStatus = Get-Val $r @("HomeLineupStatus")
                PaperOnly = Get-Val $r @("PaperOnly")
                Result = $result
                Winner = $res.Winner
                FinalScore = $res.FinalScore
                ClosingPrice = Get-Val $r @("ClosingPrice")
                CLV = Get-Val $r @("CLV")
                ROI = $roi
                BrierComponent = $brier
                LogLossComponent = $logLoss
                SourceGate = Get-Val $r @("SourceGate")
                TelegramFile = Get-Val $r @("TelegramFile")
            }
            $settledCount++
        } else {
            $updated += ,$r
            $pendingCount++
        }
    } else {
        $updated += ,$r
        if ($status -eq "SETTLED") { $settledCount++ } else { $pendingCount++ }
    }
}

$updated | Export-Csv -NoTypeInformation -Encoding UTF8 $ledgerCsv
$updated | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 $ledgerJson

$totalSettled = @($updated | Where-Object { (Get-Val $_ @("Status")) -eq "SETTLED" }).Count
$wins = @($updated | Where-Object { (Get-Val $_ @("Result")) -eq "WIN" }).Count
$losses = @($updated | Where-Object { (Get-Val $_ @("Result")) -eq "LOSS" }).Count
$pending = @($updated | Where-Object { (Get-Val $_ @("Status")) -eq "PENDING_RESULT" }).Count

$lines = @()
$lines += "ASTRODDS 250 SETTLE OFFICIAL PICKS"
$lines += ""
$lines += "Rows checked: $($rows.Count)"
$lines += "Newly settled this run: $settledCount"
$lines += "Total settled: $totalSettled"
$lines += "Wins: $wins"
$lines += "Losses: $losses"
$lines += "Pending: $pending"
$lines += ""
$lines += "LEDGER"
foreach ($r in $updated) {
    $lines += "- $(Get-Val $r @('Status')) | $(Get-Val $r @('Result')) | $(Get-Val $r @('Pick')) | $(Get-Val $r @('Game')) | ROI=$(Get-Val $r @('ROI')) | Score=$(Get-Val $r @('FinalScore'))"
}

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    rowsChecked = $rows.Count
    newlySettled = $settledCount
    totalSettled = $totalSettled
    wins = $wins
    losses = $losses
    pending = $pending
    ledger = $ledgerCsv
} | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $outJson

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output JSON: $outJson"
Write-Host "Ledger CSV: $ledgerCsv"
Write-Host ""
