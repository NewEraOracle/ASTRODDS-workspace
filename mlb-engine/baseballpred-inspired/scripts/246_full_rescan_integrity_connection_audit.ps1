$ErrorActionPreference = "Stop"

$root = "C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace"
$astro = Join-Path $root ".astrodds"
$scripts = Join-Path $root "mlb-engine\baseballpred-inspired\scripts"

$runner245b = Join-Path $scripts "245b_run_final_confidence_client_drop_NO_243.ps1"

$finalGate = Join-Path $astro "ASTRODDS-final-trusted-full-slate-gate-latest.csv"
$confidenceCsv = Join-Path $astro "ASTRODDS-simple-confidence-official-message-latest.csv"
$confidenceTxt = Join-Path $astro "ASTRODDS-simple-confidence-official-message-latest.txt"
$controlBoard = Join-Path $astro "ASTRODDS-schedule-first-full-slate-control-board-latest.csv"
$ledgerCsv = Join-Path $astro "ASTRODDS-official-picks-ledger-latest.csv"

$outTxt = Join-Path $astro "ASTRODDS-246-full-rescan-integrity-connection-audit-latest.txt"
$outCsv = Join-Path $astro "ASTRODDS-246-full-rescan-official-pick-audit-latest.csv"
$outJson = Join-Path $astro "ASTRODDS-246-full-rescan-integrity-connection-audit-latest.json"
$outChildLog = Join-Path $astro "ASTRODDS-246-full-rescan-child-log-latest.txt"

Write-Host ""
Write-Host "ASTRODDS 246 FULL RESCAN + CONNECTION INTEGRITY AUDIT" -ForegroundColor Cyan
Write-Host "POWERSHELL ONLY - LINEUPS / WEATHER / INJURIES / MODEL / MARKET" -ForegroundColor Cyan
Write-Host ""

$childLog = @()

function Run-Step($name, $path) {
    $start = Get-Date
    Write-Host "Running $name..." -ForegroundColor Cyan

    if (!(Test-Path $path)) {
        Write-Host "MISSING: $path" -ForegroundColor Yellow
        return [pscustomobject]@{
            Name = $name
            Status = "MISSING"
            ExitCode = ""
            DurationSec = 0
        }
    }

    try {
        $output = & powershell -ExecutionPolicy Bypass -File $path 2>&1
        $exitCode = $LASTEXITCODE
        $duration = [math]::Round(((Get-Date) - $start).TotalSeconds, 2)

        $script:childLog += ""
        $script:childLog += "============================================================"
        $script:childLog += "STEP: $name"
        $script:childLog += "PATH: $path"
        $script:childLog += "EXIT: $exitCode"
        $script:childLog += "DURATION: $duration sec"
        $script:childLog += "============================================================"
        $script:childLog += @($output | ForEach-Object { "$_" })

        if ($exitCode -eq 0 -or $null -eq $exitCode) {
            Write-Host "OK: $name ($duration sec)" -ForegroundColor Green
            return [pscustomobject]@{
                Name = $name
                Status = "OK"
                ExitCode = "0"
                DurationSec = $duration
            }
        } else {
            Write-Host "ERROR: $name exit $exitCode" -ForegroundColor Red
            return [pscustomobject]@{
                Name = $name
                Status = "ERROR"
                ExitCode = "$exitCode"
                DurationSec = $duration
            }
        }
    } catch {
        $duration = [math]::Round(((Get-Date) - $start).TotalSeconds, 2)

        $script:childLog += ""
        $script:childLog += "ERROR STEP: $name"
        $script:childLog += "$($_.Exception.Message)"

        Write-Host "ERROR: $name" -ForegroundColor Red
        Write-Host $_.Exception.Message

        return [pscustomobject]@{
            Name = $name
            Status = "ERROR"
            ExitCode = "1"
            DurationSec = $duration
        }
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

function Normalize-Team($s) {
    $x = "$s".ToLower().Trim()
    $x = $x -replace "[^a-z0-9 ]", ""
    $x = $x -replace "\s+", " "
    return $x
}

function Split-Key($game) {
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

    return (Normalize-Team $awayTeamName) + " @ " + (Normalize-Team $homeTeamName)
}

function Get-Matching-Fields($row, $patterns) {
    if ($null -eq $row) { return "" }

    $hits = @()

    foreach ($p in $row.PSObject.Properties) {
        $name = "$($p.Name)"
        $value = ""
        if ($null -ne $p.Value) {
            $value = "$($p.Value)".Trim()
        }

        if ($value -eq "") { continue }

        foreach ($pat in $patterns) {
            if ($name -match $pat) {
                $hits += "$name=$value"
                break
            }
        }
    }

    if ($hits.Count -eq 0) { return "" }

    return ($hits -join " | ")
}

function Find-Row-By-Game($rows, $game) {
    $key = Split-Key $game

    foreach ($r in $rows) {
        $g = Get-Val $r @("Game","game")
        if ($g -eq "") { continue }

        if ((Split-Key $g) -eq $key) {
            return $r
        }
    }

    return $null
}

function File-Group-Count($pattern) {
    if (!(Test-Path $astro)) { return 0 }

    return @(
        Get-ChildItem -Path $astro -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match $pattern }
    ).Count
}

function Latest-File-Name($pattern) {
    if (!(Test-Path $astro)) { return "" }

    $f = Get-ChildItem -Path $astro -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match $pattern } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1

    if ($null -eq $f) { return "" }

    return "$($f.Name) | $($f.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'))"
}

$steps = @()
$steps += ,(Run-Step "245B final confidence client drop runner" $runner245b)

$childLog | Set-Content -Encoding UTF8 $outChildLog

$finalRows = Safe-Csv $finalGate
$confidenceRows = Safe-Csv $confidenceCsv
$controlRows = Safe-Csv $controlBoard
$ledgerRows = Safe-Csv $ledgerCsv

$officialRows = @($finalRows | Where-Object {
    (Get-Val $_ @("FinalDecision")) -eq "CLIENT_OFFICIAL_SEND_OK"
})

$reviewRows = @($finalRows | Where-Object {
    (Get-Val $_ @("FinalDecision")) -like "REVIEW*"
})

$blockedRows = @($finalRows | Where-Object {
    (Get-Val $_ @("FinalDecision")) -eq "BLOCKED_FOR_REVIEW"
})

$noModelRows = @($finalRows | Where-Object {
    (Get-Val $_ @("HardBlocks")) -like "*NO_MODEL_YET*"
})

$connectionSummary = [pscustomobject]@{
    LineupFilesFound = File-Group-Count "lineup"
    WeatherFilesFound = File-Group-Count "weather|meteo|wind|rain|forecast"
    InjuryFilesFound = File-Group-Count "injur|injury|injuries|IL"
    PitcherFilesFound = File-Group-Count "pitcher|starter"
    BullpenFilesFound = File-Group-Count "bullpen"
    MarketFilesFound = File-Group-Count "market|price|odds|polymarket"
    LatestLineupFile = Latest-File-Name "lineup"
    LatestWeatherFile = Latest-File-Name "weather|meteo|wind|rain|forecast"
    LatestInjuryFile = Latest-File-Name "injur|injury|injuries|IL"
    LatestPitcherFile = Latest-File-Name "pitcher|starter"
    LatestBullpenFile = Latest-File-Name "bullpen"
    LatestMarketFile = Latest-File-Name "market|price|odds|polymarket"
}

$auditRows = @()

foreach ($r in $officialRows) {
    $game = Get-Val $r @("Game")
    $pick = Get-Val $r @("Pick")
    $control = Find-Row-By-Game $controlRows $game

    $lineupInfo = Get-Matching-Fields $r @("Lineup")
    $weatherInfo = Get-Matching-Fields $control @("weather","wind","temp","rain","precip","roof","humidity")
    $injuryInfo = Get-Matching-Fields $control @("injur","injury","IL","risk")
    $pitcherInfo = Get-Matching-Fields $control @("pitcher","starter","era","whip")
    $bullpenInfo = Get-Matching-Fields $control @("bullpen","fatigue","relief")

    $weatherStatus = "NOT_CONNECTED_OR_NOT_IN_ROW"
    if ($weatherInfo -ne "") { $weatherStatus = "CONNECTED" }

    $injuryStatus = "NOT_CONNECTED_OR_NOT_IN_ROW"
    if ($injuryInfo -ne "") { $injuryStatus = "CONNECTED" }

    $pitcherStatus = "NOT_CONNECTED_OR_NOT_IN_ROW"
    if ($pitcherInfo -ne "") { $pitcherStatus = "CONNECTED" }

    $bullpenStatus = "NOT_CONNECTED_OR_NOT_IN_ROW"
    if ($bullpenInfo -ne "") { $bullpenStatus = "CONNECTED" }

    $ledgerMatch = @($ledgerRows | Where-Object {
        (Get-Val $_ @("Pick")) -eq $pick -and
        (Get-Val $_ @("Game")) -eq $game -and
        (Get-Val $_ @("Status")) -eq "PENDING_RESULT"
    }).Count

    $auditRows += ,[pscustomobject]@{
        FinalDecision = Get-Val $r @("FinalDecision")
        Pick = $pick
        Game = $game
        Entry = Get-Val $r @("Price")
        Confidence = ""
        Model = Get-Val $r @("ModelProbability")
        Edge = Get-Val $r @("Edge")
        Lineups = $lineupInfo
        MlbStatus = Get-Val $r @("MlbStatus")
        WeatherStatus = $weatherStatus
        WeatherInfo = $weatherInfo
        InjuryStatus = $injuryStatus
        InjuryInfo = $injuryInfo
        PitcherStatus = $pitcherStatus
        PitcherInfo = $pitcherInfo
        BullpenStatus = $bullpenStatus
        BullpenInfo = $bullpenInfo
        LedgerPendingRows = $ledgerMatch
        Reason = Get-Val $r @("FinalReason")
    }
}

# Attach confidence values from the simplified client file
foreach ($a in $auditRows) {
    foreach ($c in $confidenceRows) {
        if ((Get-Val $c @("Pick")) -eq $a.Pick -and (Get-Val $c @("Game")) -eq $a.Game) {
            $a.Confidence = Get-Val $c @("Confidence")
        }
    }
}

$auditRows | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv

$scheduleGames = $controlRows.Count
$sendOk = $officialRows.Count
$review = $reviewRows.Count
$blocked = $blockedRows.Count
$noModel = $noModelRows.Count

$lineupsConfirmed = @($controlRows | Where-Object {
    (Get-Val $_ @("AwayLineupStatus")) -eq "confirmed" -and
    (Get-Val $_ @("HomeLineupStatus")) -eq "confirmed"
}).Count

$lineupsMissing = @($controlRows | Where-Object {
    (Get-Val $_ @("AwayLineupStatus")) -ne "confirmed" -or
    (Get-Val $_ @("HomeLineupStatus")) -ne "confirmed"
}).Count

$clientText = ""
if (Test-Path $confidenceTxt) {
    $clientText = Get-Content $confidenceTxt -Raw
}

$overallDecision = "PARTIAL_CLIENT_DROP_ALLOWED"
if ($sendOk -eq 0) {
    $overallDecision = "CLIENT_DROP_BLOCKED"
}

$lines = @()
$lines += "ASTRODDS 246 FULL RESCAN + CONNECTION INTEGRITY AUDIT"
$lines += ""
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$lines += "Overall decision: $overallDecision"
$lines += ""
$lines += "SUMMARY"
$lines += "- Schedule/control rows: $scheduleGames"
$lines += "- Official SEND_OK: $sendOk"
$lines += "- Review rows: $review"
$lines += "- Blocked rows: $blocked"
$lines += "- NO_MODEL_YET rows: $noModel"
$lines += "- Lineups confirmed games: $lineupsConfirmed"
$lines += "- Lineups missing games: $lineupsMissing"
$lines += ""

$lines += "CONNECTION CHECK"
$lines += "- Lineup files found: $($connectionSummary.LineupFilesFound) | Latest: $($connectionSummary.LatestLineupFile)"
$lines += "- Weather files found: $($connectionSummary.WeatherFilesFound) | Latest: $($connectionSummary.LatestWeatherFile)"
$lines += "- Injury files found: $($connectionSummary.InjuryFilesFound) | Latest: $($connectionSummary.LatestInjuryFile)"
$lines += "- Pitcher files found: $($connectionSummary.PitcherFilesFound) | Latest: $($connectionSummary.LatestPitcherFile)"
$lines += "- Bullpen files found: $($connectionSummary.BullpenFilesFound) | Latest: $($connectionSummary.LatestBullpenFile)"
$lines += "- Market/odds files found: $($connectionSummary.MarketFilesFound) | Latest: $($connectionSummary.LatestMarketFile)"
$lines += ""

$lines += "OFFICIAL PICK INTERNAL AUDIT"
if ($auditRows.Count -eq 0) {
    $lines += "- No official picks passed."
} else {
    foreach ($a in $auditRows) {
        $lines += "- $($a.Pick) | $($a.Game)"
        $lines += "  Entry=$($a.Entry) | Confidence=$($a.Confidence)/100 | Model=$($a.Model) | Edge=$($a.Edge) | Status=$($a.MlbStatus)"
        $lines += "  Lineups: $($a.Lineups)"
        $lines += "  Weather: $($a.WeatherStatus)"
        if ($a.WeatherInfo -ne "") { $lines += "    $($a.WeatherInfo)" }
        $lines += "  Injuries: $($a.InjuryStatus)"
        if ($a.InjuryInfo -ne "") { $lines += "    $($a.InjuryInfo)" }
        $lines += "  Pitcher: $($a.PitcherStatus)"
        if ($a.PitcherInfo -ne "") { $lines += "    $($a.PitcherInfo)" }
        $lines += "  Bullpen: $($a.BullpenStatus)"
        if ($a.BullpenInfo -ne "") { $lines += "    $($a.BullpenInfo)" }
        $lines += "  Ledger pending rows: $($a.LedgerPendingRows)"
        $lines += "  Decision reason: $($a.Reason)"
    }
}
$lines += ""

$lines += "REVIEW ROWS"
if ($reviewRows.Count -eq 0) {
    $lines += "- None"
} else {
    foreach ($r in $reviewRows) {
        $lines += "- $(Get-Val $r @('Pick')) | $(Get-Val $r @('Game')) | Edge=$(Get-Val $r @('Edge'))"
        $wr = Get-Val $r @("Warnings")
        if ($wr -ne "") { $lines += "  Warn: $wr" }
    }
}
$lines += ""

$lines += "BLOCKED SAMPLE"
foreach ($r in ($blockedRows | Select-Object -First 12)) {
    $lines += "- $(Get-Val $r @('Pick')) | $(Get-Val $r @('Game'))"
    $hb = Get-Val $r @("HardBlocks")
    if ($hb -ne "") { $lines += "  Hard: $hb" }
}
if ($blockedRows.Count -gt 12) {
    $lines += "- ... plus $($blockedRows.Count - 12) blocked rows"
}
$lines += ""

$lines += "CLIENT MESSAGE"
$lines += $clientText

[pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    overallDecision = $overallDecision
    scheduleRows = $scheduleGames
    officialSendOk = $sendOk
    review = $review
    blocked = $blocked
    noModelYet = $noModel
    lineupsConfirmedGames = $lineupsConfirmed
    lineupsMissingGames = $lineupsMissing
    connectionSummary = $connectionSummary
    officialAuditRows = @($auditRows)
    clientMessageFile = $confidenceTxt
    childLog = $outChildLog
} | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 $outJson

($lines -join [Environment]::NewLine) | Set-Content -Encoding UTF8 $outTxt

Write-Host ""
Write-Host ($lines -join [Environment]::NewLine)
Write-Host ""
Write-Host "Output TXT: $outTxt"
Write-Host "Output CSV: $outCsv"
Write-Host "Output JSON: $outJson"
Write-Host "Child log: $outChildLog"
Write-Host ""
