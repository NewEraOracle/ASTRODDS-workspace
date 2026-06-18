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

function Invoke-Json($url, $timeout = 25) {
    try { return Invoke-RestMethod -Uri $url -Method Get -TimeoutSec $timeout }
    catch { return $null }
}

function Run-Step($name, $path, [ref]$childLog) {
    $start = Get-Date
    Write-Host "Running $name..." -ForegroundColor Cyan

    if (!(Test-Path $path)) {
        Write-Host "MISSING: $path" -ForegroundColor Yellow
        return [pscustomobject]@{Name=$name;Status="MISSING";ExitCode="";DurationSec=0}
    }

    try {
        $output = & powershell -ExecutionPolicy Bypass -File $path 2>&1
        $exitCode = $LASTEXITCODE
        $duration = [math]::Round(((Get-Date)-$start).TotalSeconds,2)
        $childLog.Value += ""
        $childLog.Value += "============================================================"
        $childLog.Value += "STEP: $name"
        $childLog.Value += "PATH: $path"
        $childLog.Value += "EXIT: $exitCode"
        $childLog.Value += "DURATION: $duration sec"
        $childLog.Value += "============================================================"
        $childLog.Value += @($output | ForEach-Object { "$_" })
        if ($exitCode -eq 0 -or $null -eq $exitCode) {
            Write-Host "OK: $name ($duration sec)" -ForegroundColor Green
            return [pscustomobject]@{Name=$name;Status="OK";ExitCode="0";DurationSec=$duration}
        } else {
            Write-Host "ERROR: $name exit $exitCode" -ForegroundColor Red
            return [pscustomobject]@{Name=$name;Status="ERROR";ExitCode="$exitCode";DurationSec=$duration}
        }
    } catch {
        $duration = [math]::Round(((Get-Date)-$start).TotalSeconds,2)
        $childLog.Value += ""
        $childLog.Value += "ERROR STEP: $name"
        $childLog.Value += "$($_.Exception.Message)"
        return [pscustomobject]@{Name=$name;Status="ERROR";ExitCode="1";DurationSec=$duration}
    }
}

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
Ensure-Dir $astro

$outCsv = Join-Path $astro "ASTRODDS-smart-scan-window-plan-latest.csv"
$outTxt = Join-Path $astro "ASTRODDS-337-smart-scan-window-planner-latest.txt"
$outJson = Join-Path $astro "ASTRODDS-337-smart-scan-window-planner-latest.json"

Write-Host ""
Write-Host "ASTRODDS 337 SMART SCAN WINDOW PLANNER" -ForegroundColor Cyan
Write-Host "Plans scan windows to protect Odds credits." -ForegroundColor Cyan
Write-Host ""

$today = Get-Date
$date = $today.ToString("yyyy-MM-dd")
$url = "https://statsapi.mlb.com/api/v1/schedule?sportId=1&date=$date&hydrate=probablePitcher,team"
$resp = Invoke-Json $url 25

$rows = @()
if ($null -ne $resp) {
    foreach ($d in @($resp.dates)) {
        foreach ($g in @($d.games)) {
            $gamePk = "$($g.gamePk)"
            $away = "$($g.teams.away.team.name)"
            $homeTeam = "$($g.teams.home.team.name)"
            $status = "$($g.status.detailedState)"
            $gameDateUtc = [datetime]::Parse("$($g.gameDate)").ToUniversalTime()
            $gameDateLocal = $gameDateUtc.ToLocalTime()
            $mins = [math]::Round(($gameDateLocal - (Get-Date)).TotalMinutes, 1)

            $lineupWindow = "NO"
            $paidOddsWindow = "NO"
            $newDropAllowed = "NO"
            $recommendedAction = "NO_SCAN"
            $reason = ""

            if ($status -match "Final|Game Over|Completed") {
                $recommendedAction = "SETTLEMENT_ONLY"
                $reason = "game final or completed"
            } elseif ($status -match "In Progress|Manager challenge|Delayed|Suspended") {
                $recommendedAction = "LIVE_BLOCK_NEW_DROPS_SETTLEMENT_WATCH"
                $reason = "game already live/not safe for new client drop"
            } elseif ($mins -gt 240) {
                $recommendedAction = "MORNING_WATCHLIST_FREE_ONLY"
                $reason = "too early; free sources only"
            } elseif ($mins -le 240 -and $mins -gt 75) {
                $recommendedAction = "WATCHLIST_FREE_SOURCES_ONLY"
                $reason = "pre-window; update free context, no paid odds unless candidate already exists"
            } elseif ($mins -le 75 -and $mins -gt 45) {
                $recommendedAction = "PREGAME_CONTEXT_SCAN"
                $lineupWindow = "YES"
                $reason = "75-45 min pregame; check lineups/context"
            } elseif ($mins -le 45 -and $mins -gt 15) {
                $recommendedAction = "FINAL_VALUE_SCAN"
                $lineupWindow = "YES"
                $paidOddsWindow = "CANDIDATE_ONLY"
                $newDropAllowed = "YES"
                $reason = "45-15 min pregame; final value scan if candidate"
            } elseif ($mins -le 15 -and $mins -gt 0) {
                $recommendedAction = "LAST_CALL_STRICT_SCAN"
                $lineupWindow = "YES"
                $paidOddsWindow = "CANDIDATE_ONLY"
                $newDropAllowed = "YES_STRICT"
                $reason = "under 15 min; only very strict clean SEND_OK"
            } elseif ($mins -le 0) {
                $recommendedAction = "LIVE_BLOCK_NEW_DROPS_SETTLEMENT_WATCH"
                $reason = "start time passed"
            }

            $rows += ,[pscustomobject]@{
                GamePk = $gamePk
                Game = "$away @ $homeTeam"
                MlbStatus = $status
                GameTimeLocal = $gameDateLocal.ToString("yyyy-MM-dd HH:mm:ss")
                MinutesToStart = $mins
                RecommendedAction = $recommendedAction
                LineupWindow = $lineupWindow
                PaidOddsWindow = $paidOddsWindow
                NewDropAllowed = $newDropAllowed
                Reason = $reason
            }
        }
    }
}

$rows | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$counts = $rows | Group-Object RecommendedAction | Sort-Object Name
$shouldRunFull = @($rows | Where-Object { $_.RecommendedAction -in @("PREGAME_CONTEXT_SCAN","FINAL_VALUE_SCAN","LAST_CALL_STRICT_SCAN") }).Count -gt 0
$shouldSettle = @($rows | Where-Object { $_.RecommendedAction -match "SETTLEMENT|LIVE_BLOCK" }).Count -gt 0
$globalAction = "IDLE_OR_SETTLEMENT_ONLY"
if ($shouldRunFull) { $globalAction = "RUN_FULL_PRODUCTION_SCAN" }
elseif ($shouldSettle) { $globalAction = "RUN_SETTLEMENT_AND_REPORTS_ONLY" }

$lines = @()
$lines += "ASTRODDS 337 SMART SCAN WINDOW PLANNER"
$lines += ""
$lines += "Date: $date"
$lines += "Games: $($rows.Count)"
$lines += "Global action: $globalAction"
$lines += ""
$lines += "COUNTS"
foreach ($c in $counts) { $lines += "- $($c.Name): $($c.Count)" }
$lines += ""
$lines += "PLAN"
foreach ($r in ($rows | Sort-Object GameTimeLocal)) {
    $lines += "- $($r.RecommendedAction) | $($r.Game) | $($r.MlbStatus) | start=$($r.GameTimeLocal) | min=$($r.MinutesToStart) | odds=$($r.PaidOddsWindow) | drop=$($r.NewDropAllowed)"
}

[pscustomobject]@{
    generatedAt=(Get-Date).ToString("o")
    date=$date
    games=$rows.Count
    globalAction=$globalAction
    shouldRunFullProductionScan=$shouldRunFull
    shouldRunSettlementOnly=$shouldSettle
    outputCsv=$outCsv
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt
Write-Host ($lines -join [Environment]::NewLine)
exit 0

